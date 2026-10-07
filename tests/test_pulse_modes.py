from __future__ import annotations

import pytest

from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.ir.project import ModuleNode
from pne_scheduler.modules.hppc import HppcModule
from pne_scheduler.modules.rpt import RptModule
from pne_scheduler.protocol.module_state import module_boundary_issues


CELL = CellProfile(nominal_capacity_mAh=80.0, v_min=2.5, v_max=4.2)


@pytest.mark.parametrize("module_type,params,expected_topology", [
    ("rpt", {"include_dcir_pulses": False, "rest_s": 2700},
     ("discharge", "rest", "end")),
    ("hppc", {"variant": "discharge_soc_pulse", "soc_fractions": [0.8], "pulse_s": 30},
     ("discharge", "rest", "discharge", "rest", "end")),
    ("hppc", {"variant": "charge_soc_pulse", "soc_fractions": [0.8], "pulse_s": 30},
     ("discharge", "rest", "charge", "rest", "end")),
])
def test_new_pulse_recipes_write_and_reparse_sch_candidates(
    tmp_path, module_type, params, expected_topology,
) -> None:
    from pne_scheduler.validate.gate_d_harness import run_module_pipeline

    path = tmp_path / "reopen-only.sch"
    result = run_module_pipeline(module_type, cell=CELL, output_path=path, params=params)
    assert result.passed, result.mismatches
    assert path.is_file() and path.stat().st_size > 0
    assert result.topology == expected_topology
    assert result.roundtrip is not None and result.roundtrip.passed
    if module_type == "hppc":
        assert any("end_capacity_fraction" in warning for warning in result.warnings)


def _measurement_pulses(module: HppcModule):
    return [
        step
        for step in module.expand(CELL)
        if step.step_type in {"charge", "discharge"}
        and "measurement pulse" in step.label
    ]


def test_rpt_without_dcir_is_one_reference_discharge_and_final_rest() -> None:
    module = RptModule(
        include_dcir_pulses=False,
        reference_c_rate=0.25,
        soc_fractions=[0.9, 0.1],
        dcir_pulse_c_rates=[],
        preparation_policy="unconfirmed_entry",
        start_soc=0.25,
    )

    assert module.validate(CELL) == []
    steps = module.expand(CELL)

    assert [step.step_type for step in steps] == ["discharge", "rest"]
    assert steps[0].mode == "CC"
    assert steps[0].c_rate == pytest.approx(0.25)
    assert steps[0].end_voltage_v == pytest.approx(CELL.v_min)
    assert steps[0].end_capacity_fraction is None
    assert all("SOC" not in step.label and "DC-IR pulse" not in step.label for step in steps)


def test_rpt_without_dcir_honors_explicit_charge_to_full_preparation() -> None:
    module = RptModule(
        include_dcir_pulses=False,
        preparation_policy="charge_to_full",
        start_soc=0.25,
    )
    steps = module.expand(CELL)

    assert module.validate(CELL) == []
    assert [step.step_type for step in steps] == ["charge", "rest", "discharge", "rest"]
    assert steps[0].mode == "CCCV"
    assert steps[0].voltage_v == pytest.approx(CELL.v_max)
    assert steps[2].mode == "CC"
    assert steps[2].end_voltage_v == pytest.approx(CELL.v_min)
    assert sum(step.step_type == "discharge" for step in steps) == 1
    assert all(step.end_capacity_fraction is None for step in steps)


def test_rpt_with_dcir_keeps_existing_soc_ladder_shape() -> None:
    steps = RptModule(
        include_dcir_pulses=True,
        soc_fractions=[0.8],
        dcir_pulse_c_rates=[1.0, 1.5],
    ).expand(CELL)

    assert [step.step_type for step in steps] == [
        "discharge", "rest", "discharge", "rest", "discharge", "rest"
    ]
    assert steps[0].end_capacity_fraction == pytest.approx(0.2)
    assert [step.c_rate for step in steps if "DC-IR pulse" in step.label] == [1.0, 1.5]
    assert [
        (
            step.step_type,
            step.mode,
            step.label,
            step.c_rate,
            step.end_time_s,
            step.end_capacity_fraction,
            step.dcr_start_s,
            step.dcr_end_s,
        )
        for step in steps
    ] == [
        (
            "discharge",
            "CC",
            "RPT C/3 to SOC 80%",
            1.0 / 3.0,
            None,
            1.0 - 0.8,
            None,
            None,
        ),
        ("rest", None, "RPT rest at SOC 80%", None, 1800.0, None, None, None),
        ("discharge", "CC", "RPT DC-IR pulse 1C @ SOC 80%", 1.0, 10.0, None, 1.0, 10.0),
        ("rest", None, "RPT rest after DC-IR 1C @ SOC 80%", None, 1800.0, None, None, None),
        ("discharge", "CC", "RPT DC-IR pulse 1.5C @ SOC 80%", 1.5, 10.0, None, 1.0, 10.0),
        ("rest", None, "RPT rest after DC-IR 1.5C @ SOC 80%", None, 1800.0, None, None, None),
    ]


