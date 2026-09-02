from __future__ import annotations

from pathlib import Path

import pytest

from pne_scheduler.__main__ import main
from pne_scheduler.engine.compiler import voltage_to_raw_mV
from pne_scheduler.io.layout import detect_sch_layout
from pne_scheduler.io.sch_parser import parse_schedule_file
from pne_scheduler.io.writer import write_sch_reloadable
from pne_scheduler.ir.project import ScheduleProject
from pne_scheduler.schema.layouts import SCH_FILE_MAGIC


ROOT = Path(__file__).resolve().parents[1]


def test_voltage_encoding_matches_corpus_millivolts() -> None:
    assert voltage_to_raw_mV(3.318) == pytest.approx(3318.0)
    assert voltage_to_raw_mV(4.2) == pytest.approx(4200.0)
    assert voltage_to_raw_mV(3318.0) == pytest.approx(3318.0)


def test_qpeed_export_reloads_in_viewer_parser(tmp_path: Path) -> None:
    project = ScheduleProject.load(ROOT / "example" / "qpeed.schproj")
    output = tmp_path / "qpeed.sch"
    document = write_sch_reloadable(project, output)

    assert document.payload_offset == 1760
    assert document.step_size == 612
    data = output.read_bytes()
    layout = detect_sch_layout(data)
    assert layout is not None
    assert layout.payload_offset == 1760
    assert int.from_bytes(data[:4], "little") == SCH_FILE_MAGIC

    rest = document.steps[0]
    assert rest.step_type == "REST"
    assert rest.f_iref == pytest.approx(600.0)
    assert rest.f_end_time == pytest.approx(0.0)

    soc = next(
        step
        for step in document.steps
        if step.step_type == "CC_CHG" and step.f_end_v == pytest.approx(3318.0)
    )
    assert soc.f_iref == pytest.approx(80.0)

    pulse = next(
        step
        for step in document.steps
        if step.step_type == "CC_CHG" and step.f_end_v == pytest.approx(4200.0)
    )
    assert pulse.f_iref == pytest.approx(120.0)

    loops = [step for step in document.steps if step.step_type == "LOOP"]
    assert loops
    assert loops[0].loop_count == 12
    assert loops[0].loop_target >= 1
    assert document.steps[-1].step_type == "END"


def test_example_export_reloads(tmp_path: Path) -> None:
    project = ScheduleProject.load(ROOT / "example" / "example.schproj")
    document = write_sch_reloadable(project, tmp_path / "example.sch")
    assert document.steps[-1].step_type == "END"
    assert any(step.step_type == "LOOP" and step.loop_count == 2 for step in document.steps)
    assert any(step.step_type == "LOOP" and step.loop_count == 10 for step in document.steps)


def test_cli_build_reload_mentions_viewer(tmp_path: Path, capsys) -> None:
    output = tmp_path / "cli.sch"
    result = main(
        [
            "build",
            str(ROOT / "example" / "qpeed.schproj"),
            "-o",
            str(output),
            "--allow-experimental-output",
        ]
    )
    captured = capsys.readouterr()
    assert result == 0
    assert "Viewer reload OK" in captured.out
    parse_schedule_file(output)
