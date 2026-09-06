from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import struct

from pne_scheduler.io.sch_binary import (
    SchBinaryDocument,
    SchBinaryStep,
    read_loop_info,
    read_sch_binary,
    write_sch_binary,
)
from pne_scheduler.resume import build_resume_plan, detect_checkpoint, splice_resume_schedule
from pne_scheduler.schema.enums import (
    SCH_STEP_TYPE_CC_DISCHARGE,
    SCH_STEP_TYPE_CCCV,
    SCH_STEP_TYPE_END,
    SCH_STEP_TYPE_LOOP,
    SCH_STEP_TYPE_REST,
)
from pne_scheduler.schema.fields import OFFSET_LOOP_COUNT, OFFSET_LOOP_GOTO

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
    assert result.manifest_path == out.with_suffix(".sch.manifest.json")
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["writer"] == "resume_splice"
    assert manifest["template"]["sha256"]
    assert manifest["changed_fields"][0]["operation"] == "splice_and_renumber"
    assert manifest["validation"]["all_passed"] is True
    assert manifest["equipment_executable"] is False


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


def _make_step(step_no: int, step_type: int, step_size: int, *, goto: int = 0, count: int = 0) -> SchBinaryStep:
    record = bytearray(step_size)
    struct.pack_into("<i", record, 0, step_no)
    struct.pack_into("<i", record, 8, step_type)
    if step_type == int(SCH_STEP_TYPE_LOOP):
        struct.pack_into("<I", record, OFFSET_LOOP_GOTO, goto)
        struct.pack_into("<I", record, OFFSET_LOOP_COUNT, count)
    return SchBinaryStep(step_no=step_no, step_type_code=step_type, record=bytes(record))


def _write_loop_fixture(tmp_path: Path, *, loop_goto: int) -> Path:
    """rest(1) -> charge(2) -> rest(3) -> discharge(4) -> loop(5, goto=loop_goto) -> end(6)."""
    template = read_sch_binary(FIXTURE_SCH)
    steps = (
        _make_step(1, int(SCH_STEP_TYPE_REST), template.step_size),
        _make_step(2, int(SCH_STEP_TYPE_CCCV), template.step_size),
        _make_step(3, int(SCH_STEP_TYPE_REST), template.step_size),
        _make_step(4, int(SCH_STEP_TYPE_CC_DISCHARGE), template.step_size),
        _make_step(5, int(SCH_STEP_TYPE_LOOP), template.step_size, goto=loop_goto, count=3),
        _make_step(6, int(SCH_STEP_TYPE_END), template.step_size),
    )
    doc = SchBinaryDocument(
        path=tmp_path / "loop_fixture.sch",
        sch_version=template.sch_version,
        payload_offset=template.payload_offset,
        step_size=template.step_size,
        header=template.header,
        steps=steps,
    )
    write_sch_binary(doc, doc.path)
    return doc.path


def test_resume_remaps_loop_goto_target_within_resumed_range(tmp_path: Path) -> None:
    """LOOP originally goto=2 (charge); resuming from step 2 must remap it to
    the new position of that same step, not leave the stale original number."""
    sch_path = _write_loop_fixture(tmp_path, loop_goto=2)
    stepend = tmp_path / "stepend.csv"
    _write_stepend(stepend, [(2, "Rest", "Time Complete")])  # placeholder to satisfy detect_checkpoint

    out = tmp_path / "resumed.sch"
    # remaining_loop_count pinned explicitly so this test isolates goto remapping
    # from the separate (also correct) auto loop-count adjustment behavior.
    result = splice_resume_schedule(
        sch_path, stepend, out, resume_sch_step=2, remaining_loop_count=3
    )

    doc = read_sch_binary(out)
    loop_step = next(s for s in doc.steps if s.is_loop)
    goto, count = read_loop_info(loop_step)
    # original charge(2) is now new step 1 after splicing from step 2
    assert goto == 1
    assert count == 3
    assert any("goto target remapped" in w for w in result.plan.warnings)


def test_resume_blocks_when_loop_target_would_be_dropped(tmp_path: Path) -> None:
    """LOOP originally goto=2 (charge); resuming from step 3 drops step 2, so the
    original reference can no longer be represented -- must fail loudly, not
    silently point at whatever step now occupies that slot."""
    sch_path = _write_loop_fixture(tmp_path, loop_goto=2)
    stepend = tmp_path / "stepend.csv"
    _write_stepend(stepend, [(3, "Rest", "Time Complete")])

    out = tmp_path / "resumed.sch"
    with pytest.raises(ValueError, match="cannot safely remap"):
        splice_resume_schedule(sch_path, stepend, out, resume_sch_step=3)
