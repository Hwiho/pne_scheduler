"""Cell batches: explicit basis, separate currents, gated and atomic output."""

from __future__ import annotations

import hashlib
import json
import csv

import pytest

from pne_scheduler.batch import export_cell_batch, plan_cell_batch
from pne_scheduler.exporting import ExportBlocked
from pne_scheduler.ir.equipment_profile import EquipmentProfile
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
