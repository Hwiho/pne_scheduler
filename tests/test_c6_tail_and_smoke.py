from __future__ import annotations

from pathlib import Path

from pne_scheduler.io.sch_binary import read_sch_binary
from pne_scheduler.ir.project import ScheduleProject
from pne_scheduler.validate.roundtrip import roundtrip_project

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "example" / "fixtures"
SMOKE_PROJECT = ROOT / "example" / "smoke_rest_cc_end.schproj"
SMOKE_PROBE_PROJECT = ROOT / "example" / "smoke_writer_probe.schproj"


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


def test_smoke_writer_probe_project_roundtrips(tmp_path: Path) -> None:
    """One from-scratch build exercising charge+discharge+loop+per-step sampling.

    Every packed field here is already writer_ready/corpus_inferred in
    schema/fields.py; this only combines them so a single Gate C5 reopen can
    confirm the discharge codepath, the LOOP construct, and independent
    per-step sampling at once instead of needing separate physical tests.
    """
    project = ScheduleProject.load(SMOKE_PROBE_PROJECT)
    output = tmp_path / "smoke_writer_probe.sch"
    report = roundtrip_project(project, output)
    assert report.passed, report.mismatches
    assert report.expected_step_count == 6
    doc = read_sch_binary(output)
    # No Cycle marker: matches PNE02 loop pairs and CTS Cycle/Loop save rule.
    assert [step.step_type_code for step in doc.steps] == [
        0x101,  # CCCV charge
        0x03,  # rest 1
        0x202,  # CC discharge
        0x03,  # rest 2
        0x08,  # loop (goto step 1)
        0x06,  # end
    ]
