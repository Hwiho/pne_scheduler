"""Editing the individual steps of a detached module.

`detach_module` freezes a preset into `custom_steps` so an advanced user can
change one step without pretending the golden topology still holds.  Until now
that was where the road ended: the steps existed as verbatim dicts and nothing
could insert, remove, reorder or retype one.

These functions close that gap and are the only place that writes into a
`custom_steps` step list.  They are pure — each takes the current step dicts and
returns new ones — so the caller decides when a change becomes an undo entry, and
a preview costs nothing.

Two invariants are enforced here rather than left to the writer:

* the list never becomes empty — an empty module would silently vanish from the
  procedure while still occupying a row;
* END stays last if it is present at all, matching `CustomStepsModule.validate`
  and the composer's single-terminal-END rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..ir.step_intent import StepIntent
from ..modules.primitive import PRIMITIVE_KINDS, PrimitiveModule
from ..spec import units

# StepIntent field -> the unit its value is typed and displayed in.
STEP_FIELD_KINDS: dict[str, str] = {
    "c_rate": "c_rate",
    "cv_cutoff_c_rate": "c_rate",
    "voltage_v": "voltage_v",
    "end_voltage_v": "voltage_v",
    "end_time_s": "duration_s",
    "dod_percent": "percent",
    "end_capacity_fraction": "fraction",
    "record_time_s": "duration_s",
    "loop_count": "count",
    "label": "text",
}

STEP_FIELD_LABELS_KO: dict[str, str] = {
    "c_rate": "전류",
    "cv_cutoff_c_rate": "정전압 종료 전류",
    "voltage_v": "목표 전압",
    "end_voltage_v": "종료 전압",
    "end_time_s": "시간",
    "dod_percent": "DOD",
    "end_capacity_fraction": "용량 기준 종료",
    "record_time_s": "기록 간격",
    "loop_count": "반복 횟수",
    "label": "설명",
}


# What the "add a step" control offers, in the order it offers them.
PRIMITIVE_STEP_CHOICES: tuple[tuple[str, str], ...] = tuple(
    (kind, title) for kind, (_type, _mode, title) in PRIMITIVE_KINDS.items()
)


class StepEditError(ValueError):
    """A step edit that would leave the module in a state it must never hold."""


@dataclass(frozen=True, slots=True)
class StepFieldView:
    key: str
    label: str
    kind: str
    text: str
    detail: str = ""


def _as_intent(raw: dict[str, Any]) -> StepIntent:
    return StepIntent.from_dict(dict(raw))


def _check(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not steps:
        raise StepEditError("스텝을 모두 지울 수는 없습니다. 구간 자체를 삭제하세요.")
    ends = [i for i, step in enumerate(steps) if step.get("step_type") == "end"]
    if ends and ends != [len(steps) - 1]:
        raise StepEditError("END 는 마지막 스텝에만 올 수 있습니다.")
    return steps


def _bounds(steps: list[dict[str, Any]], index: int) -> None:
    if not 0 <= index < len(steps):
        raise StepEditError(f"스텝 번호가 범위를 벗어납니다 (1–{len(steps)}).")


def insert_step(
    steps: list[dict[str, Any]], index: int, kind: str
) -> list[dict[str, Any]]:
    """Insert a primitive-shaped step at ``index`` (0-based, may equal len)."""
    if kind not in PRIMITIVE_KINDS:
        raise StepEditError(f"알 수 없는 스텝 종류입니다: {kind}")
    if not 0 <= index <= len(steps):
        raise StepEditError(f"삽입 위치가 범위를 벗어납니다 (1–{len(steps) + 1}).")
    # Built from the same definition the palette uses, so a step inserted here
    # and one added as its own module start identical.
    fresh = PrimitiveModule(kind=kind).build_step().to_dict()
    updated = list(steps)
    updated.insert(index, fresh)
    return _check(updated)


def remove_step(steps: list[dict[str, Any]], index: int) -> list[dict[str, Any]]:
    _bounds(steps, index)
    updated = list(steps)
    updated.pop(index)
    return _check(updated)


def move_step(
    steps: list[dict[str, Any]], index: int, delta: int
) -> list[dict[str, Any]]:
    _bounds(steps, index)
    target = index + delta
    if not 0 <= target < len(steps):
        return list(steps)
    updated = list(steps)
    updated.insert(target, updated.pop(index))
    return _check(updated)


def set_step_field(
    steps: list[dict[str, Any]], index: int, key: str, text: Any
) -> list[dict[str, Any]]:
    """Retype one field of one step, parsing it in the unit it is shown in."""
    _bounds(steps, index)
    if key not in STEP_FIELD_KINDS:
        raise StepEditError(f"이 항목은 직접 고칠 수 없습니다: {key}")

    kind = STEP_FIELD_KINDS[key]
    raw = "" if text is None else str(text).strip()
    if raw == "" and kind != "text":
        value: Any = None
    else:
        try:
            value = _parse(kind, raw)
        except ValueError as exc:
            raise StepEditError(str(exc)) from exc

    updated = list(steps)
    step = dict(updated[index])
    if value is None:
        step.pop(key, None)
    else:
        step[key] = value
    updated[index] = step
    return _check(updated)


def _parse(kind: str, raw: str) -> Any:
    if kind == "text":
        return raw
    if kind == "c_rate":
        return units.parse_c_rate(raw)
    if kind == "voltage_v":
        return units.parse_voltage(raw)
    if kind == "duration_s":
        return units.parse_duration_s(raw)
    if kind == "percent":
        return units.parse_percent(raw)
    if kind == "fraction":
        return units.parse_percent(raw) / 100.0
    if kind == "count":
        return int(units.parse_number(raw))
    raise ValueError(f"알 수 없는 단위입니다: {kind}")


def step_fields(
    raw: dict[str, Any], *, nominal_capacity_mAh: float
) -> tuple[StepFieldView, ...]:
    """The editable fields of one step, formatted with their derived readings."""
    intent = _as_intent(raw)
    views: list[StepFieldView] = []
    for key, kind in STEP_FIELD_KINDS.items():
        value = getattr(intent, key, None)
        if value is None or value == "":
            continue
        views.append(
            StepFieldView(
                key=key,
                label=STEP_FIELD_LABELS_KO[key],
                kind=kind,
                text=_format(kind, value),
                detail=_detail(kind, value, nominal_capacity_mAh),
            )
        )
    return tuple(views)


def _format(kind: str, value: Any) -> str:
    if kind == "c_rate":
        return units.format_c_rate(float(value))
    if kind == "voltage_v":
        return units.format_voltage(float(value))
    if kind == "duration_s":
        return units.format_duration_input(float(value))
    if kind == "percent":
        return units.format_percent(float(value))
    if kind == "fraction":
        return units.format_percent(float(value) * 100.0)
    if kind == "count":
        return units.format_count(float(value))
    return str(value)


def _detail(kind: str, value: Any, capacity: float) -> str:
    """The same value in the other unit a lab user thinks in."""
    if kind == "c_rate" and capacity:
        return units.format_current_mA(float(value) * capacity)
    if kind == "duration_s":
        return units.format_duration_ko(float(value))
    if kind == "fraction":
        return f"SOC {units.format_fraction_as_soc(float(value))}"
    return ""


__all__ = [
    "PRIMITIVE_STEP_CHOICES",
    "STEP_FIELD_KINDS",
    "STEP_FIELD_LABELS_KO",
    "StepEditError",
    "StepFieldView",
    "insert_step",
    "move_step",
    "remove_step",
    "set_step_field",
    "step_fields",
]
