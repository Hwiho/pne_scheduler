from __future__ import annotations

import csv
from pathlib import Path

import pytest

from pne_scheduler.io.sch_binary import read_loop_info, read_sch_binary
from pne_scheduler.resume import build_resume_plan, detect_checkpoint, splice_resume_schedule

FIXTURE_SCH = (
    Path(__file__).resolve().parents[1]
    / "example"
    / "fixtures"
    / "capacheck_zip"
    / "9)Bimodal_SJ1300_6040_NCN_capacheck.sch"
)
HPPC_SCH = (
    Path(__file__).resolve().parents[1]
    / "example"
    / "fixtures"
    / "hppc"
    / "HPPC_Full range.sch"
)
RPT_696_SCH = (
    Path(__file__).resolve().parents[1]
    / "example"
    / "fixtures"
    / "capacheck_zip"
    / "07100766_260511_SJ1300_dry_40um_RPT_500cycle.sch"
)


def _write_stepend(path: Path, rows: list[tuple[int, str, str]]) -> None:
    """rows: (cts_step_no, step_type, code)"""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["StepNo", "StepType", "Code", "TotalCycle", "CycleNum", "StepTime_sec"])
        for step_no, step_type, code in rows:
            writer.writerow([step_no, step_type, code, 1, 1, 100.0])


@pytest.fixture
def stepend_partial(tmp_path: Path) -> Path:
    path = tmp_path / "partial_stepend.csv"
    _write_stepend(
        path,
        [
            (2, "Rest", "Time Complete"),
            (3, "Charge", "Current Complete"),
            (4, "Rest", "Time Complete"),
            (5, "Discharge", "Voltage Complete"),
        ],
    )
    return path


def test_detect_checkpoint_resume_after_completed_step(stepend_partial: Path) -> None:
    cp = detect_checkpoint(stepend_partial)
    assert cp.last_completed_sch_step == 4  # CTS 5 → SCH 4
    assert cp.resume_sch_step == 5
    assert cp.is_finished is False


def test_build_resume_plan(stepend_partial: Path) -> None:
    if not FIXTURE_SCH.exists():
        pytest.skip("fixture missing")
    plan = build_resume_plan(FIXTURE_SCH, stepend_partial)
    assert plan.resume_sch_step == 5
    assert plan.original_step_count >= plan.resume_sch_step


def test_splice_resume_schedule(stepend_partial: Path, tmp_path: Path) -> None:
    if not FIXTURE_SCH.exists():
        pytest.skip("fixture missing")
    out = tmp_path / "resumed.sch"
    result = splice_resume_schedule(FIXTURE_SCH, stepend_partial, out)
    doc = read_sch_binary(out)
    assert doc.step_count < read_sch_binary(FIXTURE_SCH).step_count
    assert doc.steps[0].step_no == 1
    assert doc.steps[-1].is_end
    assert result.plan.resumed_step_count == doc.step_count


@pytest.mark.parametrize(
    ("path", "step_no", "expected"),
    [
        (HPPC_SCH, 46, (29, 1)),
        (RPT_696_SCH, 40, (4, 100)),
    ],
)
def test_loop_fields_match_raw_fixtures(
    path: Path,
    step_no: int,
    expected: tuple[int, int],
) -> None:
    doc = read_sch_binary(path)
    loop = next(step for step in doc.steps if step.step_no == step_no)

    assert read_loop_info(loop) == expected
