"""Write .sch binary files from ScheduleProject IR."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..engine.compiler import compile_steps
from ..ir.project import ScheduleProject
from ..schema import DEFAULT_SCH_VERSION
from ..schema.v0x00010003_612 import STEP_RECORD_SIZE


def write_sch(project: ScheduleProject, output_path: Path) -> None:
    """Compile project to a minimal valid .sch payload (Phase 0.3 stub)."""
    intents = project.expand_steps()
    if not intents or intents[-1].step_type != "end":
        from ..ir.step_intent import StepIntent

        intents = [*intents, StepIntent(step_type="end")]

    step_records = compile_steps(intents, project.cell_profile)
    payload = _build_file_bytes(project, step_records)
    output_path.write_bytes(payload)


def _build_file_bytes(project: ScheduleProject, step_records: list[bytes]) -> bytes:
    # Header + test info placeholders; exact sizes finalized in Phase 0.1.
    header = bytearray(512)
    payload_offset = len(header)
    body = bytearray(payload_offset + len(step_records) * STEP_RECORD_SIZE)

    # nFileVersion at offset 4 (UINT) — common PNE header hint pattern
    import struct

    struct.pack_into("<I", body, 0, 0)  # nFileID placeholder
    struct.pack_into("<I", body, 4, int(project.sch_version or DEFAULT_SCH_VERSION))

    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S").encode("ascii")
    body[8 : 8 + min(len(created), 63)] = created[:63]

    for index, record in enumerate(step_records):
        start = payload_offset + index * STEP_RECORD_SIZE
        body[start : start + STEP_RECORD_SIZE] = record

    return bytes(body)
