from __future__ import annotations

from pathlib import Path

import pytest

from pne_scheduler.tools.analyze_schedule_mdb import build_schedule_mdb_report

MDB = Path("c:/Schedule.mdb")


@pytest.mark.skipif(not MDB.is_file(), reason="lab Schedule.mdb not present")
def test_schedule_mdb_analysis_shape() -> None:
    report = build_schedule_mdb_report(MDB)
    assert report["schema"] == "pne_scheduler.schedule_mdb_analysis/v1"
    assert report["contains_raw_sch_blobs"] is False
    assert report["counts"]["schedules"] >= 800
    assert "TestName" in report["tables"]
    assert "Step" in report["tables"]
    assert report["tables"]["TestName"]["row_count"] == report["counts"]["schedules"]
