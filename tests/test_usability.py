"""Cell table and key conditions are shared views, not new schedule arithmetic."""
from copy import deepcopy
import json

import pytest

from pne_scheduler.api import routes
from pne_scheduler.api.errors import ApiError
from pne_scheduler.batch import cell_table, inspect_cell_rows
from pne_scheduler.io.sch_parser import parse_schedule_file
from pne_scheduler.ui.native_controller import NativeController


def test_paste_preserves_invalid_values_and_extra_columns():
    result = cell_table([], action="paste", text="셀 ID\t기준용량\nA01\t80\nA02\t\nA03\t90\tunexpected")
    assert len(result["inputRows"]) == 3
    assert result["rows"][0]["oneCmA"] == 80
    assert {(i["row"], i["field"]) for i in result["issues"]} == {(1, "referenceCapacityMah"), (2, "extraColumns")}


def test_paste_empty_first_column_does_not_shift_capacity_into_id():
    result = cell_table([], action="paste", text="\t80\nA02\t90\t")
    assert result["inputRows"][0] == {"cellId": "", "referenceCapacityMah": "80"}
    assert result["inputRows"][1]["extraColumns"] == 1
    assert {(i["row"], i["field"]) for i in result["issues"]} == {(0, "cellId"), (1, "extraColumns")}


@pytest.mark.parametrize("cell_id", [None, True, False])
def test_empty_or_boolean_cell_id_is_not_a_filename(cell_id):
    result = inspect_cell_rows([{"cellId": cell_id, "referenceCapacityMah": 80}])
    assert not result["ok"]
    assert result["issues"][0]["field"] == "cellId"


def test_core_setup_keeps_exact_numeric_values_for_unitless_input(tmp_path):
    native = NativeController(data_dir=tmp_path)
    native.edit("setCellValue", {"key": "v_max", "text": "4.123456789"})
    fields = {field["key"]: field for field in native.views["setupFields"]}
    assert fields["v_max"]["numericValue"] == 4.123456789
    assert fields["nominal_capacity_mAh"]["numericValue"] == native.project["cell_profile"]["nominal_capacity_mAh"]


@pytest.mark.parametrize("value", [None, "", "bad", "nan", "inf", -1, 0, True, 1_000_001])
def test_invalid_capacity_has_addressable_issue(value):
    result = inspect_cell_rows([{"cellId": "A01", "referenceCapacityMah": value}])
    assert result["issues"][0]["field"] == "referenceCapacityMah"
    assert result["rows"][0]["oneCmA"] is None


def test_duplicate_ids_are_flagged_on_both_rows():
    result = inspect_cell_rows([{"cellId": name, "referenceCapacityMah": "80"} for name in ["A01", "a01"]])
    assert [(i["row"], i["field"]) for i in result["issues"]] == [(0, "cellId"), (1, "cellId")]


def test_table_operations_are_nonmutating_and_number_without_collisions():
    rows = [{"cellId": "A01", "referenceCapacityMah": "80"}, {"cellId": "A03", "referenceCapacityMah": "90"}]
    original = deepcopy(rows)
    copied = cell_table(rows, action="duplicate", selected=[0])["inputRows"]
    assert copied[-1] == {"cellId": "A02", "referenceCapacityMah": "80"}
    numbered = cell_table(copied, action="number", selected=[0, 2], prefix="A")["inputRows"]
    assert len({r["cellId"] for r in numbered}) == 3
    removed = cell_table(numbered, action="remove", selected=[1])["inputRows"]
    assert len(removed) == 2
    assert rows == original


@pytest.mark.parametrize("args", [{"action": "remove", "selected": [-1]},
                                  {"action": "number", "selected": [True]},
                                  {"action": "duplicate", "selected": []},
                                  {"action": "add", "prefix": "../"},
                                  {"action": "paste", "text": "X,80\n" * 101}])
def test_bad_table_operations_reject_whole_change(args):
    rows = [{"cellId": "A01", "referenceCapacityMah": "80"}]
    before = deepcopy(rows)
    with pytest.raises(ValueError):
        cell_table(rows, **args)
    assert rows == before


