"""Cycle/RPT campaign planning and the multi-rate DC-IR it schedules."""

from __future__ import annotations

from pathlib import Path

import pytest

from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.ir.project import ModuleNode
from pne_scheduler.modules.dcir import DcirModule
from pne_scheduler.modules.rpt import RptModule
from pne_scheduler.protocol.campaign import build_cycle_rpt_campaign
from pne_scheduler.protocol.module_state import module_boundary_issues
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
    # A rest follows every pulse for voltage recovery; it does not restore SOC.
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


def test_rpt_next_soc_segment_accounts_for_all_prior_pulse_capacity():
    module = RptModule(
        soc_fractions=[0.8, 0.5],
        dcir_pulse_c_rates=[1.0, 1.5],
        dcir_pulse_s=10.0,
    )
    setting_steps = [
        step for step in module.expand(CELL) if step.label.startswith("RPT C/3 to SOC")
    ]

    assert setting_steps[0].end_capacity_fraction == pytest.approx(0.2)
    expected_fraction = 0.8 - (1.0 + 1.5) * 10.0 / 3600.0 - 0.5
    assert setting_steps[1].end_capacity_fraction == pytest.approx(expected_fraction)
    assert setting_steps[1].end_capacity_fraction * 80.0 == pytest.approx(23.4444444444)


def test_dcir_next_soc_segment_accounts_for_prior_pulse_capacity():
    module = DcirModule(soc_fractions=[0.8, 0.5], pulse_c_rate=1.5, pulse_s=10.0)
    setting_steps = [
        step
        for step in module.expand(CELL)
        if step.label.startswith("DC-IR SOC setting")
    ]

    assert setting_steps[1].end_capacity_fraction == pytest.approx(
        0.8 - 1.5 * 10.0 / 3600.0 - 0.5
    )


@pytest.mark.parametrize(
    "module, expected",
    [
        (RptModule(soc_fractions=[0.5, 0.8]), "strictly descending"),
        (RptModule(soc_fractions=[0.8, float("nan")]), "finite"),
        (RptModule(reference_c_rate=0.0), "C-rate"),
        (RptModule(dcir_pulse_s=0.0), "pulse duration"),
        (RptModule(rest_s=float("inf")), "rest duration"),
        (DcirModule(dcr_start_s=10.0, dcr_end_s=1.0), "start time before"),
        (DcirModule(pulse_s=5.0, dcr_end_s=10.0), "within the pulse"),
        (
            DcirModule(soc_fractions=[0.8, 0.79], pulse_c_rate=10.0, pulse_s=10.0),
            "remain positive",
        ),
    ],
)
def test_bad_soc_ladder_inputs_are_rejected(module, expected):
    assert any(expected in error for error in module.validate(CELL))


def test_unconfirmed_entry_state_is_reported_without_adding_precharge():
    node = ModuleNode("rpt-1", "rpt", {})
    issues = module_boundary_issues([node])

    assert [(issue.code, issue.module_id, issue.severity) for issue in issues] == [
        ("ENTRY_SOC_UNCONFIRMED", "rpt-1", "warning")
    ]
    assert "자동으로 추가되지 않습니다" in issues[0].message
    assert not any(step.step_type == "charge" for step in RptModule().expand(CELL))


def test_user_confirmed_start_soc_changes_first_delta_and_clears_boundary_warning():
    module = RptModule(
        preparation_policy="user_confirmed_start_soc",
        start_soc=0.9,
        soc_fractions=[0.8],
    )
    node = ModuleNode(
        "rpt-1",
        "rpt",
        {"preparation_policy": "user_confirmed_start_soc", "start_soc": 0.9},
    )

    assert module.expand(CELL)[0].end_capacity_fraction == pytest.approx(0.1)
    assert module_boundary_issues([node]) == []


def test_precharge_policy_is_not_silently_invented():
    node = ModuleNode("dcir-1", "dcir", {"preparation_policy": "precharge"})
    issues = module_boundary_issues([node])

    assert [(issue.code, issue.severity) for issue in issues] == [
        ("ENTRY_PREPARATION_POLICY_INVALID", "error")
    ]
    assert DcirModule(preparation_policy="precharge").validate(CELL)


def test_low_terminal_state_conflicts_with_next_declared_start_soc_even_if_confirmed():
    issues = module_boundary_issues(
        [
            ModuleNode("cycle-1", "cycle_life", {}),
            ModuleNode("rest-1", "rest", {"duration_s": 60.0}),
            ModuleNode(
                "rpt-1",
                "rpt",
                {
                    "preparation_policy": "user_confirmed_start_soc",
                    "start_soc": 1.0,
                },
            ),
        ]
    )

    assert [(issue.code, issue.module_id, issue.severity) for issue in issues] == [
        ("ENTRY_SOC_CHAIN_CONFLICT", "rpt-1", "error")
    ]
    assert "충전 단계가 없습니다" in issues[0].message


