from __future__ import annotations

from pathlib import Path

import pytest

from pne_scheduler.io.sch_binary import read_sch_binary
from pne_scheduler.tools.export_baseline2_pne02 import PNE02_ZIP, export_baseline2

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not PNE02_ZIP.is_file(), reason="PNE02.zip not in corpus")
def test_export_baseline2_pne02_layout(tmp_path: Path) -> None:
    out = tmp_path / "baseline2.sch"
    summary = export_baseline2(out)
    doc = read_sch_binary(out)
    assert summary["layout"] == "0x00010003/612"
    assert doc.sch_version == 0x00010003
    assert doc.payload_offset == 1760
    assert doc.step_count == 4
    assert [step.step_type_code for step in doc.steps] == [0x101, 0x202, 8, 6]
    charge = summary["steps"][0]
    assert charge["step_type"] == "CCCV"
    assert charge["f_iref"] == pytest.approx(10.0)
    assert charge["f_end_i"] == pytest.approx(2.0)
