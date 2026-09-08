"""Gate D P0 — module validate → expand → compile → parse → semantic compare."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..engine.compiler import compile_step_warnings, compile_steps
from ..ir.cell_profile import CellProfile
from ..ir.project import ModuleNode, ScheduleProject
from ..io.sch_binary import read_sch_binary
from ..io.sch_parser import parse_schedule_file
from ..ir.composer import compose_module_steps
from ..modules.base import get_module_class
from ..schema.ensol_v612 import (
    OFF_CURRENT_MA,
    OFF_LOOP_COUNT,
    OFF_LOOP_GOTO_ENSOL,
    OFF_LOOP_GOTO_LEGACY,
    OFF_TIME_OR_REST_S,
    OFF_VOLT_OR_VLIM_MV,
    OFF_VOLTAGE_CUTOFF_MV,
)
from .roundtrip import RoundTripReport, roundtrip_project


@dataclass(frozen=True, slots=True)
class GateDModuleReport:
    module_type: str
    passed: bool
    topology: tuple[str, ...]
    step_count: int
    mismatches: tuple[str, ...]
    warnings: tuple[str, ...]
    roundtrip: RoundTripReport | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "pne_scheduler.gate_d_module_report/v1",
            "module_type": self.module_type,
            "passed": self.passed,
            "topology": list(self.topology),
            "step_count": self.step_count,
            "mismatches": list(self.mismatches),
            "warnings": list(self.warnings),
            "roundtrip": None if self.roundtrip is None else self.roundtrip.to_dict(),
        }


def run_module_pipeline(
    module_type: str,
    *,
    cell: CellProfile,
    output_path: Path,
    params: dict[str, Any] | None = None,
    schedule_name: str | None = None,
) -> GateDModuleReport:
    """Validate → expand → write → re-parse; compare topology and key fields."""
    cls = get_module_class(module_type)
    if cls is None:
        return GateDModuleReport(
            module_type=module_type,
            passed=False,
            topology=(),
            step_count=0,
            mismatches=(f"Unknown module type: {module_type!r}",),
            warnings=(),
        )

    node = ModuleNode(id=f"{module_type}_1", module_type=module_type, params=dict(params or {}))
    try:
        intents = compose_module_steps([node], cell)
    except ValueError as exc:
        return GateDModuleReport(
            module_type=module_type,
            passed=False,
            topology=(),
            step_count=0,
            mismatches=(str(exc),),
            warnings=(),
        )

    topology = tuple(intent.step_type for intent in intents)
    warnings = list(compile_step_warnings(intents))
    mismatches: list[str] = []

    records = compile_steps(intents, cell)
    for index, (intent, record) in enumerate(zip(intents, records), start=1):
        if intent.end_time_s is not None:
            packed_t = struct.unpack_from("<f", record, OFF_TIME_OR_REST_S)[0]
            if abs(packed_t - float(intent.end_time_s)) > 1e-3:
                mismatches.append(
                    f"Step {index}: compile time_s {packed_t} != {intent.end_time_s}"
                )
        if intent.step_type == "charge" and intent.voltage_v is not None:
            packed_v = struct.unpack_from("<f", record, OFF_VOLT_OR_VLIM_MV)[0]
            expected_v = float(intent.voltage_v) * 1000.0
            if abs(packed_v - expected_v) > 1e-3:
                mismatches.append(
                    f"Step {index}: compile charge voltage_mV {packed_v} != {expected_v}"
                )
        if intent.step_type == "discharge" and intent.end_voltage_v is not None:
            packed_v = struct.unpack_from("<f", record, OFF_VOLTAGE_CUTOFF_MV)[0]
            expected_v = float(intent.end_voltage_v) * 1000.0
            if abs(packed_v - expected_v) > 1e-3:
                mismatches.append(
                    f"Step {index}: compile end_voltage_mV {packed_v} != {expected_v}"
                )
        if intent.step_type in {"charge", "discharge"} and (
            intent.current_mA is not None or intent.c_rate is not None
        ):
            packed_i = struct.unpack_from("<f", record, OFF_CURRENT_MA)[0]
            if packed_i == 0.0:
                mismatches.append(f"Step {index}: expected nonzero current_mA, got 0")
        if intent.step_type == "loop":
            if intent.loop_count is not None:
                packed_count = struct.unpack_from("<I", record, OFF_LOOP_COUNT)[0]
                if packed_count != int(intent.loop_count):
                    mismatches.append(
                        f"Step {index}: compile loop_count {packed_count} != {intent.loop_count}"
                    )
            if intent.loop_goto_step is not None:
                legacy = struct.unpack_from("<I", record, OFF_LOOP_GOTO_LEGACY)[0]
                ensol = struct.unpack_from("<I", record, OFF_LOOP_GOTO_ENSOL)[0]
                if legacy != int(intent.loop_goto_step) or ensol != int(intent.loop_goto_step):
                    mismatches.append(
                        f"Step {index}: compile loop_goto {legacy}/{ensol} != "
                        f"{intent.loop_goto_step}"
                    )

    project = ScheduleProject(
        name=schedule_name or f"gate_d_{module_type}",
        cell_profile=cell,
        modules=[node],
        connections=[],
    )
    roundtrip = roundtrip_project(project, output_path)

    parsed = parse_schedule_file(output_path)
    binary = read_sch_binary(output_path)
    if len(parsed.steps) != len(intents):
        mismatches.append(
            f"Parser step count {len(parsed.steps)} != intents {len(intents)}"
        )
    if binary.step_count != len(intents):
        mismatches.append(
            f"Binary step count {binary.step_count} != intents {len(intents)}"
        )

    for intent, step in zip(intents, binary.steps):
        written = struct.unpack_from("<i", step.record, 8)[0] & 0xFFFF
        expected = struct.unpack_from("<i", compile_steps([intent], cell)[0], 8)[0] & 0xFFFF
        if written != expected:
            mismatches.append(
                f"Step {step.step_no}: type code {written:#x} != expected {expected:#x}"
            )

    all_mismatches = [*mismatches, *roundtrip.mismatches]
    return GateDModuleReport(
        module_type=module_type,
        passed=not all_mismatches and roundtrip.passed,
        topology=topology,
        step_count=len(intents),
        mismatches=tuple(all_mismatches),
        warnings=tuple([*warnings, *roundtrip.warnings]),
        roundtrip=roundtrip,
    )
