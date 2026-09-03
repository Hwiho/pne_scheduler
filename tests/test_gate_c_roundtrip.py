"""Gate C3/C4 — writer round-trip and ASSB cross-check."""

from __future__ import annotations

from pathlib import Path

from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.ir.project import ScheduleProject
from pne_scheduler.ir.step_intent import StepIntent
from pne_scheduler.io.layout import detect_sch_layout
from pne_scheduler.io.sch_binary import read_sch_binary
from pne_scheduler.io.writer import write_sch
from pne_scheduler.validate.roundtrip import roundtrip_intents, roundtrip_project
from pne_scheduler.validate.writer_assb_check import cross_check_writer_output_with_assb

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "example" / "example.schproj"
CELL = CellProfile(nominal_capacity_mAh=80.0, v_max=4.2, v_min=2.5)


def _smoke_intents() -> list[StepIntent]:
    return [
        StepIntent(step_type="rest", end_time_s=60.0, record_time_s=60.0),
        StepIntent(
            step_type="charge",
            mode="CCCV",
            c_rate=0.1,
            voltage_v=4.2,
            cv_cutoff_c_rate=0.05,
            record_time_s=60.0,
        ),
        StepIntent(
            step_type="discharge",
            mode="CC",
            c_rate=0.1,
            end_voltage_v=2.5,
            record_time_s=60.0,
        ),
        StepIntent(step_type="loop", loop_goto_step=1, loop_count=2),
        StepIntent(step_type="end"),
    ]


def test_c3_roundtrip_intents_pass(tmp_path: Path) -> None:
    output = tmp_path / "roundtrip.sch"
    report = roundtrip_intents(_smoke_intents(), cell=CELL, output_path=output)
    assert report.passed, report.mismatches
    assert report.parsed_step_count == 5


def test_c3_roundtrip_example_project_pass(tmp_path: Path) -> None:
    output = tmp_path / "example_roundtrip.sch"
    project = ScheduleProject.load(PROJECT)
    report = roundtrip_project(project, output)
    assert report.passed, report.mismatches
    assert report.parsed_step_count == report.expected_step_count


def test_c4_writer_output_matches_assb(tmp_path: Path) -> None:
    output = tmp_path / "assb_crosscheck.sch"
    report = roundtrip_intents(_smoke_intents(), cell=CELL, output_path=output)
    assert report.passed, report.mismatches
    check = cross_check_writer_output_with_assb(output)
    assert check.passed, check.notes
    assert check.layout_match
    assert check.step_count_match
    assert check.field_mismatch_count == 0


def test_c6_writer_emits_696_shared_prefix_framing(tmp_path: Path) -> None:
    output = tmp_path / "v10004.sch"
    project = ScheduleProject(
        name="c6-smoke",
        cell_profile=CELL,
        sch_version=0x00010004,
        modules=[],
        connections=[],
    )
    project.expand_steps = lambda: _smoke_intents()  # type: ignore[method-assign]
    write_sch(project, output)

    layout = detect_sch_layout(output.read_bytes())
    assert layout is not None
    assert layout.payload_offset == 1844
    assert layout.step_size == 696

    doc = read_sch_binary(output)
    assert doc.sch_version == 0x00010004
    assert doc.payload_offset == 1844
    assert doc.step_size == 696
    assert doc.step_count == 5
    # Unmapped 84-byte tail stays zero on from-scratch writes.
    assert doc.steps[1].record[612:] == b"\x00" * 84

    check = cross_check_writer_output_with_assb(output)
    assert check.layout_match
    assert check.step_count_match
