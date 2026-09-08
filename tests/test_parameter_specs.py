from __future__ import annotations

import pytest

from pne_scheduler.ir import CellProfile
from pne_scheduler.spec import (
    UnitParseError,
    apply_field_edit,
    build_module_form,
    spec_coverage_gaps,
    spec_for,
    validate_value,
    visible_parameter_specs,
)

CELL = CellProfile(24.0, 4.2, 2.5, max_current_mA=500.0)


def test_every_visible_module_parameter_has_a_spec() -> None:
    assert spec_coverage_gaps() == ()


def test_qpeed_full_hides_legacy_only_parameters() -> None:
    keys = {spec.key for spec in visible_parameter_specs("qpeed", {"variant": "full"})}

    assert "high_rate_levels" in keys
    assert "soc_fractions" not in keys
    assert "pulse_s" not in keys
    assert "soc_dod_percent" not in keys


def test_qpeed_soc_setting_shows_its_own_dod() -> None:
    keys = {spec.key for spec in visible_parameter_specs("qpeed", {"variant": "soc_setting"})}

    assert "soc_dod_percent" in keys
    assert "high_rate_levels" not in keys


def test_c_rate_field_reports_current_and_equipment_headroom() -> None:
    form = build_module_form(
        "qpeed", {"variant": "full"}, cell=CELL, current_limit_mA=500.0
    )
    field = form.field_for("high_rate_start_c")

    assert field is not None
    assert "36 mA" in field.view.detail


def test_derived_values_expose_the_peak_rate_and_step_count() -> None:
    form = build_module_form(
        "qpeed", {"variant": "full"}, cell=CELL, current_limit_mA=500.0
    )
    derived = {value.label: value.text for value in form.derived}

    # 166 phase steps; the schedule's single trailing END is added once, by the
    # whole-project composition, not by each module.
    assert derived["스텝 수"] == "166 스텝"
    assert "432 mA" in derived["최고 전류"]


def test_current_over_the_equipment_limit_is_an_error() -> None:
    spec = spec_for("qpeed", "high_rate_start_c")
    issues = validate_value(spec, 25.0, cell=CELL, current_limit_mA=500.0)

    assert any(issue.code == "CURRENT_LIMIT" and issue.is_error for issue in issues)


def test_out_of_range_value_is_an_error_and_soft_range_is_a_warning() -> None:
    spec = spec_for("cycle_life", "loop_count")

    assert any(issue.is_error for issue in validate_value(spec, 0))
    assert all(
        not issue.is_error for issue in validate_value(spec, 2000)
    ) and validate_value(spec, 2000)


def test_apply_field_edit_parses_units_and_keeps_other_values() -> None:
    updated = apply_field_edit("formation", {"cycle_count": 2}, "rest_s", "30분")

    assert updated["rest_s"] == 1800.0
    assert updated["cycle_count"] == 2


def test_apply_field_edit_rejects_unreadable_text() -> None:
    with pytest.raises(UnitParseError):
        apply_field_edit("formation", {}, "charge_c_rate", "빠르게")


def test_choice_fields_round_trip_through_their_korean_label() -> None:
    form = build_module_form("hppc", {"variant": "full"}, cell=CELL)
    field = form.field_for("variant")
    updated = apply_field_edit("hppc", {"variant": "full"}, "variant", field.view.text)

    assert updated["variant"] == "full"
