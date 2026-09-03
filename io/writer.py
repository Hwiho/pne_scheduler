"""Write .sch binary files from ScheduleProject IR."""

from __future__ import annotations

from pathlib import Path

from ..engine.compiler import compile_steps
from ..ir.project import ScheduleProject
from ..schema import DEFAULT_SCH_VERSION
from ..schema.enums import SchFileVersion
from ..schema.layouts import get_sch_layout
from ..schema.v0x00010003_612 import STEP_RECORD_SIZE
from .header import build_sch_header_v00010003, safety_limits_from_cell


def write_sch(project: ScheduleProject, output_path: Path) -> None:
    """Compile project to a framed ``0x00010003`` SCH file (Gate C1 header)."""
    intents = project.expand_steps()
    if not intents or intents[-1].step_type != "end":
        from ..ir.step_intent import StepIntent

        intents = [*intents, StepIntent(step_type="end")]

    step_records = compile_steps(intents, project.cell_profile)
    payload = _build_file_bytes(project, step_records)
    output_path.write_bytes(payload)


def _build_file_bytes(project: ScheduleProject, step_records: list[bytes]) -> bytes:
    version = int(project.sch_version or DEFAULT_SCH_VERSION)
    if version != int(SchFileVersion.V0X00010003):
        raise ValueError(
            f"From-scratch writer currently supports only 0x00010003 "
            f"(got 0x{version:08x}); use patch-sch for other layouts"
        )

    layout = get_sch_layout(version)
    if layout is None or layout.payload_offset != 1760 or layout.step_size != STEP_RECORD_SIZE:
        raise ValueError("0x00010003 layout registry mismatch")

    cell = project.cell_profile
    header = build_sch_header_v00010003(
        schedule_name=project.name or "schedule",
        safety=safety_limits_from_cell(
            v_max=cell.v_max,
            v_min=cell.v_min,
            nominal_capacity_mAh=cell.nominal_capacity_mAh,
            max_current_mA=cell.max_current_mA,
        ),
    )
    if len(header) != layout.payload_offset:
        raise AssertionError(
            f"Header length {len(header)} != payload offset {layout.payload_offset}"
        )

    body = bytearray(header)
    body.extend(b"\x00" * (len(step_records) * STEP_RECORD_SIZE))
    for index, record in enumerate(step_records):
        if len(record) != STEP_RECORD_SIZE:
            raise ValueError(
                f"Step record {index + 1} has size {len(record)}, expected {STEP_RECORD_SIZE}"
            )
        start = layout.payload_offset + index * STEP_RECORD_SIZE
        body[start : start + STEP_RECORD_SIZE] = record
    return bytes(body)
