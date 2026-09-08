"""Structured, UI-independent schedule preflight validation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from ..engine.c_rate import current_mA_from_c_rate
from ..ir.equipment_profile import effective_current_limit_mA
from ..ir.project import ScheduleProject
from ..modules.catalog import get_module_spec

Severity = Literal["error", "warning"]
Purpose = Literal["preview", "experimental_build", "production"]


@dataclass(frozen=True, slots=True)
class PreflightIssue:
    code: str
    severity: Severity
    message: str
    object_id: str | None = None
    field: str | None = None
    evidence: str | None = None
    remediation: str | None = None


@dataclass(frozen=True, slots=True)
class PreflightResult:
    issues: tuple[PreflightIssue, ...]

    @property
    def errors(self) -> tuple[PreflightIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[PreflightIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def passed(self) -> bool:
        return not self.errors


def validate_project(
    project: ScheduleProject,
    *,
    purpose: Purpose = "preview",
) -> PreflightResult:
    issues: list[PreflightIssue] = []
    cell = project.cell_profile
    # The binding current limit is the smaller of the cell's own limit and the
    # target cycler's rating, so naming an under-rated unit is caught here and
    # not only at export time.
    current_limit_mA = effective_current_limit_mA(cell.max_current_mA, project.equipment)
    limit_source = "cell"
    if (
        project.equipment is not None
        and project.equipment.max_current_mA is not None
        and current_limit_mA == project.equipment.max_current_mA
    ):
        limit_source = project.equipment.unit
    for field_name, value in (
        ("nominal_capacity_mAh", cell.nominal_capacity_mAh),
        ("v_min", cell.v_min),
        ("v_max", cell.v_max),
    ):
        if not _finite(value):
            issues.append(_error("CELL_NONFINITE", f"{field_name} must be finite", field=field_name))
    if cell.max_current_mA is not None and (
        not _finite(cell.max_current_mA) or cell.max_current_mA <= 0
    ):
        issues.append(
            _error("CELL_MAX_CURRENT", "max_current_mA must be finite and positive", field="max_current_mA")
        )

    for node in project.modules:
        spec = get_module_spec(node.module_type)
        if spec is None:
            issues.append(_error("MODULE_UNCATALOGED", f"No catalog metadata for {node.module_type!r}", object_id=node.id))
            continue
        if spec.internal_only:
            issues.append(
                _warning("MODULE_INTERNAL", f"{spec.title} is an internal validation module", object_id=node.id)
            )
        if spec.trust_status in {"prototype", "software-checked"}:
            severity: Severity = "error" if purpose == "production" else "warning"
            issues.append(
                PreflightIssue(
                    "MODULE_TRUST",
                    severity,
                    f"{spec.title} status is {spec.trust_status}",
                    object_id=node.id,
                    evidence="modules/catalog.py",
                    remediation="Complete CTSPro reopen/equipment validation for this exact recipe and hash.",
                )
            )
        for limitation in spec.limitations:
            issues.append(_warning("MODULE_LIMITATION", limitation, object_id=node.id))

    try:
        steps = project.expand_steps()
    except (TypeError, ValueError) as exc:
        issues.append(_error("COMPOSE_FAILED", str(exc)))
        return PreflightResult(tuple(issues))

    if len(steps) == 1 and steps[0].step_type == "end":
        issues.append(_error("EMPTY_SCHEDULE", "Schedule has no executable steps"))
    end_positions = [index for index, step in enumerate(steps, start=1) if step.step_type == "end"]
    if end_positions != [len(steps)]:
        issues.append(_error("END_CONTRACT", "Schedule must contain exactly one final END"))

    for index, step in enumerate(steps, start=1):
        object_id = f"step:{index}"
        for field_name in (
            "c_rate", "cv_cutoff_c_rate", "current_mA", "cv_cutoff_mA",
            "voltage_v", "end_voltage_v", "end_time_s", "dod_percent",
        ):
            value = getattr(step, field_name)
            if value is not None and not _finite(value):
                issues.append(_error("STEP_NONFINITE", f"{field_name} must be finite", object_id=object_id, field=field_name))
        if step.step_type in {"charge", "discharge"} and step.c_rate is None and step.current_mA is None:
            issues.append(_error("CURRENT_REQUIRED", "Charge/discharge requires C-rate or current", object_id=object_id))
        if step.c_rate is not None and step.c_rate <= 0:
            issues.append(_error("C_RATE_RANGE", "C-rate must be positive", object_id=object_id, field="c_rate"))
        if step.current_mA is not None and step.current_mA <= 0:
            issues.append(_error("CURRENT_RANGE", "Current must be positive", object_id=object_id, field="current_mA"))
        if step.cv_cutoff_c_rate is not None and step.cv_cutoff_c_rate <= 0:
            issues.append(_error("CV_CUTOFF_RANGE", "CV cutoff C-rate must be positive", object_id=object_id, field="cv_cutoff_c_rate"))
        if step.cv_cutoff_mA is not None and step.cv_cutoff_mA <= 0:
            issues.append(_error("CV_CUTOFF_RANGE", "CV cutoff current must be positive", object_id=object_id, field="cv_cutoff_mA"))
        if step.end_time_s is not None and step.end_time_s <= 0:
            issues.append(_error("TIME_RANGE", "End time must be positive", object_id=object_id, field="end_time_s"))
        if step.dod_percent is not None and not (0 < step.dod_percent <= 100):
            issues.append(_error("DOD_RANGE", "DOD/SOC percent must be in (0, 100]", object_id=object_id, field="dod_percent"))
        if step.end_capacity_fraction is not None and not (0 < step.end_capacity_fraction <= 1):
            issues.append(_error("CAPACITY_FRACTION_RANGE", "Capacity fraction must be in (0, 1]", object_id=object_id, field="end_capacity_fraction"))
        if step.end_voltage_v is not None and not (cell.v_min <= step.end_voltage_v <= cell.v_max):
            issues.append(_error("END_VOLTAGE_RANGE", "End voltage is outside the cell window", object_id=object_id, field="end_voltage_v"))
        if step.voltage_v is not None and step.voltage_v < cell.v_min:
            if (
                step.step_type == "discharge"
                and step.end_voltage_v is not None
                and step.end_voltage_v >= cell.v_min
                and step.voltage_v > 0
            ):
                issues.append(
                    PreflightIssue(
                        "DISCHARGE_VLIM_HEADROOM",
                        "warning",
                        "Discharge mode limit is below v_min; the end-voltage cutoff remains in range",
                        object_id,
                        "voltage_v",
                    )
                )
            else:
                issues.append(
                    _error(
                        "VOLTAGE_RANGE",
                        "Voltage limit is below the cell v_min",
                        object_id=object_id,
                        field="voltage_v",
                    )
                )
        if step.voltage_v is not None and step.voltage_v > cell.v_max:
            cc_source_limit = (
                step.step_type == "charge"
                and step.mode == "CC"
                and step.end_voltage_v is not None
                and step.end_voltage_v <= cell.v_max
                and step.voltage_v <= 5.0 + 1e-9
            )
            severity = (
                "warning"
                if cc_source_limit or step.voltage_v <= cell.v_max + 0.1 + 1e-9
                else "error"
            )
            issues.append(PreflightIssue("VOLTAGE_HEADROOM", severity, "Charge voltage limit exceeds cell v_max", object_id, "voltage_v"))
        if (
            current_limit_mA is not None
            and step.step_type in {"charge", "discharge"}
            and (step.current_mA is not None or step.c_rate is not None)
        ):
            current = (
                abs(step.current_mA)
                if step.current_mA is not None
                else abs(current_mA_from_c_rate(step.c_rate, cell))
            )
            if current > current_limit_mA + 1e-6:
                issues.append(
                    _error(
                        "CURRENT_LIMIT",
                        f"{current:g} mA exceeds the {limit_source} limit "
                        f"{current_limit_mA:g} mA",
                        object_id=object_id,
                        field="current_mA",
                    )
                )
        if step.step_type == "loop":
            if step.loop_goto_step is None or step.loop_count is None:
                issues.append(_error("LOOP_REQUIRED", "LOOP requires target and count", object_id=object_id))
            elif step.loop_goto_step < 1 or step.loop_goto_step >= index or step.loop_count < 1:
                issues.append(_error("LOOP_RANGE", "LOOP must target an earlier step and use count >= 1", object_id=object_id))
        if step.end_capacity_fraction is not None:
            severity = "error" if purpose == "production" else "warning"
            issues.append(PreflightIssue("FENDC_UNVERIFIED", severity, "Capacity cutoff fEndC@36 is not controlled-pair verified", object_id, "end_capacity_fraction", "planning/PATTERN_VALIDATION_PLAN.md"))
        if step.dod_percent is not None:
            severity = "error" if purpose == "production" else "warning"
            issues.append(
                PreflightIssue(
                    "DOD_UNVERIFIED",
                    severity,
                    "DOD/SOC cutoff @384 is not controlled-pair verified",
                    object_id,
                    "dod_percent",
                    "planning/PATTERN_VALIDATION_PLAN.md",
                )
            )
        if step.dcr_start_s is not None or step.dcr_end_s is not None:
            severity = "error" if purpose == "production" else "warning"
            issues.append(PreflightIssue("DCR_IR_ONLY", severity, "DCR window is IR-only and is not written", object_id, "dcr_start_s"))

    return PreflightResult(tuple(_dedupe(issues)))


def _finite(value: float) -> bool:
    return math.isfinite(float(value))


def _error(code: str, message: str, *, object_id: str | None = None, field: str | None = None) -> PreflightIssue:
    return PreflightIssue(code, "error", message, object_id, field)


def _warning(code: str, message: str, *, object_id: str | None = None) -> PreflightIssue:
    return PreflightIssue(code, "warning", message, object_id)


def _dedupe(issues: list[PreflightIssue]) -> list[PreflightIssue]:
    seen: set[tuple[str, str, str | None, str | None]] = set()
    result: list[PreflightIssue] = []
    for issue in issues:
        key = (issue.code, issue.message, issue.object_id, issue.field)
        if key not in seen:
            seen.add(key)
            result.append(issue)
    return result
