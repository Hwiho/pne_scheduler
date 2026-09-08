"""Read-only values computed from a module's inputs.

Users ask "so what current is that actually, and how long will it run?" — the
answers are derived, never typed, so they belong next to the form as
non-editable rows rather than as fields somebody could contradict.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ..engine.duration import estimate_steps_duration
from ..ir.cell_profile import CellProfile
from ..ir.composer import compose_module_steps
from ..ir.project import ModuleNode
from . import units

Severity = Literal["info", "warning", "error"]


@dataclass(frozen=True, slots=True)
class DerivedValue:
    label: str
    text: str
    severity: Severity = "info"
    help: str = ""


def module_derived_values(
    module_type: str,
    params: dict[str, Any],
    *,
    cell: CellProfile,
    current_limit_mA: float | None = None,
) -> tuple[DerivedValue, ...]:
    """Step count, duration, and peak current for the current inputs."""
    try:
        steps = compose_module_steps(
            [ModuleNode("preview", module_type, dict(params))], cell, append_end=False
        )
    except (TypeError, ValueError) as exc:
        return (
            DerivedValue(
                "미리보기", f"현재 값으로는 스텝을 만들 수 없습니다 — {exc}", "error"
            ),
        )

    values: list[DerivedValue] = [
        DerivedValue("스텝 수", f"{len(steps)} 스텝", help="이 모듈이 만드는 장비 스텝 개수입니다."),
    ]

    estimate = estimate_steps_duration(steps)
    if estimate.estimated_seconds > 0:
        text = units.format_duration_ko(estimate.estimated_seconds)
        if not estimate.is_exact:
            text += " (근사)"
        values.append(
            DerivedValue(
                "예상 소요 시간", text,
                help="시간 종료 조건만으로 계산한 값입니다. 전압/용량 종료 조건은 더 짧게 끝날 수 있습니다.",
            )
        )

    peak = _peak_current(steps, cell)
    if peak is not None:
        rate, current = peak
        text = f"{units.format_c_rate(rate)} = {units.format_current_mA(current)}"
        severity: Severity = "info"
        if current_limit_mA:
            ratio = current / current_limit_mA
            text += f" · 장비 한계 {units.format_current_mA(current_limit_mA)}의 {ratio * 100:.0f}%"
            if ratio > 1.0 + 1e-9:
                severity = "error"
            elif ratio > 0.9:
                severity = "warning"
        values.append(
            DerivedValue(
                "최고 전류", text, severity,
                help="이 모듈에서 가장 큰 충·방전 전류입니다. 장비 정격을 넘으면 내보낼 수 없습니다.",
            )
        )

    loops = [step.loop_count for step in steps if step.step_type == "loop" and step.loop_count]
    if loops:
        values.append(
            DerivedValue("반복 스텝", f"{len(loops)}개 · 최대 {max(loops):,}회")
        )
    return tuple(values)


def _peak_current(steps, cell: CellProfile) -> tuple[float, float] | None:
    best: tuple[float, float] | None = None
    for step in steps:
        if step.step_type not in {"charge", "discharge"}:
            continue
        if step.current_mA is not None:
            current = abs(float(step.current_mA))
            rate = current / cell.nominal_capacity_mAh
        elif step.c_rate is not None:
            rate = abs(float(step.c_rate))
            current = rate * cell.nominal_capacity_mAh
        else:
            continue
        if best is None or current > best[1]:
            best = (rate, current)
    return best


__all__ = ["DerivedValue", "module_derived_values"]