@pytest.mark.parametrize(
    ("variant", "pulse_type", "absent_type", "voltage"),
    [
        ("discharge_soc_pulse", "discharge", "charge", CELL.v_min),
        ("charge_soc_pulse", "charge", "discharge", CELL.v_max),
    ],
)
def test_new_hppc_modes_emit_only_the_selected_measurement_pulse_polarity(
    variant, pulse_type, absent_type, voltage
) -> None:
    module = HppcModule(variant=variant, soc_fractions=[0.8, 0.5])

    pulses = _measurement_pulses(module)

    assert [step.step_type for step in pulses] == [pulse_type, pulse_type]
    assert not [step for step in pulses if step.step_type == absent_type]
    assert all(step.voltage_v == pytest.approx(voltage) for step in pulses)
    assert all(step.end_voltage_v == pytest.approx(voltage) for step in pulses)
    adjustments = [step for step in module.expand(CELL) if "SOC adjustment" in step.label]
    assert all(step.step_type == "discharge" for step in adjustments)
    assert all(step.c_rate == pytest.approx(1.0 / 3.0) for step in adjustments)


def test_hppc_signed_pulse_capacity_changes_the_next_soc_adjustment() -> None:
    discharge = HppcModule(
        variant="discharge_soc_pulse",
        soc_fractions=[0.8, 0.5],
        pulse_c_rate=1.0,
        pulse_s=36.0,
    )
    charge = HppcModule(
        variant="charge_soc_pulse",
        soc_fractions=[0.8, 0.5],
        pulse_c_rate=1.0,
        pulse_s=36.0,
    )

    discharge_adjustments = [
        step.end_capacity_fraction
        for step in discharge.expand(CELL)
        if "SOC adjustment" in step.label
    ]
    charge_adjustments = [
        step.end_capacity_fraction
        for step in charge.expand(CELL)
        if "SOC adjustment" in step.label
    ]

    assert discharge_adjustments == pytest.approx([0.2, 0.29])
    assert charge_adjustments == pytest.approx([0.2, 0.31])


@pytest.mark.parametrize(
    ("module", "message"),
    [
        (HppcModule(variant="discharge_soc_pulse", soc_fractions=[0.5, 0.8]), "strictly descending"),
        (HppcModule(variant="charge_soc_pulse", start_soc=0.5, soc_fractions=[0.8]), "reachable"),
        (HppcModule(variant="discharge_soc_pulse", pulse_s=0.0), "duration"),
        (HppcModule(variant="charge_soc_pulse", soc_rest_s=float("inf")), "rest duration"),
        (
            HppcModule(
                variant="discharge_soc_pulse",
                soc_fractions=[0.001],
                pulse_c_rate=1.0,
                pulse_s=10.0,
            ),
            "deplete",
        ),
        (
            HppcModule(
                variant="charge_soc_pulse",
                soc_fractions=[0.999],
                pulse_c_rate=1.0,
                pulse_s=10.0,
            ),
            "100%",
        ),
    ],
)
def test_new_hppc_modes_reject_unsafe_or_inconsistent_inputs(module, message) -> None:
    assert any(message in error for error in module.validate(CELL))


def test_new_hppc_entry_state_is_preflighted_without_relabeling_legacy() -> None:
    new_issues = module_boundary_issues(
        [ModuleNode("new", "hppc", {"variant": "discharge_soc_pulse"})]
    )
    legacy_issues = module_boundary_issues(
        [ModuleNode("legacy", "hppc", {"variant": "legacy_soc_pulse"})]
    )

    assert {issue.code for issue in new_issues} == {
        "ENTRY_SOC_UNCONFIRMED",
        "HPPC_SOC_PULSE_REOPEN_ONLY",
    }
    assert legacy_issues == []


def test_legacy_hppc_remains_a_paired_discharge_and_charge_pulse() -> None:
    steps = HppcModule(
        variant="legacy_soc_pulse", soc_fractions=[0.8]
    ).expand(CELL)

    assert [(step.step_type, step.label) for step in steps if "pulse" in step.label] == [
        ("discharge", "HPPC discharge pulse @ 80%"),
        ("charge", "HPPC charge pulse @ 80%"),
    ]


@pytest.mark.parametrize("variant", ["discharge_soc_pulse", "charge_soc_pulse"])
def test_hppc_stabilization_and_post_pulse_rests_are_independently_applied(variant):
    module = HppcModule(
        variant=variant, soc_fractions=[0.8], soc_rest_s=1800, rest_between_s=40
    )
    rests = [step for step in module.expand(CELL) if step.step_type == "rest"]
    assert [step.end_time_s for step in rests] == [1800, 40]
    module.rest_between_s = -1
    assert any("post-pulse rest" in error for error in module.validate(CELL))


def test_rpt_pulse_off_state_check_does_not_consume_hidden_soc_inputs():
    issues = module_boundary_issues([
        ModuleNode("cycle", "cycle_life", {}),
        ModuleNode("rpt", "rpt", {"include_dcir_pulses": False, "start_soc": "unused"}),
    ])
    assert not issues
    following = module_boundary_issues([
        ModuleNode("plain", "rpt", {"include_dcir_pulses": False}),
        ModuleNode("dcir", "dcir", {"start_soc": 1}),
    ])
    assert "ENTRY_SOC_CHAIN_CONFLICT" in {issue.code for issue in following}


def test_unconfirmed_soc_warning_is_human_readable_percent():
    issues = module_boundary_issues([ModuleNode("dcir", "dcir", {"start_soc": 0.8})])
    warning = next(issue for issue in issues if issue.code == "ENTRY_SOC_UNCONFIRMED")
    assert "80%" in warning.message
    assert "0.8" not in warning.message
