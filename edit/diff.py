"""Change impact: what an edit does to the expanded step list, before saving.

"Raise the loop count" and "change the variant" look identical in a form and
are wildly different in the schedule.  Showing the step-level consequence of
an edit ahead of time is the cheapest way to stop a wrong one.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from ..ir.project import ScheduleProject
from ..ir.step_intent import StepIntent
from ..spec import units

_COMPARED_FIELDS = (
    "step_type", "mode", "c_rate", "cv_cutoff_c_rate", "current_mA",
    "cv_cutoff_mA", "voltage_v", "end_voltage_v", "end_time_s",
    "end_capacity_fraction", "dod_percent", "loop_goto_step", "loop_count",
)

_FIELD_LABELS_KO = {
    "step_type": "스텝 종류",
    "mode": "모드",
    "c_rate": "전류(C-rate)",
    "cv_cutoff_c_rate": "CV 종료 전류",
    "current_mA": "전류(mA)",
    "cv_cutoff_mA": "CV 종료 전류(mA)",
    "voltage_v": "전압 한계",
    "end_voltage_v": "종료 전압",
    "end_time_s": "시간 종료 조건",
    "end_capacity_fraction": "용량 종료 조건",
    "dod_percent": "DOD",
    "loop_goto_step": "LOOP 대상",
    "loop_count": "LOOP 횟수",
}


@dataclass(frozen=True, slots=True)
class FieldChange:
    field: str
    before: Any
    after: Any

    def describe(self) -> str:
        label = _FIELD_LABELS_KO.get(self.field, self.field)
        return f"{label}: {_render(self.field, self.before)} → {_render(self.field, self.after)}"


@dataclass(frozen=True, slots=True)
class StepChange:
    kind: str  # "added" | "removed" | "changed"
    before_index: int | None
    after_index: int | None
    label: str
    fields: tuple[FieldChange, ...] = ()

    def describe(self) -> str:
        position = self.after_index or self.before_index or 0
        if self.kind == "added":
            return f"+ {position}번 스텝 추가 — {self.label}"
        if self.kind == "removed":
            return f"- {position}번 스텝 삭제 — {self.label}"
        detail = ", ".join(change.describe() for change in self.fields)
        return f"~ {position}번 스텝 변경 — {detail}"


@dataclass(frozen=True, slots=True)
class StepDiff:
    changes: tuple[StepChange, ...]
    before_count: int
    after_count: int
    # Set when one side could not be expanded at all, so "everything was
    # deleted" is not reported as if it were a real step change.
    note: str = ""

    @property
    def added(self) -> int:
        return sum(1 for change in self.changes if change.kind == "added")

    @property
    def removed(self) -> int:
        return sum(1 for change in self.changes if change.kind == "removed")

    @property
    def modified(self) -> int:
        return sum(1 for change in self.changes if change.kind == "changed")

    @property
    def is_empty(self) -> bool:
        return not self.changes

    def headline(self) -> str:
        if self.note:
            return self.note
        if self.is_empty:
            return "스텝에는 변화가 없습니다."
        parts: list[str] = []
        if self.added:
            parts.append(f"{self.added}개 추가")
        if self.removed:
            parts.append(f"{self.removed}개 삭제")
        if self.modified:
            parts.append(f"{self.modified}개 값 변경")
        return (
            f"스텝 {self.before_count} → {self.after_count} · " + ", ".join(parts)
        )

    def preview_lines(self, limit: int = 12) -> tuple[str, ...]:
        lines = [change.describe() for change in self.changes[:limit]]
        if len(self.changes) > limit:
            lines.append(f"… 외 {len(self.changes) - limit}건")
        return tuple(lines)


def diff_steps(before: list[StepIntent], after: list[StepIntent]) -> StepDiff:
    """Align two step lists by shape, then report per-field differences."""
    before_keys = [_signature(step) for step in before]
    after_keys = [_signature(step) for step in after]
    matcher = SequenceMatcher(a=before_keys, b=after_keys, autojunk=False)
    changes: list[StepChange] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace":
            paired = min(i2 - i1, j2 - j1)
            for offset in range(paired):
                old, new = before[i1 + offset], after[j1 + offset]
                fields = _field_changes(old, new)
                if fields:
                    changes.append(
                        StepChange("changed", i1 + offset + 1, j1 + offset + 1, _label(new), fields)
                    )
            for index in range(i1 + paired, i2):
                changes.append(StepChange("removed", index + 1, None, _label(before[index])))
            for index in range(j1 + paired, j2):
                changes.append(StepChange("added", None, index + 1, _label(after[index])))
        elif tag == "delete":
            for index in range(i1, i2):
                changes.append(StepChange("removed", index + 1, None, _label(before[index])))
        elif tag == "insert":
            for index in range(j1, j2):
                changes.append(StepChange("added", None, index + 1, _label(after[index])))

    # Same shape, different values: SequenceMatcher reports these as equal
    # because the signature ignores magnitudes, so compare aligned pairs too.
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            continue
        for offset in range(i2 - i1):
            old, new = before[i1 + offset], after[j1 + offset]
            fields = _field_changes(old, new)
            if fields:
                changes.append(
                    StepChange("changed", i1 + offset + 1, j1 + offset + 1, _label(new), fields)
                )

    changes.sort(key=lambda change: (change.after_index or change.before_index or 0))
    return StepDiff(tuple(changes), len(before), len(after))


def diff_projects(before: ScheduleProject, after: ScheduleProject) -> StepDiff:
    """Step-level impact of any project edit, expansion errors included."""
    before_steps, before_error = _safe_expand(before)
    after_steps, after_error = _safe_expand(after)
    if after_error:
        return StepDiff(
            (), len(before_steps), 0,
            note=f"이 값으로는 스케줄을 만들 수 없습니다 — {after_error}",
        )
    if before_error:
        return StepDiff(
            (), 0, len(after_steps),
            note=f"이전 상태를 펼칠 수 없어 비교를 건너뜁니다 — {before_error}",
        )
    return diff_steps(before_steps, after_steps)


def preview_module_change(
    project: ScheduleProject,
    module_id: str,
    params: dict[str, Any],
) -> StepDiff:
    """What changing one module's parameters would do, without applying it."""
    candidate = project.copy()
    for node in candidate.modules:
        if node.id == module_id:
            node.params = dict(params)
            break
    else:
        raise ValueError(f"Unknown module id: {module_id}")
    return diff_projects(project, candidate)


