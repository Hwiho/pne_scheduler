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


def test_qpeed_variant_labels_do_not_claim_a_fixed_step_count() -> None:
    choices = spec_for("qpeed", "variant").choices

    assert choices
    assert all("스텝" not in choice.label for choice in choices)


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


def test_a_text_parameter_is_not_validated_as_a_number():
    """`text` fell through to float(), so every text field reported NOT_NUMBER —
    and because errors gate export, a detached module became unexportable over a
    parameter that only records where it came from."""
    from pne_scheduler.spec.parameter import ParameterSpec, validate_value

    spec = ParameterSpec(
        "source_module_type", "원본 모듈", "text", "method", "source_module_type",
        default="",
    )
    assert validate_value(spec, "formation") == ()
    assert validate_value(spec, "") == ()


def test_a_detached_module_reports_no_errors_of_its_own(tmp_path):
    """The end-to-end shape of the same bug."""
    from pne_scheduler.ui.document import ProjectDocument
    from pne_scheduler.ui.workspace_model import WorkspaceModel

    model = WorkspaceModel(ProjectDocument.new(autosave_dir=tmp_path / "recovery"))
    module_id = model.add_module("formation", {"cycle_count": 1})
    assert not [row for row in model.validation_rows() if row.severity == "error"]

    model.detach(module_id)
    assert not [row for row in model.validation_rows() if row.severity == "error"]


def test_sequence_specs_keep_structured_children_out_of_the_generated_form() -> None:
    specs = {spec.key: spec for spec in visible_parameter_specs("sequence", {})}
    form = build_module_form(
        "sequence",
        {"name": "내 블록", "children": [], "repeat_count": 1},
        include_advanced=False,
    )

    assert {"name", "repeat_count"} <= set(specs)
    assert form.hidden_keys == ("children",)


@pytest.mark.parametrize("kind", ["cc_charge", "cccv_charge", "cc_discharge"])
def test_primitive_form_hides_duration_when_step_does_not_use_it(kind):
    form = build_module_form("primitive", {"kind": kind}, cell=CELL)
    assert form.field_for("duration_s") is None


@pytest.mark.parametrize("kind", ["rest", "ocv", "cv_charge"])
def test_timed_primitive_form_keeps_duration(kind):
    form = build_module_form("primitive", {"kind": kind}, cell=CELL)
    assert form.field_for("duration_s") is not None
