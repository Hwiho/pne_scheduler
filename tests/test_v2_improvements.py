"""v2 follow-up: immutable methods and reversible local storage management."""

from __future__ import annotations

import copy
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from pne_scheduler.api.app import create_app
from pne_scheduler.edit.diff import diff_steps
from pne_scheduler.ir.step_intent import StepIntent
from pne_scheduler.ir.project import ScheduleProject
from pne_scheduler.library import MethodLibrary, method_load_token
from pne_scheduler.storage_companion import process_due
from pne_scheduler.storage_records import StorageStore
from pne_scheduler.ui.document import ProjectDocument
from pne_scheduler.ui.workspace_model import WorkspaceModel

NOW = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)


def rest(seconds):
    return {"id": "rest_1", "module_type": "rest", "params": {"duration_s": seconds}}


def source_project():
    return {"schema": "pne_scheduler.schproj/v2", "name": "v2 regression",
            "cell_profile": {"nominal_capacity_mAh": 80, "v_min": 2.5, "v_max": 4.2},
            "modules": [rest(600)], "connections": []}


@pytest.fixture()
def resources(tmp_path):
    root = tmp_path / "library"
    store = MethodLibrary(root)
    for seconds in (60, 1800):
        store.save(name="표준 휴지", method_id="standard", modules=[rest(seconds)],
                   equipment_unit="PNE02", description=f"{seconds}s")
    return create_app(root, tmp_path / "storage.sqlite3").test_client(), store


def preview(client, project=None, **options):
    return client.post("/api/library/load", json={
        "project": project or source_project(), "methodId": "standard",
        "version": 2, "preview": True, **options,
    })


def test_preview_compares_versions_without_changing_project_or_files(resources):
    client, store = resources
    project = source_project()
    original = copy.deepcopy(project)
    files = {path: path.read_bytes() for path in store.root.rglob("*.json")}
    data = preview(client, project).get_json()
    assert data["ok"] is True
    assert data["method"]["version"] == 2
    assert data["impact"]["afterCount"] == 3  # Two rests plus one END.
    assert data["versionDiff"]["baseVersion"] == 1
    assert data["versionDiff"]["headVersion"] == 2
    assert "1개 값 변경" in data["versionDiff"]["headline"]
    assert any("1분" in line and "30분" in line for line in data["versionDiff"]["lines"])
    assert data["versionDiff"]["metadataChanges"] == ["설명 변경"]
    assert project == original
    assert files == {path: path.read_bytes() for path in store.root.rglob("*.json")}


def test_specific_old_version_load_is_pinned_and_undoes_as_one_change(resources, tmp_path):
    client, store = resources
    project = source_project()
    token = preview(client, project, version=1, replace=True, compareVersion=2).get_json()["token"]
    store.save(name="표준 휴지", method_id="standard", modules=[rest(7200)])
    model = WorkspaceModel(ProjectDocument(ScheduleProject.from_dict(project),
                                         autosave_dir=tmp_path / "recovery"), library=store)
    assert token == method_load_token(model.project.to_dict(), store.get("standard", 1), replace=True)
    before = model.project.to_dict()
    model.load_saved_method("standard", 1, replace=True, preview_token=token)
    assert len(model.project.modules) == 1
    assert model.project.modules[0].params["duration_s"] == 60
    assert model.project.cell_profile.nominal_capacity_mAh == 80
    assert model.document.can_undo
    model.document.undo()
    assert model.project.to_dict() == before
    assert not model.document.can_undo


@pytest.mark.parametrize("value", [True, False, 1.5, 0, -1, "x", "1.5", [], {}])
def test_invalid_method_version_is_a_client_error(resources, value):
    client, _ = resources
    assert preview(client, version=value).status_code == 400
    response = client.post("/api/edit/loadMethod", json={
        "project": source_project(), "args": {"methodId": "standard", "version": value},
    })
    assert response.status_code == 400


def test_missing_versions_and_invalid_flags_are_not_silently_coerced(resources):
    client, _ = resources
    assert preview(client, version=999).status_code == 404
    assert preview(client, compareVersion=999).status_code == 404
    for options in ({"replace": "false"}, {"preview": "false"}):
        assert preview(client, **options).status_code == 400
    assert preview(client, version=1).get_json()["versionDiff"] is None


@pytest.mark.parametrize("mutation", ["project", "method", "mode"])
def test_stale_method_load_is_rejected_atomically(resources, mutation):
    client, store = resources
    project = source_project()
    token = preview(client, project, version=1).get_json()["token"]
    if mutation == "project":
        project["cell_profile"]["nominal_capacity_mAh"] = 81
    if mutation == "method":
        path = store.get("standard", 1).path
        raw = json.loads(path.read_text())
        raw["modules"][0]["params"]["duration_s"] = 120
        path.write_text(json.dumps(raw), encoding="utf-8")
    original = copy.deepcopy(project)
    response = client.post("/api/edit/loadMethod", json={"project": project, "args": {
        "methodId": "standard", "version": 1, "replace": mutation == "mode", "previewToken": token,
    }})
    assert response.status_code == 400
    assert "다시 미리보기" in response.get_json()["error"]
    assert project == original


