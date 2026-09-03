"""Internal write → read semantic round-trip validation (Gate C3)."""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..engine.compiler import compile_step_warnings
from ..engine.c_rate import current_mA_from_c_rate
from ..ir.project import ScheduleProject
from ..ir.step_intent import StepIntent
from ..io.reader import read_sch
from ..io.sch_binary import read_sch_binary
from ..io.sch_parser import parse_schedule_file
from ..io.writer import write_sch
from ..schema.ensol_v612 import (
    OFF_CURRENT_MA,
    OFF_CV_CUTOFF_MA,
    OFF_DOD_PERCENT,
    OFF_LOOP_COUNT,
    OFF_LOOP_GOTO_ENSOL,
    OFF_LOOP_GOTO_LEGACY,
    OFF_RECORD_TIME_S,
    OFF_TIME_OR_REST_S,
    OFF_VOLT_OR_VLIM_MV,
    OFF_VOLTAGE_CUTOFF_MV,
)


@dataclass(frozen=True, slots=True)
class RoundTripReport:
    output_path: Path
    passed: bool
    expected_step_count: int
    parsed_step_count: int
    mismatches: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "pne_scheduler.roundtrip_report/v1",
            "output_path": str(self.output_path),
            "passed": self.passed,
            "expected_step_count": self.expected_step_count,
            "parsed_step_count": self.parsed_step_count,
            "mismatches": list(self.mismatches),
            "warnings": list(self.warnings),
        }


def validate_written_project(project: ScheduleProject, output_path: Path) -> list[str]:
    """Backward-compatible wrapper returning mismatch/warning strings."""
    report = roundtrip_project(project, output_path)
    return [*report.mismatches, *report.warnings]


def roundtrip_project(project: ScheduleProject, output_path: Path) -> RoundTripReport:
    """Write a project and semantically re-read it with the native parser."""
    intents = list(project.expand_steps())
    if not intents or intents[-1].step_type != "end":
        intents = [*intents, StepIntent(step_type="end")]

    warnings = list(compile_step_warnings(intents))
    write_sch(project, output_path)
    return _compare_intents_to_file(intents, project, Path(output_path), warnings)


def roundtrip_intents(
    intents: list[StepIntent],
    *,
    cell,
    output_path: Path,
    schedule_name: str = "roundtrip",
) -> RoundTripReport:
    """Round-trip a flat intent list via a temporary ScheduleProject shell."""
    project = ScheduleProject(
        name=schedule_name,
        cell_profile=cell,
        sch_version=0x00010003,
        modules=[],
        connections=[],
    )
    # Bypass module expand: write compiled records directly through write_sch
    # by temporarily monkey-patching expand_steps.
    warnings = list(compile_step_warnings(intents))
    sealed = list(intents)
    if not sealed or sealed[-1].step_type != "end":
        sealed = [*sealed, StepIntent(step_type="end")]

    def _expand() -> list[StepIntent]:
        return list(sealed)

    project.expand_steps = _expand  # type: ignore[method-assign]
    write_sch(project, output_path)
    return _compare_intents_to_file(sealed, project, Path(output_path), warnings)


