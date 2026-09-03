from __future__ import annotations

from pathlib import Path

from pne_scheduler.io.sch_binary import read_sch_binary
from pne_scheduler.io.writer import write_sch
from pne_scheduler.ir.project import ScheduleProject
from pne_scheduler.validate.roundtrip import roundtrip_project

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "example" / "fixtures"
SMOKE_PROJECT = ROOT / "example" / "smoke_rest_cc_end.schproj"


def test_catalog_696_tails_are_all_zero() -> None:
    paths = sorted(FIXTURES.rglob("*.sch"))
    checked = 0
    for path in paths:
        try:
            doc = read_sch_binary(path)
        except ValueError:
            continue
        if doc.step_size != 696:
            continue
        checked += 1
        for step in doc.steps:
            assert step.record[612:] == b"\x00" * 84, path
    assert checked >= 90


def test_smoke_rest_cc_end_project_roundtrips(tmp_path: Path) -> None:
    project = ScheduleProject.load(SMOKE_PROJECT)
    output = tmp_path / "smoke.sch"
    report = roundtrip_project(project, output)
    assert report.passed, report.mismatches
    assert report.expected_step_count == 3
    doc = read_sch_binary(output)
    assert [step.step_type_code for step in doc.steps] == [3, 0x101, 6]
