"""Read-only values computed from a module's inputs.

Users ask "so what current is that actually, and how long will it run?" — the
answers are derived, never typed, so they belong next to the form as
non-editable rows rather than as fields somebody could contradict.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
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
        if not estimate.is_complete:
            text += f" (부분 합계 · {estimate.unknown_step_count}스텝 시간 미정)"
        elif not estimate.is_exact:
            text += " (근사)"
        values.append(
            DerivedValue(
                "예상 소요 시간", text,
                help="용량÷C-rate의 근사와 휴지 시간을 합산합니다. 전압·DOD만으로 알 수 없는 스텝은 포함하지 않습니다. CV 감쇠와 장비 지연은 별도이며, 안전 시간 제한은 실제 예정 시간이 아닙니다.",
            )
        )

    if estimate.upper_bound_seconds is not None and not estimate.is_exact:
        values.append(DerivedValue("시간 제한 합계", units.format_duration_ko(estimate.upper_bound_seconds),
                                   help="모든 스텝이 설정된 최대 시간까지 진행했을 때의 제한 합계입니다. 실제 소요 시간이 아니며 기존 LOOP 실행 횟수 해석을 따릅니다."))
    if module_type == "qpeed" and params.get("variant") == "full":
        start = float(params.get("high_rate_start_c", 1.5))
        gap = float(params.get("high_rate_step_c", 1.5))
        levels = int(params.get("high_rate_levels", 12))
        top = start + gap * (levels - 1)
        values.append(DerivedValue("최대 고율 충전율", f"{top:g}C = {units.format_current_mA(top * cell.nominal_capacity_mAh)}",
                                   help=f"{start:g}C + {gap:g}C × ({levels}단계 − 1). 최고 전류 항목은 컨디셔닝까지 포함한 실제 스텝의 최대값입니다."))
    if module_type == "qpeed" and params.get("soc_voltage_source"):
        try:
            source = json.loads(params["soc_voltage_source"])
            source_text = f"{source['fileName']} · 셀 {source['cellId'] or '미지정'} · 스텝 {source['step'] or '미지정'} · {source['row']}행"
            if source.get("socPercent") is not None:
                source_text += f" · SOC {source['socPercent']:g}% ({source['socBasis']})"
        except (ValueError, TypeError, KeyError):
            source_text = "저장된 데이터 출처를 확인하세요."
        values.append(DerivedValue("SOC 전압 출처", source_text, help="불러온 전압은 사용자가 선택한 데이터 행입니다. 셀·온도·SOC 대응을 확인하세요."))

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
