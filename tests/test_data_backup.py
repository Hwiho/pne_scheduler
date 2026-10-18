"""Real isolated file/DB round trips; no GUI, personal data or notifications."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import sqlite3
import stat
import zipfile

import pytest

from pne_scheduler.data_backup import DataManager, _database_rows
from pne_scheduler.data_safety import publish_new_directory
from pne_scheduler.ui.native_controller import NativeController


@pytest.fixture
def sample(tmp_path):
    c = NativeController(data_dir=tmp_path / "data")
    c.edit("addModule", {"moduleType": "rest"})
    c.save(tmp_path / "external.schproj")
    c.edit("setProjectName", {"name": "unsaved"})
    c.save_method("test method")
    record = c.storage.add({"sample": "test cell", "temperatureC": 45, "targetDays": 30,
                            "startedAt": "2025-01-01T00:00:00Z", "notifyEnabled": True, "checkpointDays": [7, 14]})
    c.storage.acknowledge_alert(record["id"], record["alerts"][0]["id"])
    c.storage.set_archived(record["id"], True)
    c.storage.set_archived(record["id"], False)
    return c, DataManager(c.storage, c.library.root, c.autosave_dir)


def make_backup(tmp_path, c, manager):
    paths = [str(tmp_path / "external.schproj")]
    plan = manager.preview_backup(paths, c.project)
    archive = tmp_path / "backup.zip"
    manager.create_backup(archive, plan["token"], paths=paths, current_project=c.project, external_writes_stopped=True)
    return archive


def test_verified_roundtrip_preserves_history_and_pauses_restore(sample, tmp_path):
    c, m = sample
    source = c.storage.list_records(include_archived=True)
    archive = make_backup(tmp_path, c, m)
    inspection = m.inspect_backup(archive)
    target = tmp_path / "restored"
    m.restore_backup(archive, target, inspection["token"])
    restored = NativeController(data_dir=target)
    rows = restored.storage.list_records(include_archived=True)
    assert len(rows) == len(source) == 1
    assert rows[0]["alerts"] == source[0]["alerts"]
    assert rows[0]["archiveHistory"] == source[0]["archiveHistory"]
    assert rows[0]["notifyEnabled"] is False
    assert restored.storage.claim_due() == []
    assert restored.data_action("status")["companion"]["restorePaused"]
    assert restored.data_action("status")["companion"]["pendingCount"] == 2
    recovery = json.loads(next((target / "recovery").glob("autosave-*.json")).read_text())
    assert recovery["source_path"] is None and recovery["backup_original_source_path"]
    assert len(list((target / "projects").glob("*.schproj"))) == 2
    assert len(restored.library.methods()) == 1
    with pytest.raises(ValueError):
        restored.data_action("resumeNotifications")
    resumed = restored.data_action("resumeNotifications", {"confirmed": True})
    assert not resumed["companion"]["active"] and not resumed["companion"]["restorePaused"]
    assert restored.storage.list_records()[0]["notifyEnabled"]
    assert c.storage.list_records(include_archived=True) == source


def test_snapshot_sees_committed_wal_and_fences_legacy_writes(sample, tmp_path, monkeypatch):
    c, m = sample
    with closing(sqlite3.connect(c.storage.path)) as writer:
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("UPDATE storage_records SET sample='WAL cell'")
        writer.commit()
        assert c.storage.path.with_name(c.storage.path.name + "-wal").exists()
        original = m.inspect_backup
        def check(path):
            with closing(sqlite3.connect(c.storage.path, timeout=.05)) as other:
                with pytest.raises(sqlite3.OperationalError, match="locked"):
                    other.execute("UPDATE storage_records SET sample='concurrent'")
            return original(path)
        monkeypatch.setattr(m, "inspect_backup", check)
        archive = make_backup(tmp_path, c, m)
    _manifest, _payloads, rows, _hash = m._read_archive(archive)
    columns, values = rows["storage_records"]
    assert values[0][columns.index("sample")] == "WAL cell"


def test_stale_preview_and_existing_outputs_never_overwrite(sample, tmp_path):
    c, m = sample
    plan = m.preview_backup(current_project=c.project)
    c.edit("setProjectName", {"name": "changed"})
    with pytest.raises(ValueError, match="미리보기"):
        m.create_backup(tmp_path / "none.zip", plan["token"], current_project=c.project, external_writes_stopped=True)
    assert not (tmp_path / "none.zip").exists()
    archive = make_backup(tmp_path, c, m)
    original = archive.read_bytes()
    with pytest.raises(ValueError):
        m.create_backup(archive, plan["token"], external_writes_stopped=True)
    assert archive.read_bytes() == original
    target = tmp_path / "existing"
    target.mkdir()
    with pytest.raises(ValueError):
        m.restore_backup(archive, target, m.inspect_backup(archive)["token"])
    assert list(target.iterdir()) == []


@pytest.mark.parametrize("failure", ["mutation", "disk-full", "publish"])
def test_failed_creation_never_publishes_partial_archive(sample, tmp_path, monkeypatch, failure):
    c, m = sample
    plan = m.preview_backup([str(tmp_path / "external.schproj")])
    def fail(*args, **kwargs):
        raise OSError("disk full")
    if failure == "mutation":
        original = m.inspect_backup
        def mutate(path):
            result = original(path)
            (tmp_path / "external.schproj").write_text(json.dumps(c.project))
            return result
        monkeypatch.setattr(m, "inspect_backup", mutate)
    elif failure == "disk-full":
        monkeypatch.setattr(zipfile.ZipFile, "writestr", fail)
    else:
        monkeypatch.setattr("pne_scheduler.data_backup.os.link", fail)
    with pytest.raises((ValueError, OSError)):
        m.create_backup(tmp_path / "partial.zip", plan["token"], paths=[str(tmp_path / "external.schproj")], external_writes_stopped=True)
    assert not (tmp_path / "partial.zip").exists()
    assert not list(tmp_path.glob(".pne-backup-*"))


def mutate_zip(archive, mutation):
    with zipfile.ZipFile(archive) as z:
        entries = {i.filename: z.read(i) for i in z.infolist()}
    mutation(entries)
    with zipfile.ZipFile(archive, "w") as z:
        for name, raw in entries.items():
            z.writestr(name, raw)


@pytest.mark.parametrize("path", ["../escape", "/absolute", "C:/drive", "x\\y", "projects/CON.schproj", "projects/foo. ", "MANIFEST.json"])
def test_unsafe_archive_paths_are_rejected(sample, tmp_path, path):
    c, m = sample
    archive = make_backup(tmp_path, c, m)
    mutate_zip(archive, lambda entries: entries.update({path: b"bad"}))
    with pytest.raises(ValueError):
        m.inspect_backup(archive)
    assert not (tmp_path / "escape").exists()


@pytest.mark.parametrize("kind", ["hash", "missing", "future", "symlink", "limit", "corrupt-db", "trigger"])
def test_corrupt_or_unsupported_backup_fails_before_restore(sample, tmp_path, monkeypatch, kind):
    c, m = sample
    archive = make_backup(tmp_path, c, m)
    def mutation(entries):
        manifest = json.loads(entries["manifest.json"])
        if kind == "hash":
            entries["projects/current.schproj"] += b" "
        elif kind == "missing":
            del entries["projects/current.schproj"]
        elif kind == "future":
            manifest["schema"] = "pne_scheduler.backup/v999"
        elif kind in {"corrupt-db", "trigger"}:
            raw = b"not a database"
            if kind == "trigger":
                db = tmp_path / "injected.sqlite3"
                db.write_bytes(entries["storage.sqlite3"])
                with closing(sqlite3.connect(db)) as conn:
                    conn.execute("CREATE TRIGGER evil AFTER INSERT ON storage_records BEGIN DELETE FROM storage_records; END")
                raw = db.read_bytes()
            entries["storage.sqlite3"] = raw
            item = next(f for f in manifest["files"] if f["path"] == "storage.sqlite3")
            item.update(size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        entries["manifest.json"] = json.dumps(manifest).encode()
    mutate_zip(archive, mutation)
    if kind == "symlink":
        with zipfile.ZipFile(archive, "a") as z:
            info = zipfile.ZipInfo("projects/link.schproj")
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(info, "target")
    if kind == "limit":
        monkeypatch.setattr("pne_scheduler.data_backup.MAX_TOTAL_BYTES", 10)
    with pytest.raises((ValueError, sqlite3.DatabaseError)):
        m.restore_backup(archive, tmp_path / "must-not-exist", "invalid")
    assert not (tmp_path / "must-not-exist").exists()


def test_directory_publication_never_replaces_empty_target(tmp_path):
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "kept").write_text("original")
    with pytest.raises(OSError):
        publish_new_directory(source, target)
    assert (source / "kept").read_text() == "original"
    assert list(target.iterdir()) == []


def test_api_and_native_use_same_actions(sample, tmp_path):
    pytest.importorskip("flask")
    from pne_scheduler.api.app import create_app
    c, m = sample
    client = create_app(c.library.root, c.storage.path, c.autosave_dir).test_client()
    native = c.data_action("backupPreview", {"includeCurrent": True})
    web = client.post("/api/data/backupPreview", json={"includeCurrent": True, "project": c.project})
    assert web.status_code == 200 and web.json["token"] == native["token"]
    assert client.post("/api/data/resumeNotifications", json={}).status_code == 400
    assert client.post("/api/data/backupCreate", json={"outputPath": str(tmp_path / "no.zip")}).status_code == 400
    assert _database_rows(c.storage.path)["storage_records"][1]


def test_busy_backup_is_http_conflict(sample, tmp_path):
    pytest.importorskip("flask")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from pne_scheduler.api.app import create_app
    from pne_scheduler.companion_control import notifier_lock
    from pne_scheduler.data_safety import file_lock
    c, _m = sample
    ready, release = Event(), Event()
    def holder():
        with file_lock(notifier_lock(c.storage)):
            ready.set()
            assert release.wait(10)
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(holder)
        assert ready.wait(5)
        try:
            client = create_app(c.library.root, c.storage.path, c.autosave_dir).test_client()
            assert client.post("/api/data/backupPreview", json={}).status_code == 409
        finally:
            release.set()
        future.result()


def test_failed_restore_cleans_staging_and_preserves_source(sample, tmp_path, monkeypatch):
    c, m = sample
    archive = make_backup(tmp_path, c, m)
    original = archive.read_bytes()
    before = c.storage.list_records(include_archived=True)
    token = m.inspect_backup(archive)["token"]
    def fail(source, target):
        raise OSError("disk unavailable")
    monkeypatch.setattr("pne_scheduler.data_backup.publish_new_directory", fail)
    with pytest.raises(OSError):
        m.restore_backup(archive, tmp_path / "failed", token)
    assert not (tmp_path / "failed").exists()
    assert not list(tmp_path.glob(".pne-restore-*"))
    assert archive.read_bytes() == original
    assert c.storage.list_records(include_archived=True) == before