@pytest.mark.parametrize("identifier", ["../outside", "/tmp/outside", "..", "a/b", "a\\b", "C:drive", ""])
def test_method_paths_cannot_escape_library(tmp_path, identifier):
    store = MethodLibrary(tmp_path / "library")
    with pytest.raises(ValueError):
        store.versions(identifier)
    if identifier:
        with pytest.raises(ValueError):
            store.save(name="invalid", modules=[rest(60)], method_id=identifier)


def test_symlinks_cannot_load_external_method_versions(tmp_path):
    store = MethodLibrary(tmp_path / "library")
    entry = store.save(name="one", modules=[rest(60)])
    outside = tmp_path / "outside"
    outside.mkdir()
    (store.root / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        store.versions("escape")
    (entry.path.parent / "v0002.json").symlink_to(entry.path)
    assert store.versions(entry.method_id) == (entry,)
    assert store.methods() == (entry,)


def test_concurrent_saves_never_overwrite_a_version(tmp_path, monkeypatch):
    from pne_scheduler import library as module

    store = MethodLibrary(tmp_path / "library")
    original_write = module._atomic_write
    barrier = threading.Barrier(8)
    state = threading.local()

    def synchronized_write(path, text):
        if not getattr(state, "started", False):
            state.started = True
            barrier.wait(timeout=10)
        return original_write(path, text)

    monkeypatch.setattr(module, "_atomic_write", synchronized_write)
    def save(index):
        return store.save(name="shared", method_id="shared", modules=[rest(index + 1)])
    with ThreadPoolExecutor(max_workers=8) as workers:
        saved = list(workers.map(save, range(8)))
    assert sorted(entry.version for entry in saved) == list(range(1, 9))
    assert {entry.modules[0]["params"]["duration_s"] for entry in store.versions("shared")} == set(range(1, 9))
    assert len(list(store.root.rglob("*.json"))) == 8
    assert not list(store.root.rglob("*.tmp"))


def test_sampling_dcir_and_reset_changes_are_visible_in_step_comparison():
    before = StepIntent("rest", end_time_s=60, record_time_s=1)
    after = StepIntent("rest", end_time_s=60, record_time_s=2,
                       record_dV_mV=5, dcr_start_s=0, dcr_end_s=10, loop_reset_capacity=True)
    fields = {change.field for change in diff_steps([before], [after]).changes[0].fields}
    assert {"record_time_s", "record_dV_mV", "dcr_start_s", "dcr_end_s", "loop_reset_capacity"} <= fields


def test_adding_same_kind_step_does_not_misreport_an_existing_step_change():
    before = [StepIntent("rest", end_time_s=60), StepIntent("end")]
    after = [StepIntent("rest", end_time_s=60), StepIntent("rest", end_time_s=1800), StepIntent("end")]
    diff = diff_steps(before, after)
    assert (diff.added, diff.removed, diff.modified) == (1, 0, 0)
    assert diff.changes[0].after_index == 2
    reverse = diff_steps(after, before)
    assert (reverse.added, reverse.removed, reverse.modified) == (0, 1, 0)
    assert reverse.changes[0].before_index == 2


def storage_row(**changes):
    return {"id": "cell_01", "sample": "Cell 01", "temperatureC": 45,
            "startedAt": (NOW - timedelta(days=15)).isoformat(), "targetDays": 30,
            "checkpointDays": [7, 14], "notifyEnabled": True, **changes}


def test_archive_restore_preserves_alert_history_and_original_notification_choice(tmp_path):
    store = StorageStore(tmp_path / "storage.sqlite3")
    record = store.add(storage_row(), now=NOW)
    first, second, _ = record["alerts"]
    store.acknowledge_alert(record["id"], first["id"], now=NOW)
    store.snooze_alert(record["id"], second["id"], (NOW + timedelta(hours=2)).isoformat(), now=NOW)
    before = store.list_records()[0]
    store.set_archived(record["id"], True, now=NOW)
    store.set_archived(record["id"], True, now=NOW + timedelta(minutes=1))
    assert store.list_records() == []
    archived = StorageStore(store.path).list_records(include_archived=True)[0]
    assert archived["alerts"] == before["alerts"]
    assert archived["dueAt"] == before["dueAt"]
    assert archived["notifyEnabled"] is False
    assert archived["notifyBeforeArchive"] is True
    assert len(archived["archiveHistory"]) == 1
    assert store.claim_due(now=NOW + timedelta(days=20)) == []
    with pytest.raises(ValueError, match="복원"):
        store.set_notifications(record["id"], True)
    store.set_archived(record["id"], False, now=NOW + timedelta(minutes=2))
    restored = store.list_records()[0]
    assert restored["notifyEnabled"] is True
    assert restored["alerts"] == before["alerts"]
    assert [event["action"] for event in restored["archiveHistory"]] == ["archived", "restored"]
    assert process_due(store, lambda *_: None, now=NOW + timedelta(hours=3)) == 1


def test_archiving_does_not_reenable_opted_out_notifications(tmp_path):
    store = StorageStore(tmp_path / "storage.sqlite3")
    store.add(storage_row(notifyEnabled=False), now=NOW)
    store.set_archived("cell_01", True, now=NOW)
    store.set_archived("cell_01", False, now=NOW)
    assert store.list_records()[0]["notifyEnabled"] is False
    assert store.claim_due(now=NOW) == []


def test_archive_after_claim_is_rechecked_before_sending(tmp_path, monkeypatch):
    store = StorageStore(tmp_path / "storage.sqlite3")
    store.add(storage_row(), now=NOW)
    claim = store.claim_due
    def archive_after_claim(**kwargs):
        alerts = claim(**kwargs)
        store.set_archived("cell_01", True, now=NOW)
        return alerts
    monkeypatch.setattr(store, "claim_due", archive_after_claim)
    assert process_due(store, lambda *_: pytest.fail("archived record sent an alert"), now=NOW) == 0
    assert all(alert["notifiedAt"] is None for alert in store.list_records(include_archived=True)[0]["alerts"])


def test_old_storage_database_migrates_without_losing_records(tmp_path):
    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE storage_records (
            id TEXT PRIMARY KEY, sample TEXT NOT NULL, temperature_c REAL NOT NULL,
            started_at TEXT NOT NULL, target_days REAL NOT NULL, due_at TEXT NOT NULL,
            notify_enabled INTEGER NOT NULL DEFAULT 0, completed_at TEXT,
            notified_at TEXT, claim_at TEXT, checkpoint_days TEXT NOT NULL DEFAULT '[]')""")
        connection.execute("""INSERT INTO storage_records
            (id, sample, temperature_c, started_at, target_days, due_at)
            VALUES ('legacy', 'old sample', 45, '2026-10-01T00:00:00Z', 30, '2026-10-31T00:00:00Z')""")
    store = StorageStore(path)
    assert store.list_records()[0]["sample"] == "old sample"
    assert store.list_records()[0]["archivedAt"] is None
    store.set_archived("legacy", True, now=NOW)
    assert len(store.list_records(include_archived=True)) == 1


def test_storage_archive_api_is_reversible_and_rejects_invalid_flags(tmp_path):
    client = create_app(tmp_path / "library", tmp_path / "storage.sqlite3").test_client()
    created = client.post("/api/storage", json=storage_row()).get_json()["record"]
    url = f"/api/storage/{created['id']}/archive"
    assert client.post(url, json={"archived": "false"}).status_code == 400
    assert client.post("/api/storage/missing/archive", json={"archived": True}).status_code == 404
    assert client.post(url, json={"archived": True}).status_code == 200
    assert client.post(f"/api/storage/{created['id']}/notifications", json={"enabled": True}).status_code == 400
    assert client.post("/api/storage/missing/notifications", json={"enabled": True}).status_code == 404
    assert client.get("/api/storage").get_json()["records"] == []
    assert len(client.get("/api/storage?includeArchived=true").get_json()["records"]) == 1
    assert client.post(url, json={"archived": False}).status_code == 200
    assert client.get("/api/storage").get_json()["records"][0]["archivedAt"] is None


def test_schema_upgrade_is_safe_for_concurrent_api_and_companion_access(tmp_path):
    path = tmp_path / "upgrade.sqlite3"
    # The database predates both the checkpoints and archive columns.
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE storage_records (
            id TEXT PRIMARY KEY, sample TEXT NOT NULL, temperature_c REAL NOT NULL,
            started_at TEXT NOT NULL, target_days REAL NOT NULL, due_at TEXT NOT NULL,
            notify_enabled INTEGER NOT NULL DEFAULT 0, completed_at TEXT,
            notified_at TEXT, claim_at TEXT)""")
    barrier = threading.Barrier(8)
    def read(_):
        barrier.wait(timeout=10)
        return StorageStore(path).list_records(include_archived=True)
    with ThreadPoolExecutor(max_workers=8) as workers:
        assert list(workers.map(read, range(8))) == [[]] * 8
    store = StorageStore(path)
    assert store.add(storage_row(), now=NOW)["sample"] == "Cell 01"
    store.set_archived("cell_01", True, now=NOW)
    assert store.list_records(include_archived=True)[0]["archivedAt"]
