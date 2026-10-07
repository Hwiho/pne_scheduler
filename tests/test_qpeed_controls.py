from __future__ import annotations

from pathlib import Path

import pytest

from pne_scheduler.io.sch_parser import parse_schedule_file
from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.modules.qpeed import QpeedModule
from pne_scheduler.spec import build_module_form
from pne_scheduler.validate.gate_d_harness import run_module_pipeline


CELL = CellProfile(nominal_capacity_mAh=80.0, v_max=4.2, v_min=2.5)

CONDITIONING_TOPOLOGY = (
    "rest",
    "discharge",
    "rest",
    "charge",
    "rest",
    "discharge",
    "rest",
    "charge",
    "rest",
    "loop",
)
HIGH_RATE_BLOCK_TOPOLOGY = (
    "cycle",
    "charge",
    "rest",
    "rest",
    "discharge",
    "rest",
    "charge",
    "rest",
    "discharge",
    "rest",
    "charge",
    "rest",
    "loop",
)


def _topology(module: QpeedModule) -> tuple[str, ...]:
    return tuple(step.step_type for step in module.expand(CELL))


def test_capacity_start_soc_and_high_rate_dod_are_independent_for_every_reset() -> None:
    module = QpeedModule(
        variant="full",
        soc_control="capacity",
        start_soc_percent=23.0,
        high_rate_dod_percent=4.0,
        high_rate_levels=3,
    )

    assert module.validate(CELL) == []
    steps = module.expand(CELL)
    soc_resets = [step for step in steps if "nominal start SOC" in step.label]
    high_rate_charges = [
        step
        for step in steps
        if step.label.startswith("QPEED ") and step.label.endswith("C charge")
    ]

    assert len(soc_resets) == 4  # Initial setting plus one reset per rate block.
    assert all(step.end_capacity_fraction == pytest.approx(0.23) for step in soc_resets)
    assert all(step.dod_percent is None for step in soc_resets)
    assert all(step.voltage_v == pytest.approx(CELL.v_max) for step in soc_resets)
    assert all(step.end_voltage_v == pytest.approx(CELL.v_max) for step in soc_resets)

    assert len(high_rate_charges) == 3
    assert all(
        step.end_capacity_fraction == pytest.approx(0.04)
        for step in high_rate_charges
    )
    assert all(step.dod_percent is None for step in high_rate_charges)
    assert all(step.end_voltage_v == pytest.approx(CELL.v_max) for step in high_rate_charges)


def test_default_voltage_control_preserves_full_and_soc_setting_contracts() -> None:
    full = QpeedModule.from_params(
        {"variant": "full", "soc_voltage_source": "selected-result.csv:42"}
    )
    soc = QpeedModule(variant="soc_setting")

    assert full.soc_control == "voltage"
    assert full.soc_voltage_source == "selected-result.csv:42"
    assert _topology(full) == (
        CONDITIONING_TOPOLOGY
        + HIGH_RATE_BLOCK_TOPOLOGY * 12
        + ("end",)
    )
    assert _topology(soc) == CONDITIONING_TOPOLOGY + ("end",)

    full_steps = full.expand(CELL)
    high_rate_charges = [
        step
        for step in full_steps
        if step.label.startswith("QPEED ") and step.label.endswith("C charge")
    ]
    voltage_soc_charges = [
        step
        for step in full_steps
        if step.step_type == "charge"
        and step.mode == "CC"
        and step.end_voltage_v == pytest.approx(full.soc_voltage_v)
    ]
    soc_charge = soc.expand(CELL)[7]

    assert len(full_steps) == 167 and full_steps[-1].step_type == "end"
    assert len(voltage_soc_charges) == 13
    assert all(step.end_capacity_fraction is None for step in voltage_soc_charges)
    assert all(step.dod_percent == pytest.approx(1.0) for step in high_rate_charges)
    assert all(step.extra == {"cap_ref_step": 7} for step in high_rate_charges)
    assert len(soc.expand(CELL)) == 11 and soc.expand(CELL)[-1].step_type == "end"
    assert soc_charge.end_voltage_v == pytest.approx(3.318)
    assert soc_charge.dod_percent == pytest.approx(10.0)
    assert soc_charge.extra == {"cap_ref_step": 7}


