"""Write .sch binary files from ScheduleProject IR."""

from __future__ import annotations

from pathlib import Path

from ..engine.compiler import compile_step_warnings, compile_steps
from ..ir.project import ScheduleProject
from ..schema import DEFAULT_SCH_VERSION
from ..schema.ensol_v612 import STEP_SIZE
from ..schema.enums import SchFileVersion
from ..schema.layouts import get_sch_layout
from .header import build_sch_header, safety_limits_from_cell

_SUPPORTED_WRITE_VERSIONS = {
    int(SchFileVersion.V0X00010003),
    int(SchFileVersion.V0X00010004),
}


def write_sch(project: ScheduleProject, output_path: Path) -> None:
    """Compile project to a framed SCH file (``0x00010003`` or ``0x00010004``)."""
    intents = project.expand_steps()
    if not intents or intents[-1].step_type != "end":
        from ..ir.step_intent import StepIntent

        intents = [*intents, StepIntent(step_type="end")]

    _ = compile_step_warnings(intents)
    step_records = compile_steps(intents, project.cell_profile)
    payload = _build_file_bytes(project, step_records)
    output_path.write_bytes(payload)


def _pad_step_record(record: bytes, step_size: int) -> bytes:
    if len(record) == step_size:
        return record
    if len(record) > step_size:
        raise ValueError(
            f"Compiled step record is {len(record)} bytes; cannot fit step_size {step_size}"
        )
    # 696-byte records: keep the verified 612-byte prefix and zero the unmapped tail.
    return record + (b"\x00" * (step_size - len(record)))


def _build_file_bytes(project: ScheduleProject, step_records: list[bytes]) -> bytes:
    version = int(project.sch_version or DEFAULT_SCH_VERSION)
    if version not in _SUPPORTED_WRITE_VERSIONS:
        raise ValueError(
            f"From-scratch writer currently supports 0x00010003/0x00010004 "
            f"(got 0x{version:08x}); use patch-sch for other layouts"
        )

    layout = get_sch_layout(version)
    if layout is None:
        raise ValueError(f"No layout registered for 0x{version:08x}")

    cell = project.cell_profile
    header = build_sch_header(
        version=version,
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
    body.extend(b"\x00" * (len(step_records) * layout.step_size))
    for index, record in enumerate(step_records):
        if len(record) != STEP_SIZE:
            raise ValueError(
                f"Step record {index + 1} has size {len(record)}, expected {STEP_SIZE}"
            )
        padded = _pad_step_record(record, layout.step_size)
        start = layout.payload_offset + index * layout.step_size
        body[start : start + layout.step_size] = padded
    return bytes(body)