def test_web_native_table_parity_and_real_batch_files(tmp_path):
    native = NativeController(data_dir=tmp_path / "data")
    native.edit("setEquipmentUnit", {"unit": "PNE02"})
    native.edit("addModule", {"moduleType": "formation"})
    args = {"rows": [], "action": "paste", "text": "A01,80\nA02,90\nA03,100"}
    before = deepcopy(native.project)
    web = routes.plan("cellTable", {"project": native.project, "args": args})
    assert native.plan("cellTable", args) == web
    assert native.project == before
    options = {"phase": "formation", "basis": "manual_reference", "kind": "review_candidate", "rows": web["inputRows"]}
    plan = native.plan("cellBatch", options)
    assert plan["ok"]
    assert [r["oneCmA"] for r in plan["rows"]] == [80, 90, 100]
    assert [r["maxCurrentmA"] for r in plan["rows"]] == [8, 9, 10]
    native.export_batch(options, plan["token"], str(tmp_path / "outputs"))
    manifest = json.loads((tmp_path / "outputs" / "batch-manifest.json").read_text())
    assert len(manifest["cells"]) == 3
    assert manifest["equipmentExecutable"] is False
    for row, expected in zip(manifest["cells"], (8, 9, 10), strict=True):
        candidate = tmp_path / "outputs" / row["cellId"] / "candidate_REOPEN_ONLY_DO_NOT_RUN.sch"
        reopened = parse_schedule_file(candidate)
        assert max(abs(step.f_iref) for step in reopened.steps) == pytest.approx(expected)
    changed = deepcopy(options)
    changed["rows"][0]["referenceCapacityMah"] = "81"
    with pytest.raises(ApiError):
        native.export_batch(changed, plan["token"], str(tmp_path / "stale"))
    assert not (tmp_path / "stale").exists()


@pytest.mark.parametrize("module_type,keys", [
    ("formation", {"charge_c_rate", "discharge_c_rate", "rest_s", "cycle_count"}),
    ("cycle_life", {"loop_count", "charge_c_rate"}),
    ("primitive", {"kind", "duration_s"}),
    ("qpeed", {"high_rate_levels", "soc_control", "condition_c_rate"}),
])
def test_core_fields_use_visible_specs_and_existing_edit_history(tmp_path, module_type, keys):
    native = NativeController(data_dir=tmp_path)
    native.edit("addModule", {"moduleType": module_type})
    form = native.views["form"]
    fields = [f for section in form["sections"] for f in section["fields"]]
    assert keys <= {f["key"] for f in fields if f["keyCondition"]}
    web = routes.views({"project": native.project, "selected": native.selected})["views"]
    for key in ("form", "groupChildren", "setupFields", "procedure", "release"):
        assert native.views[key] == web[key]
    if module_type == "formation":
        before = deepcopy(native.project)
        native.edit("setParam", {"moduleId": form["moduleId"], "key": "charge_c_rate", "text": "0.2"})
        assert native.project["modules"][0]["params"]["charge_c_rate"] == .2
        native.undo()
        assert native.project == before


def test_group_core_conditions_identify_child_without_editing_siblings(tmp_path):
    native = NativeController(data_dir=tmp_path)
    for _ in range(2):
        native.edit("addModule", {"moduleType": "rest"})
    ids = [node["id"] for node in native.project["modules"]]
    native.edit("groupModules", {"moduleIds": ids, "name": "rests", "repeatCount": 2})
    group = native.project["modules"][0]["id"]
    native.edit("setGroupChildParam", {"moduleId": group, "index": 1, "key": "duration_s", "text": "30분"})
    children = native.project["modules"][0]["params"]["children"]
    assert children[0]["params"].get("duration_s", 600) == 600
    assert children[1]["params"]["duration_s"] == 1800
    for child in native.views["groupChildren"]:
        assert any(f["keyCondition"] for s in child["form"]["sections"] for f in s["fields"])
