"""Plain-language Korean summary of what a schedule will actually do.

A reviewer should be able to tell whether a schedule is right without reading
167 rows of a step table.  These sentences are generated from the same
expansion the writer uses, so they cannot drift from the file.
"""

from __future__ import annotations

from typing import Any

from dataclasses import dataclass
from datetime import datetime, timedelta

from ..engine.c_rate import current_mA_from_c_rate
from ..ir.cell_profile import CellProfile
from ..ir.project import ModuleNode, ScheduleProject
from ..spec import units

_WEEKDAYS_KO = ("월", "화", "수", "목", "금", "토", "일")


@dataclass(frozen=True, slots=True)
class ProjectSummary:
    headline: str
    cell_line: str
    equipment_line: str
    phase_lines: tuple[str, ...]
    duration_text: str
    finish_text: str
    total_steps: int
    warnings: tuple[str, ...] = ()

    def as_text(self) -> str:
        lines = [self.headline, "", self.cell_line, self.equipment_line, ""]
        lines.extend(self.phase_lines)
        lines.extend(["", f"총 {self.total_steps} 스텝 · 예상 {self.duration_text}"])
        if self.finish_text:
            lines.append(self.finish_text)
        if self.warnings:
            lines.append("")
            lines.extend(f"※ {warning}" for warning in self.warnings)
        return "\n".join(lines)


def module_headline(node: ModuleNode, cell: CellProfile) -> str:
    """One phrase describing a phase, in the words a lab user would use."""
    params = _resolved(node)
    module_type = node.module_type

    def rate(key: str, fallback: float = 0.0) -> str:
        value = float(params.get(key, fallback) or 0.0)
        if value <= 0:
            return "—"
        return units.format_c_rate(value)

    def seconds(key: str) -> str:
        return units.format_duration_ko(float(params.get(key, 0.0) or 0.0))

    if module_type == "formation":
        return f"{rate('charge_c_rate')} 충방전 {int(params.get('cycle_count', 0))}회"
    if module_type == "rest":
        return f"{seconds('duration_s')} 휴지"
    if module_type in {"cycle_life", "insitu_cycle"}:
        suffix = " (RPT 없음)" if module_type == "insitu_cycle" else ""
        return f"{rate('charge_c_rate')} 충전 / {rate('discharge_c_rate')} 방전 × {int(params.get('loop_count', 0)):,} 사이클{suffix}"
    if module_type == "capacheck":
        cycles = int(params.get("measurement_cycles", 1))
        return f"{rate('initial_c_rate')} 확인 후 {rate('measurement_c_rate')} 측정 {cycles}회"
    if module_type == "rpt":
        socs = _soc_text(params.get("soc_fractions"))
        if not params.get("include_dcir_pulses", True):
            return f"{rate('reference_c_rate')} 기준 방전 · SOC {socs} (펄스 없음)"
        return f"{rate('reference_c_rate')} 기준 · SOC {socs} 에서 {rate('dcir_pulse_c_rate')} DC-IR"
    if module_type == "dcir":
        return f"SOC {_soc_text(params.get('soc_fractions'))} 에서 {rate('pulse_c_rate')} {seconds('pulse_s')} 펄스"
    if module_type == "hppc":
        if params.get("variant") == "full":
            return f"전 구간 HPPC · 기준 {rate('reference_c_rate')} · 펄스 {rate('full_pulse_c_rate')}"
        return f"SOC {_soc_text(params.get('soc_fractions'))} 펄스 (구버전)"
    if module_type == "qpeed":
        variant = params.get("variant")
        if variant == "full":
            start = float(params.get("high_rate_start_c", 0.0))
            stepping = float(params.get("high_rate_step_c", 0.0))
            levels = int(params.get("high_rate_levels", 0))
            top = start + stepping * max(levels - 1, 0)
            current = current_mA_from_c_rate(top, cell) if top > 0 else 0.0
            return (
                f"{units.format_c_rate(start)} → {units.format_c_rate(top)} "
                f"({units.format_current_mA(current)}) {levels}단계 고율 충전"
            )
        if variant == "soc_setting":
            return f"{float(params.get('soc_voltage_v', 0.0)):.3f} V SOC 설정 · DOD {params.get('soc_dod_percent')}%"
        return f"SOC {_soc_text(params.get('soc_fractions'))} 펄스 (구버전)"
    if module_type == "qc":
        rates = params.get("fast_rates_c") or []
        chain = " → ".join(units.format_c_rate(float(value)) for value in rates)
        label = {"cycle": "QC 사이클", "1n1q": "1N1Q", "1_charge": "1 charge"}.get(
            str(params.get("variant")), "QC"
        )
        return f"{label} · {chain} 다단 급속충전" if chain else label
    if module_type == "custom_steps":
        origin = params.get("source_module_type") or "프리셋"
        return f"{origin} 에서 분리한 {len(params.get('steps') or [])} 스텝 (직접 편집)"
    return module_type