@pytest.mark.parametrize("levels", [1, 40])
def test_high_rate_level_boundaries_are_valid(levels: int) -> None:
    assert QpeedModule(high_rate_levels=levels).validate(CELL) == []


@pytest.mark.parametrize("levels", [0, 41, True, False, 1.5, float("nan")])
def test_high_rate_levels_reject_out_of_range_bool_and_non_integer_values(
    levels: object,
) -> None:
    errors = QpeedModule(high_rate_levels=levels).validate(CELL)  # type: ignore[arg-type]

    assert "high_rate_levels must be an integer between 1 and 40" in errors


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("condition_c_rate", -1.0),
        ("high_rate_start_c", 0.0),
        ("high_rate_dod_percent", -1.0),
        ("high_rate_dod_percent", True),
        ("high_rate_dod_percent", float("nan")),
        ("start_soc_percent", 0.0),
        ("start_soc_percent", 100.0),
        ("start_soc_percent", False),
        ("start_soc_percent", float("nan")),
    ],
)
def test_charge_and_soc_controls_reject_nonpositive_bool_and_nan(
    field: str, value: object
) -> None:
    params = {"soc_control": "capacity", field: value}

    assert QpeedModule.from_params(params).validate(CELL)


def test_capacity_start_soc_plus_high_rate_dod_may_equal_but_not_exceed_100() -> None:
    valid = QpeedModule(
        soc_control="capacity", start_soc_percent=20.0, high_rate_dod_percent=80.0
    )
    invalid = QpeedModule(
        soc_control="capacity", start_soc_percent=20.0, high_rate_dod_percent=80.01
    )

    assert valid.validate(CELL) == []
    assert any("100%" in error for error in invalid.validate(CELL))


def test_capacity_qpeed_writes_and_reparses_capacity_end_fields(
    tmp_path: Path,
) -> None:
    path = tmp_path / "qpeed-capacity-reopen-only.sch"
    report = run_module_pipeline(
        "qpeed",
        cell=CELL,
        output_path=path,
        params={
            "variant": "full",
            "soc_control": "capacity",
            "start_soc_percent": 25.0,
            "high_rate_dod_percent": 5.0,
            "high_rate_levels": 1,
        },
    )

    assert report.passed, report.mismatches
    assert report.topology == (
        CONDITIONING_TOPOLOGY + HIGH_RATE_BLOCK_TOPOLOGY + ("end",)
    )
    assert report.roundtrip is not None and report.roundtrip.passed
    assert any("end_capacity_fraction" in warning for warning in report.warnings)

    parsed = parse_schedule_file(path)
    assert len(parsed.steps) == 24
    assert parsed.steps[-1].step_type == "END"
    assert parsed.steps[7].step_type == "CC_CHG"
    assert parsed.steps[7].f_end_c == pytest.approx(20.0)
    assert parsed.steps[11].step_type == "CC_CHG"
    assert parsed.steps[11].f_end_c == pytest.approx(4.0)
    assert parsed.steps[20].step_type == "CC_CHG"
    assert parsed.steps[20].f_end_c == pytest.approx(20.0)


def test_capacity_full_form_exposes_start_soc_and_high_rate_dod_fields() -> None:
    capacity_form = build_module_form(
        "qpeed", {"variant": "full", "soc_control": "capacity"}, cell=CELL
    )
    voltage_form = build_module_form(
        "qpeed", {"variant": "full", "soc_control": "voltage"}, cell=CELL
    )

    assert capacity_form.field_for("start_soc_percent") is not None
    assert capacity_form.field_for("high_rate_dod_percent") is not None
    assert capacity_form.field_for("soc_voltage_v") is None
    assert voltage_form.field_for("start_soc_percent") is None
    assert voltage_form.field_for("soc_voltage_v") is not None