def test_sequence_children_are_checked_in_order_and_report_the_parent_id():
    sequence = ModuleNode(
        "sequence-1",
        "sequence",
        {
            "children": [
                ModuleNode("cycle-child", "formation", {}).to_dict(),
                ModuleNode(
                    "rpt-child",
                    "rpt",
                    {
                        "preparation_policy": "user_confirmed_start_soc",
                        "start_soc": 0.8,
                    },
                ).to_dict(),
            ]
        },
    )

    issues = module_boundary_issues([sequence])

    assert [(issue.code, issue.module_id) for issue in issues] == [
        ("ENTRY_SOC_CHAIN_CONFLICT", "sequence-1")
    ]


@pytest.mark.parametrize("module_cls", [RptModule, DcirModule])
def test_charge_to_full_is_explicit_and_requires_full_start_soc(module_cls):
    module = module_cls(
        preparation_policy="charge_to_full",
        start_soc=1.0,
        reference_c_rate=0.2,
    )
    steps = module.expand(CELL)

    assert not module.validate(CELL)
    assert steps[0].step_type == "charge"
    assert steps[0].mode == "CCCV"
    assert steps[0].c_rate == pytest.approx(0.2)
    assert steps[0].voltage_v == pytest.approx(CELL.v_max)
    assert steps[0].cv_cutoff_c_rate == pytest.approx(0.05)
    assert steps[1].step_type == "rest"
    assert any("requires start_soc == 1" in error for error in module_cls(
        preparation_policy="charge_to_full",
        start_soc=0.9,
    ).validate(CELL))


def test_charge_to_full_resolves_the_known_low_to_rpt_boundary_conflict():
    issues = module_boundary_issues(
        [
            ModuleNode("cycle-1", "cycle_life", {}),
            ModuleNode(
                "rpt-1",
                "rpt",
                {"preparation_policy": "charge_to_full", "start_soc": 1.0},
            ),
        ]
    )

    assert issues == []


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


def test_campaign_defaults_to_one_user_dcir_current_and_keeps_reference_rate():
    plan = build_cycle_rpt_campaign(
        total_cycles=50,
        charge_c_rate=0.5,
        discharge_c_rate=0.5,
        reference_c_rate=0.2,
    )
    rpt = next(block for block in plan.blocks if block.module_type == "rpt")

    assert rpt.params["dcir_pulse_c_rates"] == [1.5]
    assert rpt.params["reference_c_rate"] == pytest.approx(0.2)
    assert rpt.params["preparation_policy"] == "unconfirmed_entry"
    assert any("ENTRY_SOC_UNCONFIRMED" in warning for warning in plan.warnings)


def test_user_selected_campaign_preparation_resolves_normal_cycle_to_rpt_chain(tmp_path):
    model = _empty_model(tmp_path)
    plan = build_cycle_rpt_campaign(
        total_cycles=50,
        charge_c_rate=0.5,
        discharge_c_rate=0.5,
        preparation_policy="charge_to_full",
        start_soc=1.0,
        reference_c_rate=0.2,
    )
    model.add_campaign(plan)

    assert not [
        issue
        for issue in validate_project(
            model.project, purpose="experimental_build"
        ).errors
        if issue.code in {"ENTRY_SOC_CHAIN_CONFLICT", "ENTRY_SOC_UNCONFIRMED"}
    ]
    assert any("장비 실행이 검증된 것은 아닙니다" in warning for warning in plan.warnings)


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
        {"reference_c_rate": float("nan")},
        {"soc_fractions": [0.8, 0.9]},
        {"cycle_rest_s": 0.0},
    ],
)
def test_bad_input_returns_errors_and_no_blocks(options):
    base = {"total_cycles": 100, "charge_c_rate": 0.5, "discharge_c_rate": 0.5}
    plan = build_cycle_rpt_campaign(**{**base, **options})
    assert plan.errors and not plan.blocks and not plan.ok


# --- applying it to a project ----------------------------------------------


def _empty_model(tmp_path: Path) -> WorkspaceModel:
    return WorkspaceModel(ProjectDocument.new(autosave_dir=tmp_path / "recovery"))


def test_applying_a_campaign_produces_a_structurally_valid_but_state_gated_schedule(
    tmp_path,
):
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
    errors = validate_project(model.project, purpose="experimental_build").errors
    assert errors
    assert {issue.code for issue in errors} == {"ENTRY_SOC_CHAIN_CONFLICT"}


def test_the_whole_campaign_is_one_undo_step(tmp_path):
    model = _empty_model(tmp_path)
    plan = build_cycle_rpt_campaign(
        total_cycles=100, rpt_every=50, charge_c_rate=0.5, discharge_c_rate=0.5
    )
    model.add_campaign(plan)
    assert len(model.project.modules) == 5
    model.document.undo()
    assert model.project.modules == []
