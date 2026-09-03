from __future__ import annotations

import struct
from pathlib import Path

from pne_scheduler.io.header import build_sch_header_v00010003, safety_limits_from_cell
from pne_scheduler.io.layout import detect_sch_layout
from pne_scheduler.io.sch_binary import read_sch_binary
from pne_scheduler.io.writer import write_sch
from pne_scheduler.ir.project import ScheduleProject
from pne_scheduler.schema.ensol_v612 import (
    FILE_SIGNATURE,
    HEADER_SIZE_V3,
    HOFF_CTS_COMMON_SAFETY,
    HOFF_SAFETY,
    HOFF_SIGNATURE,
)
from pne_scheduler.schema.layouts import SCH_FILE_MAGIC

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "example" / "example.schproj"


def test_build_sch_header_v00010003_is_full_framed_header() -> None:
    header = build_sch_header_v00010003(
        schedule_name="demo",
        author="tester",
        safety=safety_limits_from_cell(
            v_max=4.2,
            v_min=2.5,
            nominal_capacity_mAh=80.0,
            max_current_mA=800.0,
        ),
    )

    assert len(header) == HEADER_SIZE_V3
    assert struct.unpack_from("<I", header, 0)[0] == SCH_FILE_MAGIC
    assert struct.unpack_from("<I", header, 4)[0] == 0x00010003
    assert header[HOFF_SIGNATURE : HOFF_SIGNATURE + len(FILE_SIGNATURE)] == FILE_SIGNATURE
    assert struct.unpack_from("<f", header, HOFF_SAFETY)[0] == 4200.0
    assert struct.unpack_from("<f", header, HOFF_SAFETY + 4)[0] == 2500.0
    assert struct.unpack_from("<f", header, HOFF_SAFETY + 8)[0] == 800.0
    # CTSEditorPro common-safety capacity (empty → "용량값이 설정되지 않았습니다")
    assert struct.unpack_from("<f", header, HOFF_CTS_COMMON_SAFETY)[0] == 4200.0
    assert struct.unpack_from("<f", header, HOFF_CTS_COMMON_SAFETY + 4)[0] == 2500.0
    assert struct.unpack_from("<f", header, HOFF_CTS_COMMON_SAFETY + 12)[0] == 80.0
    assert struct.unpack_from("<f", header, HOFF_CTS_COMMON_SAFETY + 20)[0] == 70.0


def test_write_sch_uses_1760_byte_header_not_512_placeholder(tmp_path: Path) -> None:
    output = tmp_path / "from_scratch.sch"
    project = ScheduleProject.load(PROJECT)

    write_sch(project, output)

    data = output.read_bytes()
    layout = detect_sch_layout(data)
    assert layout is not None
    assert layout.payload_offset == 1760
    assert layout.step_size == 612
    assert data[:4] != b"\x00\x00\x00\x00"
    assert len(data) >= 1760 + 612
    assert len(data) != 512 + 612  # old placeholder framing

    doc = read_sch_binary(output)
    assert doc.sch_version == 0x00010003
    assert doc.payload_offset == 1760
    assert doc.step_count >= 1
    assert doc.steps[-1].is_end
