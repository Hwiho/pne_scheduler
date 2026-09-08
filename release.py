"""Output paths and the review ladder that gates them.

Saving a draft is always allowed — a user must be able to store broken work
and come back to it.  Everything that leaves the tool is gated, and each gate
says in one sentence what is blocking it and what to do next.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .ir.equipment_profile import effective_current_limit_mA
from .ir.project import ScheduleProject
from .validate.preflight import PreflightIssue, validate_project

Stage = Literal[
    "draft",
    "software_checked",
    "ctspro_pending",
    "ctspro_confirmed",
    "equipment_approved",
]

STAGE_LADDER: tuple[tuple[Stage, str], ...] = (
    ("draft", "초안"),
    ("software_checked", "소프트웨어 검증"),
    ("ctspro_pending", "CTSPro 확인 대기"),
    ("ctspro_confirmed", "CTSPro 확인 완료"),
    ("equipment_approved", "장비 실행 승인"),
)

STAGE_LABELS: dict[str, str] = dict(STAGE_LADDER)

# The only writer path proven against a real CTSPro-authored file today.
REOPEN_SUPPORTED_UNIT = "PNE02"
REOPEN_SUPPORTED_LAYOUT = "0x00010003/612"


@dataclass(frozen=True, slots=True)
class OutputOption:
    kind: str
    title: str
    description: str
    allowed: bool
    blockers: tuple[str, ...] = ()
    next_action: str = ""
    danger: bool = False

    @property
    def status_text(self) -> str:
        return "가능" if self.allowed else "잠김"


@dataclass(frozen=True, slots=True)
class ReleaseState:
    stage: Stage
    stage_label: str
    stage_index: int
    options: tuple[OutputOption, ...]
    errors: tuple[PreflightIssue, ...] = ()
    warnings: tuple[PreflightIssue, ...] = ()

    def option(self, kind: str) -> OutputOption | None:
        return next((option for option in self.options if option.kind == kind), None)

    def allows(self, kind: str) -> bool:
        option = self.option(kind)
        return bool(option and option.allowed)

    def ladder(self) -> tuple[tuple[str, str, bool], ...]:
        """(stage, label, reached) for rendering the progress ladder."""
        return tuple(
            (stage, label, index <= self.stage_index)
            for index, (stage, label) in enumerate(STAGE_LADDER)
        )


def evaluate_release(project: ScheduleProject) -> ReleaseState:
    """Current stage plus every output path with its concrete blockers."""
    preview = validate_project(project, purpose="preview")
    production = validate_project(project, purpose="production")

    software_ok = preview.passed
    equipment = project.equipment
    equipment_blockers: list[str] = []
    if equipment is None:
        equipment_blockers.append("장비 프로파일이 없습니다 (설정 탭에서 PNE 장비 선택).")
    else:
        missing = equipment.missing_fields()
        if missing:
            equipment_blockers.append(f"장비 정보가 부족합니다: {', '.join(missing)}.")
        if equipment.unit != REOPEN_SUPPORTED_UNIT:
            equipment_blockers.append(
                f"검토용 SCH 생성은 현재 {REOPEN_SUPPORTED_UNIT} 레이아웃만 검증되어 있습니다 "
                f"(현재 {equipment.unit})."
            )
        elif equipment.layout_key != REOPEN_SUPPORTED_LAYOUT:
            equipment_blockers.append(
                f"검증된 SCH layout 은 {REOPEN_SUPPORTED_LAYOUT} 입니다 "
                f"(현재 {equipment.layout_key})."
            )

    limit = effective_current_limit_mA(
        project.cell_profile.max_current_mA, equipment
    )
    limit_blockers: list[str] = []
    if limit is None:
        limit_blockers.append("최대 전류 한계가 지정되지 않아 안전 확인을 할 수 없습니다.")

    software_blockers = tuple(
        f"[{issue.code}] {issue.message}" for issue in preview.errors
    )
    production_blockers = tuple(
        f"[{issue.code}] {issue.message}" for issue in production.errors
    )

    review = project.review
    stage: Stage = "draft"
    if software_ok:
        stage = "software_checked"
    if software_ok and not equipment_blockers:
        stage = "ctspro_pending"
    if review.ctspro_reviewed:
        stage = "ctspro_confirmed"
    if review.ctspro_reviewed and review.equipment_approved:
        stage = "equipment_approved"
    stage_index = next(
        index for index, (name, _) in enumerate(STAGE_LADDER) if name == stage
    )

    options: list[OutputOption] = [
        OutputOption(
            kind="draft_save",
            title="초안 저장 (.schproj)",
            description="검증 오류가 있어도 언제나 저장할 수 있습니다. 나중에 이어서 고칠 수 있습니다.",
            allowed=True,
            next_action="Ctrl+S",
        ),
        OutputOption(
            kind="preview",
            title="스텝 미리보기 · 요약 내보내기",
            description="확장된 스텝 목록과 한국어 요약을 파일로 저장합니다. 장비로 보내지 않습니다.",
            allowed=software_ok,
            blockers=software_blockers,
            next_action="검증 탭의 오류를 먼저 해결하세요.",
        ),
        OutputOption(
            kind="review_candidate",
            title="CTSPro 검토용 SCH (실행 금지)",
            description="CTSEditorPro 로 열어 값을 눈으로 확인하기 위한 후보 파일입니다. 장비 실행용이 아닙니다.",
            allowed=software_ok and not equipment_blockers and not limit_blockers,
            blockers=tuple([*software_blockers, *equipment_blockers, *limit_blockers]),
            next_action="장비 프로파일과 소프트웨어 검증을 먼저 통과시키세요.",
            danger=True,
        ),
        OutputOption(
            kind="template_patch",
            title="템플릿 패치 (기존 SCH 수정)",
            description="CTSPro 가 만든 원본 SCH 의 검증된 필드만 바꿔 씁니다. 가장 안전한 경로입니다.",
            allowed=software_ok,
            blockers=software_blockers,
            next_action="원본 .sch 와 SHA-256 을 준비한 뒤 patch-sch 명령을 사용하세요.",
        ),
        OutputOption(
            kind="equipment_export",
            title="장비 실행용 내보내기",
            description="실제 장비에서 돌릴 수 있는 파일입니다. CTSPro 확인과 장비 승인이 모두 필요합니다.",
            allowed=(
                not production_blockers
                and not equipment_blockers
                and review.ctspro_reviewed
                and review.equipment_approved
            ),
            blockers=tuple(
                [
                    *production_blockers,
                    *equipment_blockers,
                    *(
                        ()
                        if review.ctspro_reviewed
                        else ("CTSPro 재열기 확인이 기록되지 않았습니다.",)
                    ),
                    *(
                        ()
                        if review.equipment_approved
                        else ("장비 실행 승인이 기록되지 않았습니다.",)
                    ),
                ]
            ),
            next_action="검토용 SCH 를 CTSPro 에서 확인한 뒤 내보내기 탭에서 승인을 기록하세요.",
            danger=True,
        ),
    ]

    return ReleaseState(
        stage=stage,
        stage_label=STAGE_LABELS[stage],
        stage_index=stage_index,
        options=tuple(options),
        errors=preview.errors,
        warnings=preview.warnings,
    )


__all__ = [
    "OutputOption",
    "REOPEN_SUPPORTED_LAYOUT",
    "REOPEN_SUPPORTED_UNIT",
    "ReleaseState",
    "STAGE_LABELS",
    "STAGE_LADDER",
    "Stage",
    "evaluate_release",
]