def _compare_intents_to_file(
    intents: list[StepIntent],
    project: ScheduleProject,
    output_path: Path,
    warnings: list[str],
) -> RoundTripReport:
    mismatches: list[str] = []
    try:
        doc = read_sch_binary(output_path)
        parsed = parse_schedule_file(output_path)
    except (OSError, ValueError) as exc:
        return RoundTripReport(
            output_path=output_path,
            passed=False,
            expected_step_count=len(intents),
            parsed_step_count=0,
            mismatches=(f"Re-parse failed: {exc}",),
            warnings=tuple(warnings),
        )

    if doc.sch_version != 0x00010003:
        mismatches.append(f"Expected version 0x00010003, got 0x{doc.sch_version:08x}")
    if doc.payload_offset != 1760 or doc.step_size != 612:
        mismatches.append(
            f"Unexpected framing payload={doc.payload_offset} step_size={doc.step_size}"
        )
    if doc.step_count != len(intents):
        mismatches.append(
            f"Step count mismatch: written intents={len(intents)}, parsed={doc.step_count}"
        )
    if len(parsed.steps) != len(intents):
        mismatches.append(
            f"Native parser step count mismatch: {len(parsed.steps)} vs {len(intents)}"
        )

    cell = project.cell_profile
    for intent, step in zip(intents, doc.steps):
        record = step.record
        prefix = f"Step {step.step_no}"
        if intent.step_type == "charge" and intent.voltage_v is not None:
            expected = float(intent.voltage_v) * 1000.0
            actual = struct.unpack_from("<f", record, OFF_VOLT_OR_VLIM_MV)[0]
            if not _close(actual, expected):
                mismatches.append(f"{prefix} voltage_mV: expected {expected}, got {actual}")
        if intent.step_type in {"charge", "discharge"}:
            if intent.current_mA is not None:
                expected_i = float(intent.current_mA)
            elif intent.c_rate is not None:
                expected_i = float(current_mA_from_c_rate(intent.c_rate, cell))
            else:
                expected_i = None
            if expected_i is not None:
                actual_i = struct.unpack_from("<f", record, OFF_CURRENT_MA)[0]
                if not _close(actual_i, expected_i):
                    mismatches.append(
                        f"{prefix} current_mA: expected {expected_i}, got {actual_i}"
                    )
        if intent.end_time_s is not None:
            actual_t = struct.unpack_from("<f", record, OFF_TIME_OR_REST_S)[0]
            if not _close(actual_t, float(intent.end_time_s)):
                mismatches.append(
                    f"{prefix} time_s: expected {intent.end_time_s}, got {actual_t}"
                )
        if intent.end_voltage_v is not None:
            expected_v = float(intent.end_voltage_v) * 1000.0
            actual_v = struct.unpack_from("<f", record, OFF_VOLTAGE_CUTOFF_MV)[0]
            if not _close(actual_v, expected_v):
                mismatches.append(
                    f"{prefix} end_voltage_mV: expected {expected_v}, got {actual_v}"
                )
        if intent.cv_cutoff_mA is not None or intent.cv_cutoff_c_rate is not None:
            expected_cv = (
                float(intent.cv_cutoff_mA)
                if intent.cv_cutoff_mA is not None
                else float(current_mA_from_c_rate(intent.cv_cutoff_c_rate, cell))
            )
            actual_cv = struct.unpack_from("<f", record, OFF_CV_CUTOFF_MA)[0]
            if not _close(actual_cv, expected_cv):
                mismatches.append(
                    f"{prefix} cv_cutoff_mA: expected {expected_cv}, got {actual_cv}"
                )
        if intent.record_time_s is not None:
            actual_rt = struct.unpack_from("<f", record, OFF_RECORD_TIME_S)[0]
            if not _close(actual_rt, float(intent.record_time_s)):
                mismatches.append(
                    f"{prefix} record_time_s: expected {intent.record_time_s}, got {actual_rt}"
                )
        if intent.dod_percent is not None:
            actual_dod = struct.unpack_from("<f", record, OFF_DOD_PERCENT)[0]
            if not _close(actual_dod, float(intent.dod_percent)):
                mismatches.append(
                    f"{prefix} dod_percent: expected {intent.dod_percent}, got {actual_dod}"
                )
        if intent.step_type == "loop":
            if intent.loop_count is not None:
                actual_count = struct.unpack_from("<I", record, OFF_LOOP_COUNT)[0]
                if actual_count != int(intent.loop_count):
                    mismatches.append(
                        f"{prefix} loop_count: expected {intent.loop_count}, got {actual_count}"
                    )
            if intent.loop_goto_step is not None:
                legacy = struct.unpack_from("<I", record, OFF_LOOP_GOTO_LEGACY)[0]
                ensol = struct.unpack_from("<I", record, OFF_LOOP_GOTO_ENSOL)[0]
                if legacy != int(intent.loop_goto_step) or ensol != int(intent.loop_goto_step):
                    mismatches.append(
                        f"{prefix} loop_goto: expected {intent.loop_goto_step} "
                        f"at @48/@564, got {legacy}/{ensol}"
                    )

    # Optional ASSB structural smoke (not required for C3 pass).
    try:
        assb_view = read_sch(output_path)
        if assb_view.step_count != len(intents):
            warnings.append(
                f"ASSB reader step_count={assb_view.step_count} "
                f"(native={len(intents)}); see Gate C4"
            )
    except (ImportError, ValueError) as exc:
        warnings.append(f"ASSB reader unavailable during C3: {exc}")

    return RoundTripReport(
        output_path=output_path,
        passed=not mismatches,
        expected_step_count=len(intents),
        parsed_step_count=doc.step_count,
        mismatches=tuple(mismatches),
        warnings=tuple(warnings),
    )


def _close(actual: float, expected: float, *, rel: float = 1e-5, abs_: float = 1e-3) -> bool:
    if math.isnan(actual) or math.isnan(expected):
        return False
    return math.isclose(actual, expected, rel_tol=rel, abs_tol=abs_)
