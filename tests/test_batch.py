"""Cell batches: explicit basis, separate currents, gated and atomic output."""

from __future__ import annotations

import hashlib
import json
import csv

import pytest

from pne_scheduler.batch import export_cell_batch, plan_cell_batch
from pne_scheduler.exporting import ExportBlocked
from pne_scheduler.ir.equipment_profile import EquipmentProfile
from pne_scheduler.ir.project import ModuleNode
from pne_scheduler.ui.document import ProjectDocument, new_project
from pne_scheduler.ui.workspace_model import WorkspaceModel


def _project():
    document = ProjectDocument(new_project(), record_history=False)
    model = WorkspaceModel(document)
    model.add_module("formation")
    project = model.project
    project.equipment = EquipmentProfile.from_unit("PNE02")
    project.cell_profile.max_current_mA = 500.0
    return project


def _cycle_project():
    document = ProjectDocument(new_project(), record_history=False)
    model = WorkspaceModel(document)
    model.add_module("cycle_life", {"loop_count": 2})
    project = model.project
    project.equipment = EquipmentProfile.from_unit("PNE02")
    project.cell_profile.max_current_mA = 500.0
    return project


def _grouped_cycle_project():
    project = _cycle_project()
    cycle = project.modules[0].to_dict()
    cycle["params"]["sourceReference"] = "saved-method/v3"
    fixed = ModuleNode(
        "fixed_child", "custom_steps", {"steps": [{
            "step_type": "charge", "mode": "CC", "current_mA": 321.0,
            "end_voltage_v": 4.2, "ref_id": "fixed-charge",
        }]},
    ).to_dict()
    project.modules = [ModuleNode("sequence_1", "sequence", {
        "name": "선택한 수명 그룹",
        "repeat_count": 2,
        "selectionMetadata": {"selected": True, "source": "library"},
        "children": [cycle, fixed],
    })]
    return project


def _rows():
    return [
        {"cellId": "A01", "designCapacityMah": "80"},
        {"cellId": "A02", "designCapacityMah": "90"},
        {"cellId": "A03", "designCapacityMah": "100"},
    ]


def _reference_rows():
    return [
        {"cellId": "A01", "referenceCapacityMah": "80"},
        {"cellId": "A02", "referenceCapacityMah": "90"},
        {"cellId": "A03", "referenceCapacityMah": "100"},
    ]


@pytest.mark.parametrize("module_type,phase", [("formation", "cycle"), ("cycle_life", "formation"), ("qc", "formation")])
def test_grouping_cannot_bypass_batch_phase_separation(module_type, phase):
    project = _cycle_project()
    project.modules = [ModuleNode("group", "sequence", {
        "children": [ModuleNode("child", module_type, {}).to_dict()],
    })]
    plan = plan_cell_batch(project, phase=phase, basis="manual_reference", kind="preview", rows=_reference_rows())
    assert not plan.ok
    assert any("레시피를 분리" in error for error in plan.errors)
    assert all(not row["allowed"] and row["maxCurrentmA"] is None for row in plan.rows)


def test_direct_reference_capacity_controls_each_generated_file(tmp_path):
    project = _project()
    before = project.to_dict()
    plan = plan_cell_batch(
        project, phase="formation", basis="manual_reference", kind="preview",
        rows=_reference_rows(),
    )
    assert plan.ok, plan.errors
    assert [row["oneCmA"] for row in plan.rows] == [80.0, 90.0, 100.0]
    assert [row["maxCurrentmA"] for row in plan.rows] == [8.0, 9.0, 10.0]
    target = tmp_path / "reference-batch"
    export_cell_batch(plan, target, token=plan.token)
    manifest = json.loads((target / "batch-manifest.json").read_text(encoding="utf-8"))
    assert manifest["basis"] == "manual_reference"
    assert manifest["evidence"] == "manual_reference_unverified"
    for row, capacity, max_current in zip(manifest["cells"], (80, 90, 100), (8, 9, 10)):
        assert row["selectedCapacityMah"] == capacity
        assert row["designCapacityMah"] is None
        with (target / row["cellId"] / "steps.csv").open(encoding="utf-8-sig", newline="") as source:
            currents = [abs(float(step["전류(mA)"])) for step in csv.DictReader(source) if step["전류(mA)"]]
        assert max(currents) == max_current
    assert project.to_dict() == before


