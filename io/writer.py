"""Write .sch binary files from ScheduleProject IR."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..engine.compiler import compile_steps
from ..ir.project import ScheduleProject
from ..schema import DEFAULT_SCH_VERSION, STEP_RECORD_SIZE
from ..schema.layouts import SCH_FILE_MAGIC, get_sch_layout


def write_sch(project: ScheduleProject, output_path: Path) -> None:
    """Compile a project to an experimental .sch that the viewer parser can reload.

    The file is not equipment-ready. Header reserved bytes stay zero except for
    the corpus magic/version/timestamp framing needed for layout detection.
    """
    intents = project.expand_steps()
    if not intents or intents[-1].step_type != "end":
        from ..ir.step_intent import StepIntent

        intents = [*intents, StepIntent(step_type="end")]

    step_records = compile_steps(intents, project.cell_profile)
    payload = _build_file_bytes(project, step_records)
    output_path.write_bytes(payload)


def write_sch_reloadable(project: ScheduleProject, output_path: Path):
    """Write an experimental SCH and require the in-repo viewer parser to reload it."""
    write_sch(project, output_path)
    from .sch_parser import parse_schedule_file

    try:
        return parse_schedule_file(output_path)
    except ValueError as exc:
        raise ValueError(
            f"Wrote {output_path} but the viewer parser cannot reload it: {exc}"
        ) from exc


def _build_file_bytes(project: ScheduleProject, step_records: list[bytes]) -> bytes:
    import struct

    version = int(project.sch_version or DEFAULT_SCH_VERSION)
    layout = get_sch_layout(version)
    payload_offset = layout.payload_offset if layout is not None else 1760
    step_size = layout.step_size if layout is not None else STEP_RECORD_SIZE
    body = bytearray(payload_offset + len(step_records) * step_size)

    struct.pack_into("<I", body, 0, int(SCH_FILE_MAGIC))
    struct.pack_into("<I", body, 4, version)
    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S").encode("ascii")
    body[8 : 8 + min(len(created), 19)] = created[:19]
    label = b"PNE CTSPro Schedule File."
    body[72 : 72 + len(label)] = label

    for index, record in enumerate(step_records):
        start = payload_offset + index * step_size
        body[start : start + min(len(record), step_size)] = record[:step_size]

    return bytes(body)
