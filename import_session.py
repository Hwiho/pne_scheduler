"""Open an existing `.sch` without losing what was already in it.

Reading a schedule the lab already runs is not the same as authoring one. The
file on disk is the artifact CTSEditorPro produced and, in most cases, the only
copy whose exact bytes anything has been verified against. Round-tripping it
through the IR and writing it back would replace every byte — including the
1760-byte header and the fields whose meaning is still unproven — with the
writer's best guess.

So an import session has two exits, and they are deliberately different sizes:

* **Patch** — the default. The original bytes are kept and only *writer-ready*
  fields, the ones promoted by CTSPro reopen evidence, may be edited. The output
  is the source file with those offsets rewritten and nothing else touched. A
  digest check refuses to patch bytes other than the ones that were read.
* **Clone as draft** — explicitly lossy. The parsed steps become a `.schproj`
  that can be authored freely, and the result is a *new* schedule with no claim
  on the original's verification. It is not a way to edit the source file.

A session never writes on its own; it produces a plan the caller applies, so the
same export gates apply as anywhere else.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .io.sch_parser import ScheduleDocument, parse_schedule_file
from .io.template_writer import SchFieldPatch, SchPatchPlan
from .schema.fields import get_step_fields, get_writer_ready_fields


@dataclass(frozen=True, slots=True)
class EditableField:
    """A field this session will let a user change, and why it is allowed."""

    name: str
    offset: int
    dtype: str
    evidence: str


@dataclass(frozen=True, slots=True)
class RejectedEdit:
    step_no: int
    field: str
    reason: str


@dataclass(frozen=True, slots=True)
class PatchProposal:
    source_path: Path
    source_sha256: str
    plan: SchPatchPlan | None = None
    accepted: tuple[SchFieldPatch, ...] = ()
    rejected: tuple[RejectedEdit, ...] = ()
    notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.plan is not None and bool(self.accepted)


@dataclass(frozen=True, slots=True)
class CloneProposal:
    """A lossy conversion to an authorable draft, with what was dropped."""

    steps: tuple[dict[str, Any], ...] = ()
    dropped: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return bool(self.steps)


@dataclass
class ImportSession:
    """A `.sch` held open with its bytes, its digest, and its parse."""

    path: Path
    raw: bytes
    sha256: str
    document: ScheduleDocument
    edits: dict[tuple[int, str], int | float] = field(default_factory=dict)

    # ------------------------------------------------------------- opening

    @classmethod
    def open(cls, path: str | Path) -> ImportSession:
        resolved = Path(path)
        raw = resolved.read_bytes()
        return cls(
            path=resolved,
            raw=raw,
            sha256=hashlib.sha256(raw).hexdigest(),
            document=parse_schedule_file(resolved),
        )

    @property
    def sch_version(self) -> int | None:
        return self.document.sch_version

    @property
    def step_count(self) -> int:
        return len(self.document.steps)

    def source_unchanged(self) -> bool:
        """Whether the file on disk still matches what this session read."""
        try:
            current = hashlib.sha256(self.path.read_bytes()).hexdigest()
        except OSError:
            return False
        return current == self.sha256

    # ------------------------------------------------------------- editing

    def editable_fields(self) -> tuple[EditableField, ...]:
        """Only fields promoted by reopen evidence may be edited in place."""
        version = self.sch_version
        if version is None:
            return ()
        allowed = set(get_writer_ready_fields(version))
        return tuple(
            EditableField(
                name=definition.name,
                offset=definition.offset,
                dtype=definition.dtype,
                evidence=definition.evidence,
            )
            for definition in get_step_fields(version)
            if definition.name in allowed
        )

    def stage(self, step_no: int, field_name: str, value: int | float) -> None:
        """Record an intended edit. Nothing is written until a plan is applied."""
        self.edits[(int(step_no), str(field_name))] = value

    def clear(self) -> None:
        self.edits.clear()

    # ------------------------------------------------------------ proposing

    def propose_patch(self) -> PatchProposal:
        """Turn staged edits into a plan, refusing everything unproven."""
        editable = {item.name for item in self.editable_fields()}
        accepted: list[SchFieldPatch] = []
        rejected: list[RejectedEdit] = []
        warnings: list[str] = []

        version = self.sch_version
        for (step_no, field_name), value in sorted(self.edits.items()):
            if version is None:
                rejected.append(
                    RejectedEdit(step_no, field_name, "SCH 버전을 알 수 없습니다.")
                )
                continue
            if step_no < 1 or step_no > self.step_count:
                rejected.append(
                    RejectedEdit(
                        step_no, field_name,
                        f"스텝 번호가 범위를 벗어납니다 (1–{self.step_count}).",
                    )
                )
                continue
            if field_name not in editable:
                rejected.append(
                    RejectedEdit(
                        step_no,
                        field_name,
                        "이 필드는 writer-ready 가 아닙니다. CTSPro 재열기 근거로 "
                        "승격된 필드만 원본을 고쳐 쓸 수 있습니다.",
                    )
                )
                continue
            accepted.append(SchFieldPatch(step_no=step_no, field=field_name, value=value))

        notes = [
            f"원본 {self.path.name} · 스텝 {self.step_count}개 · "
            f"SHA-256 {self.sha256[:12]}…",
            f"고칠 수 있는 필드 {len(editable)}종: {', '.join(sorted(editable)) or '없음'}",
        ]
        if rejected:
            warnings.append(
                f"{len(rejected)}개 편집을 적용하지 않습니다. "
                "근거 없는 오프셋에 쓰면 장비가 무엇을 읽을지 알 수 없습니다."
            )
        if not self.source_unchanged():
            warnings.append(
                "원본 파일이 열어본 뒤 바뀌었습니다. 다시 열고 편집하십시오."
            )
        warnings.append(
            "패치는 원본 바이트를 그대로 두고 해당 오프셋만 덮어씁니다. "
            "결과 파일도 CTSPro 재열기 확인 전에는 장비 실행용이 아닙니다."
        )

        plan = (
            SchPatchPlan(
                template_sha256=self.sha256,
                expected_version=version,
                patches=tuple(accepted),
            )
            if accepted
            else None
        )
        return PatchProposal(
            source_path=self.path,
            source_sha256=self.sha256,
            plan=plan,
            accepted=tuple(accepted),
            rejected=tuple(rejected),
            notes=tuple(notes),
            warnings=tuple(warnings),
        )

    def propose_clone(self) -> CloneProposal:
        """Convert to authorable steps, naming everything the conversion drops."""
        steps = tuple(
            {
                "step_no": view.step_no,
                "step_type": view.step_type,
                "c_rate": view.c_rate,
                "end_time_s": view.f_end_time,
                "end_voltage_v": view.f_end_v,
            }
            for view in self.document.steps
        )
        dropped = (
            "CTSPro 가 쓴 1760바이트 헤더 (원본에만 있습니다)",
            "의미가 확인되지 않은 스텝 필드 (writer-ready 가 아닌 오프셋 전체)",
            "원본의 SHA-256 과 그에 딸린 모든 검토 기록",
        )
        return CloneProposal(
            steps=steps,
            dropped=dropped,
            warnings=(
                "초안 복제는 새 스케줄입니다. 원본을 고치는 방법이 아니며, "
                "원본이 받은 검증을 물려받지 않습니다.",
                "원본 파일을 고치려면 패치 경로를 쓰십시오.",
            ),
        )


__all__ = [
    "CloneProposal",
    "EditableField",
    "ImportSession",
    "PatchProposal",
    "RejectedEdit",
]
