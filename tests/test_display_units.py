"""Presentation units are explicit while stored project units stay canonical."""

from copy import deepcopy

import pytest

from pne_scheduler.api.app import create_app
from pne_scheduler.api.serializers import field_json
from pne_scheduler.edit.steps import step_fields
from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.ir.project import ModuleNode, ScheduleProject
from pne_scheduler.spec import apply_field_edit, build_module_form, spec_for
from pne_scheduler.spec.parameter import ParameterSpec, parse_value, validate_value
from pne_scheduler.spec.units import parse_current_mA, parse_voltage


CELL = CellProfile(80, 4.2, 2.5)


@pytest.mark.parametrize("module_type", ["rpt", "dcir"])
def test_soc_form_uses_percent_without_migrating_stored_fractions(module_type):
    form = build_module_form(module_type, {}, cell=CELL)
    start = form.field_for("start_soc")
    points = form.field_for("soc_fractions")
    assert start.view.text == "100%"
    assert start.spec.unit_label == "%"
    assert "100%" in start.spec.range_text()
    assert points.view.text == "80%, 50%, 20%"
    assert field_json(start)["numericValue"] == 1.0
    assert start.value == 1.0
    assert points.value == [0.8, 0.5, 0.2]
    assert field_json(points)["numericValues"] == [0.8, 0.5, 0.2]
    assert "0–1" not in points.spec.help


@pytest.mark.parametrize("text", ["80", "80%", 80])
def test_start_soc_percent_edits_are_fractional_at_the_protocol_boundary(text):
    result = apply_field_edit("dcir", {}, "start_soc", text)
    assert result["start_soc"] == 0.8


def test_soc_list_percent_edit_roundtrips_exactly_and_validates_percent_bounds():
    result = apply_field_edit("rpt", {}, "soc_fractions", "80, 50%, 20")
    assert result["soc_fractions"] == [0.8, 0.5, 0.2]
    form = build_module_form("rpt", result, cell=CELL)
    assert form.field_for("soc_fractions").view.text == "80%, 50%, 20%"
    spec = spec_for("rpt", "start_soc")
    issues = validate_value(spec, parse_value(spec, "101"))
    assert any(issue.is_error and "101%" in issue.message for issue in issues)


def test_pulse_off_hides_inapplicable_soc_and_pulse_controls():
    form = build_module_form("rpt", {"include_dcir_pulses": False}, cell=CELL)
    keys = {field.key for field in form.fields}
    assert not {"start_soc", "soc_fractions", "dcir_pulse_s", "dcir_pulse_c_rates"} & keys
    assert {"reference_c_rate", "include_dcir_pulses", "rest_s"} <= keys


def test_unit_changes_parse_to_same_canonical_quantity():
    assert parse_voltage("4200 mV") == parse_voltage("4.2 V") == 4.2
    assert parse_current_mA("1.5 A") == parse_current_mA("1500 mA") == 1500
    assert apply_field_edit("rpt", {}, "rest_s", "0.5시간")["rest_s"] == 1800
    assert apply_field_edit("rpt", {}, "rest_s", "30분")["rest_s"] == 1800
    current = ParameterSpec("current", "전류", "current_mA")
    assert parse_value(current, "1.5A") == 1500


def test_numeric_metadata_retains_precision_and_capacity_detail_is_not_target_soc():
    form = build_module_form("formation", {"charge_c_rate": 0.4}, cell=CELL)
    assert field_json(form.field_for("charge_c_rate"))["numericValue"] == 0.4
    qc = build_module_form("qc", {}, cell=CELL)
    assert field_json(qc.field_for("fast_rates_c"))["numericValues"] == qc.field_for("fast_rates_c").value
    assert field_json(qc.field_for("fast_times_s"))["numericValues"] == qc.field_for("fast_times_s").value
    fields = step_fields(
        {"step_type": "discharge", "end_capacity_fraction": 0.2},
        nominal_capacity_mAh=80,
    )
    field = next(field for field in fields if field.key == "end_capacity_fraction")
    assert field.numeric_value == 0.2
    assert field.detail == "기준용량의 20%"


def test_http_soc_percent_edit_preserves_other_stored_parameters(tmp_path):
    client = create_app(tmp_path / "library", tmp_path / "storage.db").test_client()
    project = ScheduleProject(
        "units", CELL, modules=[ModuleNode("dcir", "dcir", {"pulse_s": 30})]
    ).to_dict()
    original = deepcopy(project)
    response = client.post(
        "/api/edit/setParam",
        json={"project": project, "args": {"moduleId": "dcir", "key": "start_soc", "text": "90%"}},
    )
    assert response.status_code == 200
    assert project == original
    result = response.get_json()
    params = result["project"]["modules"][0]["params"]
    assert params["start_soc"] == 0.9
    assert params["pulse_s"] == 30
    fields = [field for section in result["views"]["form"]["sections"] for field in section["fields"]]
    field = next(field for field in fields if field["key"] == "start_soc")
    assert field["value"] == "90%"
    assert field["numericValue"] == 0.9