def _safe_expand(project: ScheduleProject) -> tuple[list[StepIntent], str]:
    try:
        return list(project.expand_steps()), ""
    except (TypeError, ValueError) as exc:
        return [], str(exc)


def _signature(step: StepIntent) -> str:
    return f"{step.step_type}/{step.mode or '-'}"


def _label(step: StepIntent) -> str:
    return step.label or f"{step.step_type}{f' {step.mode}' if step.mode else ''}"


def _field_changes(before: StepIntent, after: StepIntent) -> tuple[FieldChange, ...]:
    changes: list[FieldChange] = []
    for name in _COMPARED_FIELDS:
        old = getattr(before, name)
        new = getattr(after, name)
        if isinstance(old, float) and isinstance(new, float):
            if abs(old - new) <= 1e-9:
                continue
        elif old == new:
            continue
        changes.append(FieldChange(name, old, new))
    return tuple(changes)


def _render(field: str, value: Any) -> str:
    if value is None:
        return "없음"
    if field in {"c_rate", "cv_cutoff_c_rate"}:
        return units.format_c_rate(float(value))
    if field in {"current_mA", "cv_cutoff_mA"}:
        return units.format_current_mA(float(value))
    if field in {"voltage_v", "end_voltage_v"}:
        return units.format_voltage(float(value))
    if field == "end_time_s":
        return units.format_duration_ko(float(value))
    if field == "dod_percent":
        return units.format_percent(float(value))
    return str(value)


__all__ = [
    "FieldChange",
    "StepChange",
    "StepDiff",
    "diff_projects",
    "diff_steps",
    "preview_module_change",
]
