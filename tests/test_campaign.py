"""Cycle/RPT campaign planning and the multi-rate DC-IR it schedules."""

from __future__ import annotations

from pathlib import Path

import pytest

from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.modules.rpt import RptModule
from pne_scheduler.protocol.campaign import build_cycle_rpt_campaign
from pne_scheduler.ui.document import ProjectDocument
from pne_scheduler.ui.workspace_model import WorkspaceModel
from pne_scheduler.validate.preflight import validate_project

CELL = CellProfile(nominal_capacity_mAh=80.0, v_min=2.5, v_max=4.2)


# --- multi-rate DC-IR -------------------------------------------------------


def test_each_rate_gets_its_own_pulse_and_recovery_rest():
    module = RptModule(soc_fractions=[0.8, 0.5], dcir_pulse_c_rates=[1.0, 1.5, 2.0])
    steps = module.expand(CELL)
    pulses = [s for s in steps if s.label and "DC-IR pulse" in s.label]
    assert [s.c_rate for s in pulses] == [1.0, 1.5, 2.0, 1.0, 1.5, 2.0]
    # A rest must follow every pulse so the next rate starts from the same SOC.
    for index, step in enumerate(steps):
        if step.label and "DC-IR pulse" in step.label:
            assert steps[index + 1].step_type == "rest"


def test_rate_labels_read_the_way_the_lab_writes_them():
    module = RptModule(soc_fractions=[0.5], dcir_pulse_c_rates=[1.0, 1.5, 2.0])
    labels = [s.label for s in module.expand(CELL) if s.label and "DC-IR pulse" in s.label]
    assert labels == [
        "RPT DC-IR pulse 1C @ SOC 50%",
        "RPT DC-IR pulse 1.5C @ SOC 50%",
        "RPT DC-IR pulse 2C @ SOC 50%",
    ]


def test_a_project_written_before_multi_rate_still_loads():
    """The old scalar key seeds the list, so an old file expands identically."""
    module = RptModule.from_params({"dcir_pulse_c_rate": 1.5, "soc_fractions": [0.5]})
    assert module.dcir_pulse_c_rates == [1.5]
    assert module.expand(CELL) == RptModule(
        soc_fractions=[0.5], dcir_pulse_c_rates=[1.5]
    ).expand(CELL)


@pytest.mark.parametrize(
    "rates, expected",
    [([], "must not be empty"), ([1.0, -2.0], "must be positive")],
)
def test_bad_pulse_rates_are_rejected(rates, expected):
    errors = RptModule(dcir_pulse_c_rates=rates).validate(CELL)
    assert any(expected in error for error in errors)


# --- campaign planning ------------------------------------------------------


def test_the_run_is_split_into_blocks_with_a_measurement_after_each():
    plan = build_cycle_rpt_campaign(
        total_cycles=200, rpt_every=50, charge_c_rate=0.5, discharge_c_rate=0.5
    )
    assert [block.module_type for block in plan.blocks] == [
        "rpt", *["cycle_life", "rpt"] * 4
    ]
    assert [b.params["loop_count"] for b in plan.blocks if b.module_type == "cycle_life"] == [
        50, 50, 50, 50
    ]
    assert plan.rpt_count == 5  # four checkpoints plus the baseline


def test_a_remainder_becomes_its_own_shorter_block():
    plan = build_cycle_rpt_campaign(
        total_cycles=120, rpt_every=50, charge_c_rate=0.5, discharge_c_rate=0.5
    )
    counts = [b.params["loop_count"] for b in plan.blocks if b.module_type == "cycle_life"]
    assert counts == [50, 50, 20]
    assert sum(counts) == 120
    assert any("나머지" in note for note in plan.notes)


def test_the_baseline_rpt_can_be_dropped():
    plan = build_cycle_rpt_campaign(
        total_cycles=100, rpt_every=50, charge_c_rate=0.5, discharge_c_rate=0.5,
        baseline_rpt=False,
    )
    assert plan.blocks[0].module_type == "cycle_life"
    assert plan.rpt_count == 2


def test_the_dcr_window_gap_is_stated_not_hidden():
    plan = build_cycle_rpt_campaign(
        total_cycles=50, charge_c_rate=0.5, discharge_c_rate=0.5
    )
    joined = " ".join(plan.warnings)
    assert "기록되지 않습니다" in joined
    assert "prototype" in joined


@pytest.mark.parametrize(
    "options",
    [
        {"total_cycles": 0},
        {"rpt_every": 0},
        {"charge_c_rate": 0.0},
        {"dcir_pulse_c_rates": []},
        {"dcir_pulse_c_rates": [1.0, -1.0]},
    ],
)
def test_bad_input_returns_errors_and_no_blocks(options):
    base = {"total_cycles": 100, "charge_c_rate": 0.5, "discharge_c_rate": 0.5}
    plan = build_cycle_rpt_campaign(**{**base, **options})
    assert plan.errors and not plan.blocks and not plan.ok


# --- applying it to a project ----------------------------------------------


def _empty_model(tmp_path: Path) -> WorkspaceModel:
    return WorkspaceModel(ProjectDocument.new(autosave_dir=tmp_path / "recovery"))


def test_applying_a_campaign_produces_a_valid_schedule(tmp_path):
    model = _empty_model(tmp_path)
    plan = build_cycle_rpt_campaign(
        total_cycles=100, rpt_every=50, charge_c_rate=0.5, discharge_c_rate=0.5,
        dcir_pulse_c_rates=[1.0, 1.5, 2.0],
    )
    ids = model.add_campaign(plan)

    assert len(ids) == len(set(ids)) == len(plan.blocks)
    steps = model.project.expand_steps()
    ends = [i for i, s in enumerate(steps) if s.step_type == "end"]
    assert ends == [len(steps) - 1], "only the final block may own END"
    loops = [s for s in steps if s.step_type == "loop"]
    assert [s.loop_count for s in loops] == [50, 50]
    assert not validate_project(model.project, purpose="experimental_build").errors


def test_the_whole_campaign_is_one_undo_step(tmp_path):
    model = _empty_model(tmp_path)
    plan = build_cycle_rpt_campaign(
        total_cycles=100, rpt_every=50, charge_c_rate=0.5, discharge_c_rate=0.5
    )
    model.add_campaign(plan)
    assert len(model.project.modules) == 5
    model.document.undo()
    assert model.project.modules == []