@pytest.mark.parametrize("row,expected", [
    ({"cellId": "A01"}, "기준용량"),
    ({"cellId": "A01", "referenceCapacityMah": 0}, "기준용량"),
    ({"cellId": "A01", "referenceCapacityMah": "nan"}, "기준용량"),
    ({"cellId": "A01", "referenceCapacityMah": 80, "designCapacityMah": 90}, "두 열"),
])
def test_direct_reference_input_fails_closed(row, expected):
    plan = plan_cell_batch(_project(), phase="formation", basis="manual_reference", kind="preview", rows=[row])
    assert not plan.ok
    assert expected in " ".join(plan.errors)


def test_three_cell_batch_has_distinct_currents_and_preserves_source(tmp_path):
    project = _project()
    before = project.to_dict()
    plan = plan_cell_batch(project, phase="formation", basis="design", kind="preview", rows=_rows())
    assert plan.ok, plan.errors
    assert [row["oneCmA"] for row in plan.rows] == [80.0, 90.0, 100.0]
    assert [row["maxCurrentmA"] for row in plan.rows] == [8.0, 9.0, 10.0]
    target = tmp_path / "new-batch"
    paths = export_cell_batch(plan, target, token=plan.token)
    assert target.is_dir() and len(paths) == 10
    manifest = json.loads((target / "batch-manifest.json").read_text(encoding="utf-8"))
    assert manifest["equipmentExecutable"] is False
    assert manifest["evidence"] == "manual_entry_unverified"
    for entry, capacity in zip(manifest["cells"], (80.0, 90.0, 100.0)):
        assert entry["selectedCapacityMah"] == capacity
        for artifact in entry["files"]:
            path = target / artifact["path"]
            assert path.is_file()
            assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
    assert project.to_dict() == before


def test_batch_rejects_stale_preview_and_never_overwrites(tmp_path):
    plan = plan_cell_batch(_project(), phase="formation", basis="design", kind="preview", rows=_rows())
    target = tmp_path / "new-batch"
    with pytest.raises(ExportBlocked, match="미리보기"):
        export_cell_batch(plan, target, token="stale")
    assert not target.exists()
    export_cell_batch(plan, target, token=plan.token)
    original = (target / "batch-manifest.json").read_bytes()
    with pytest.raises(ExportBlocked, match="출력 위치"):
        export_cell_batch(plan, target, token=plan.token)
    assert (target / "batch-manifest.json").read_bytes() == original