def summarize_project(
    project: ScheduleProject,
    *,
    start: datetime | None = None,
    procedure: Any = None,
) -> ProjectSummary:
    """``procedure`` lets a caller that already built one avoid a second pass.

    Expanding a 2400-step schedule twice to render one screen was most of the
    cost of that screen.
    """
    from ..ir.equipment_profile import effective_current_limit_mA
    from ..ir.procedure import build_procedure

    cell = project.cell_profile
    if procedure is None:
        procedure = build_procedure(project)
    limit = effective_current_limit_mA(cell.max_current_mA, project.equipment)

    cell_line = (
        f"셀: {cell.nominal_capacity_mAh:g} mAh · "
        f"{units.format_voltage(cell.v_min)} ~ {units.format_voltage(cell.v_max)}"
        f" · 1C = {units.format_current_mA(cell.nominal_capacity_mAh)}"
    )
    if project.equipment:
        equipment_line = f"장비: {project.equipment.describe()}"
        missing = project.equipment.missing_fields()
        if missing:
            equipment_line += f" · 미지정: {', '.join(missing)}"
    else:
        equipment_line = "장비: 지정되지 않음 — 설정 탭에서 PNE 장비를 선택하세요."

    phase_lines: list[str] = []
    for phase in procedure.phases:
        if phase.error:
            phase_lines.append(f"{phase.position}. {phase.title} — 확장 실패: {phase.error}")
            continue
        duration = (
            units.format_duration_ko(phase.duration_seconds)
            if phase.duration_seconds
            else "시간 미정"
        )
        subtitle = f" — {phase.subtitle}" if phase.subtitle else ""
        phase_lines.append(
            f"{phase.position}. {phase.title}{subtitle} "
            f"[{phase.step_range_text} 스텝 · {duration}]"
        )
    if not phase_lines:
        phase_lines.append("아직 실험이 없습니다. 프로토콜 탭에서 실험 목적을 고르세요.")

    duration_text = (
        units.format_duration_ko(procedure.duration_seconds)
        if procedure.duration_seconds
        else "미정"
    )
    if procedure.duration_seconds and not procedure.duration_exact:
        duration_text += " (근사)"
    finish_text = ""
    if procedure.duration_seconds:
        finish_text = "지금 시작하면 " + _finish_label(
            (start or datetime.now()) + timedelta(seconds=procedure.duration_seconds)
        ) + " 종료 예정"

    warnings: list[str] = []
    peak = _peak_current(procedure.steps, cell)
    if peak and limit and peak > limit + 1e-6:
        warnings.append(
            f"최고 전류 {units.format_current_mA(peak)} 가 한계 "
            f"{units.format_current_mA(limit)} 를 넘습니다."
        )
    if procedure.errors:
        warnings.extend(procedure.errors)

    headline = (
        f"{project.name} · {len(procedure.phases)}개 구간 · "
        f"{procedure.total_steps} 스텝 · 예상 {duration_text}"
    )
    return ProjectSummary(
        headline=headline,
        cell_line=cell_line,
        equipment_line=equipment_line,
        phase_lines=tuple(phase_lines),
        duration_text=duration_text,
        finish_text=finish_text,
        total_steps=procedure.total_steps,
        warnings=tuple(warnings),
    )


def summary_text(project: ScheduleProject) -> str:
    return summarize_project(project).as_text()


def _resolved(node: ModuleNode) -> dict:
    from ..spec.form import resolve_params

    try:
        return resolve_params(node.module_type, node.params)
    except (TypeError, ValueError):
        return dict(node.params)


def _soc_text(fractions) -> str:
    values = list(fractions or [])
    if not values:
        return "—"
    return "/".join(f"{float(value) * 100:.0f}%" for value in values)


def _peak_current(steps, cell: CellProfile) -> float | None:
    best: float | None = None
    for step in steps:
        if step.step_type not in {"charge", "discharge"}:
            continue
        if step.current_mA is not None:
            current = abs(float(step.current_mA))
        elif step.c_rate is not None:
            current = abs(float(step.c_rate)) * cell.nominal_capacity_mAh
        else:
            continue
        best = current if best is None else max(best, current)
    return best


def _finish_label(moment: datetime) -> str:
    weekday = _WEEKDAYS_KO[moment.weekday()]
    hour = moment.hour
    meridiem = "오전" if hour < 12 else "오후"
    display_hour = hour if 1 <= hour <= 12 else (12 if hour % 12 == 0 else hour % 12)
    return f"{moment.month}월 {moment.day}일({weekday}) {meridiem} {display_hour}시 {moment.minute:02d}분"


__all__ = ["ProjectSummary", "module_headline", "summarize_project", "summary_text"]
