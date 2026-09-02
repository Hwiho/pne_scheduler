from __future__ import annotations

import struct
from pathlib import Path

import pytest

from pne_scheduler.io.sch_binary import read_sch_binary
from pne_scheduler.schema.ensol_v612 import OFF_LOOP_GOTO_ENSOL
from pne_scheduler.tools.export_baseline3_loop_goto_pne02 import (
    PNE02_ZIP,
    REST_STEP_TYPE,
    export_baseline3_loop_goto,
)


@pytest.mark.skipif(not PNE02_ZIP.is_file(), reason="PNE02.zip not in corpus")
def test_export_baseline3_loop_goto_pne02_layout(tmp_path: Path) -> None:
    out = tmp_path / "baseline3-loop-goto.sch"
    summary = export_baseline3_loop_goto(out)
    doc = read_sch_binary(out)
    assert summary["layout"] == "0x00010003/612"
    assert summary["file_size"] == 5432
    assert doc.sch_version == 0x00010003
    assert doc.payload_offset == 1760
    assert doc.step_count == 6
    assert [step.step_type_code for step in doc.steps] == [
        0x101,
        REST_STEP_TYPE,
        0x202,
        REST_STEP_TYPE,
        8,
        6,
    ]
    loop = doc.steps[4]
    assert struct.unpack_from("<I", loop.record, OFF_LOOP_GOTO_ENSOL)[0] == 1
    assert summary["controlled_pair_hint"]["expected_field"] == "loop_goto_ensol"
    charge = summary["steps"][0]
    assert charge["step_type"] == "CCCV"
    assert charge["f_iref"] == pytest.approx(10.0)