def test_rate_matrix_creates_collision_safe_variants_with_actual_currents(tmp_path):
    project = _cycle_project()
    before = project.to_dict()
    matrix = [
        {"chargeRate": 0.5, "dischargeRate": 1.0},
        {"chargeRate": 1.25, "dischargeRate": 1.5},
    ]
    plan = plan_cell_batch(
        project, phase="cycle", basis="manual_reference", kind="preview",
        rows=_reference_rows()[:1], matrix=matrix,
    )
    assert plan.ok, plan.errors
    assert [row["variantId"] for row in plan.rows] == ["v01", "v02"]
    assert [row["chargeCurrentmA"] for row in plan.rows] == [40.0, 100.0]
    assert [row["dischargeCurrentmA"] for row in plan.rows] == [80.0, 120.0]
    assert [row["maxCurrentmA"] for row in plan.rows] == [80.0, 120.0]

    target = tmp_path / "matrix-batch"
    paths = export_cell_batch(plan, target, token=plan.token)
    assert len(paths) == 7
    assert (target / "A01" / "v01" / "steps.csv").is_file()
    assert (target / "A01" / "v02" / "steps.csv").is_file()
    manifest = json.loads((target / "batch-manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "pne_scheduler.cell_batch/v2"
    assert manifest["matrix"] == [
        {"variantId": "v01", "chargeRate": 0.5, "dischargeRate": 1.0},
        {"variantId": "v02", "chargeRate": 1.25, "dischargeRate": 1.5},
    ]
    for entry in manifest["cells"]:
        source = target / entry["cellId"] / entry["variantId"] / "project.schproj"
        params = json.loads(source.read_text(encoding="utf-8"))["modules"][0]["params"]
        assert params["charge_c_rate"] == entry["chargeRate"]
        assert params["discharge_c_rate"] == entry["dischargeRate"]
        for artifact in entry["files"]:
            path = target / artifact["path"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
    assert project.to_dict() == before


def test_rate_matrix_keeps_explicit_fixed_current_and_binds_plan_token(tmp_path):
    project = _cycle_project()
    project.modules.append(ModuleNode(
        "fixed_1", "custom_steps", {"steps": [{
            "step_type": "charge", "mode": "CC", "current_mA": 321.0,
            "end_voltage_v": 4.2,
        }]},
    ))
    first = plan_cell_batch(
        project, phase="cycle", basis="manual_reference", kind="preview",
        rows=_reference_rows()[:1],
        matrix=[{"chargeRate": 0.5, "dischargeRate": 1.0}],
    )
    changed = plan_cell_batch(
        project, phase="cycle", basis="manual_reference", kind="preview",
        rows=_reference_rows()[:1],
        matrix=[{"chargeRate": 0.5, "dischargeRate": 1.5}],
    )
    assert first.ok, first.errors
    assert first.rows[0]["fixedCurrentSteps"] == 1
    assert first.rows[0]["maxCurrentmA"] == 321.0
    assert first.token != changed.token
    with pytest.raises(ExportBlocked, match="미리보기"):
        export_cell_batch(changed, tmp_path / "stale-matrix", token=first.token)


def test_rate_matrix_recurses_one_sequence_level_without_touching_metadata_or_fixed_current():
    project = _grouped_cycle_project()
    before = project.to_dict()
    plan = plan_cell_batch(
        project, phase="cycle", basis="manual_reference", kind="preview",
        rows=_reference_rows()[:1],
        matrix=[{"chargeRate": 0.75, "dischargeRate": 1.25}],
    )
    assert plan.ok, plan.errors
    assert plan.rows[0]["chargeCurrentmA"] == 60.0
    assert plan.rows[0]["dischargeCurrentmA"] == 100.0
    assert plan.rows[0]["fixedCurrentSteps"] == 1
    assert plan.rows[0]["maxCurrentmA"] == 321.0

    grouped = plan.cells[0].project.modules[0].params
    original_grouped = before["modules"][0]["params"]
    assert grouped["name"] == original_grouped["name"]
    assert grouped["repeat_count"] == original_grouped["repeat_count"]
    assert grouped["selectionMetadata"] == original_grouped["selectionMetadata"]
    assert grouped["children"][0]["params"]["sourceReference"] == "saved-method/v3"
    assert grouped["children"][0]["params"]["charge_c_rate"] == 0.75
    assert grouped["children"][0]["params"]["discharge_c_rate"] == 1.25
    assert grouped["children"][1] == original_grouped["children"][1]
    assert project.to_dict() == before


def test_rate_matrix_rejects_nested_sequence():
    nested_cycle = ModuleNode("cycle_nested", "cycle_life", {"loop_count": 2}).to_dict()
    nested = ModuleNode(
        "sequence_nested", "sequence", {"children": [nested_cycle]},
    ).to_dict()
    project = _cycle_project()
    project.modules = [ModuleNode("sequence_outer", "sequence", {"children": [nested]})]
    plan = plan_cell_batch(
        project, phase="cycle", basis="manual_reference", kind="preview",
        rows=_reference_rows()[:1],
        matrix=[{"chargeRate": 0.5, "dischargeRate": 1.0}],
    )
    assert not plan.ok
    assert "중첩 sequence" in " ".join(plan.errors)


@pytest.mark.parametrize("matrix,expected", [
    ([], "1개 이상"),
    ([{"chargeRate": 0.5}], "chargeRate와 dischargeRate"),
    ([{"chargeRate": "nan", "dischargeRate": 1.0}], "유한한 양수"),
    ([{"chargeRate": True, "dischargeRate": 1.0}], "값이 없습니다"),
    ([{"chargeRate": 0.5, "dischargeRate": 1.0}, {"chargeRate": 0.5, "dischargeRate": 1.0}], "중복"),
    ([{"chargeRate": 0.5, "dischargeRate": 1.0}] * 26, "25개 이하"),
])
def test_rate_matrix_fails_closed(matrix, expected):
    plan = plan_cell_batch(
        _cycle_project(), phase="cycle", basis="manual_reference", kind="preview",
        rows=_reference_rows()[:1], matrix=matrix,
    )
    assert not plan.ok
    assert expected in " ".join(plan.errors)


def test_rate_matrix_rejects_unsupported_rate_module_and_bounded_product():
    unsupported = _project()
    unsupported.modules = [ModuleNode("probe_1", "smoke_writer_probe", {})]
    rejected = plan_cell_batch(
        unsupported, phase="formation", basis="manual_reference", kind="preview",
        rows=_reference_rows()[:1], matrix=[{"chargeRate": 0.5, "dischargeRate": 1.0}],
    )
    assert not rejected.ok
    assert "지원하지 않습니다" in " ".join(rejected.errors)

    rows = [
        {"cellId": f"A{index:02d}", "referenceCapacityMah": 80}
        for index in range(100)
    ]
    bounded = plan_cell_batch(
        _cycle_project(), phase="cycle", basis="manual_reference", kind="preview",
        rows=rows,
        matrix=[{"chargeRate": rate, "dischargeRate": 1.0} for rate in range(1, 7)],
    )
    assert not bounded.ok
    assert "500개 이하" in " ".join(bounded.errors)


@pytest.mark.parametrize("rows,basis,phase,expected", [
    ([{"cellId": "A01", "designCapacityMah": 80}, {"cellId": "a01", "designCapacityMah": 90}], "design", "formation", "중복"),
    ([{"cellId": "../escape", "designCapacityMah": 80}], "design", "formation", "셀 ID"),
    ([{"cellId": "A01", "designCapacityMah": 80}], "activation_discharge", "derating", "방전용량"),
    ([{"cellId": "A01", "designCapacityMah": "nan"}], "design", "formation", "설계용량"),
    ([{"cellId": "A01", "designCapacityMah": 80}], "derating_discharge", "formation", "사용할 수 없습니다"),
])
def test_batch_blocks_missing_or_ambiguous_capacity(rows, basis, phase, expected):
    plan = plan_cell_batch(_project(), phase=phase, basis=basis, kind="preview", rows=rows)
    assert not plan.ok
    assert expected in " ".join(plan.errors)


def test_batch_review_candidates_are_reopen_only(tmp_path):
    plan = plan_cell_batch(_project(), phase="formation", basis="design", kind="review_candidate", rows=_rows()[:2])
    assert plan.ok, plan.errors
    target = tmp_path / "review-batch"
    paths = export_cell_batch(plan, target, token=plan.token)
    assert len([path for path in paths if path.suffix == ".sch"]) == 2
    manifest = json.loads((target / "batch-manifest.json").read_text(encoding="utf-8"))
    assert manifest["kind"] == "review_candidate"
    assert manifest["equipmentExecutable"] is False


def test_batch_api_requires_matching_plan(tmp_path):
    pytest.importorskip("flask")
    from pne_scheduler.api.app import create_app

    client = create_app(tmp_path / "library").test_client()
    payload = {
        "project": _project().to_dict(),
        "args": {"phase": "formation", "basis": "design", "kind": "preview", "rows": _rows()[:1]},
    }
    planned = client.post("/api/plan/cellBatch", json=payload)
    assert planned.status_code == 200
    token = planned.get_json()["token"]
    target = tmp_path / "api-batch"
    rejected = client.post("/api/export/cell-batch", json={**payload, "token": "stale", "outDir": str(target)})
    assert rejected.status_code == 409 and not target.exists()
    result = client.post("/api/export/cell-batch", json={**payload, "token": token, "outDir": str(target)})
    assert result.status_code == 200, result.get_json()
    assert target.is_dir()


def test_batch_api_defaults_to_direct_reference_capacity(tmp_path):
    pytest.importorskip("flask")
    from pne_scheduler.api.app import create_app

    client = create_app(tmp_path / "library").test_client()
    payload = {
        "project": _project().to_dict(),
        "args": {"phase": "formation", "kind": "preview", "rows": _reference_rows()[:1]},
    }
    planned = client.post("/api/plan/cellBatch", json=payload)
    assert planned.status_code == 200
    assert planned.get_json()["ok"] is True
    target = tmp_path / "direct-api-batch"
    exported = client.post(
        "/api/export/cell-batch",
        json={**payload, "token": planned.get_json()["token"], "outDir": str(target)},
    )
    assert exported.status_code == 200, exported.get_json()
    manifest = json.loads((target / "batch-manifest.json").read_text(encoding="utf-8"))
    assert manifest["basis"] == "manual_reference"
