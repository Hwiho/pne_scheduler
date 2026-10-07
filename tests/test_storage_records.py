"""Local storage record persistence and notifier contracts."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from pne_scheduler.storage_companion import process_due
from pne_scheduler.storage_records import StorageStore

NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def row(**changes):
    return {"id": "cell_01", "sample": "Cell 01", "temperatureC": 45,
            "startedAt": (NOW - timedelta(days=2)).isoformat(),
            "targetDays": 1, "notifyEnabled": True, **changes}


def test_notification_toggle_preserves_schedule_and_acknowledgements(tmp_path):
    store = StorageStore(tmp_path / "storage.sqlite3")
    record = store.add(row(notifyEnabled=False), now=NOW)
    alert_id = record["alerts"][0]["id"]
    store.acknowledge_alert(record["id"], alert_id, now=NOW)
    before = store.list_records()[0]
    store.set_notifications(record["id"], True)
    after = store.list_records()[0]
    assert after["notifyEnabled"] is True
    assert after["dueAt"] == before["dueAt"]
    assert after["alerts"] == before["alerts"]
    store.set_notifications(record["id"], False)
    assert store.list_records()[0]["notifyEnabled"] is False
    assert store.claim_due(now=NOW) == []
    with pytest.raises(ValueError):
        store.set_notifications(record["id"], "false")
    with pytest.raises(ValueError):
        store.set_notifications("missing", True)


def test_persistence_due_and_once(tmp_path):
    path = tmp_path / "storage.sqlite3"
    store = StorageStore(path)
    store.add(row(), now=NOW)
    assert len(StorageStore(path).list_records()) == 1
    notices = []
    assert process_due(store, lambda title, message: notices.append((title, message)), now=NOW) == 1
    assert "Cell 01" in notices[0][1]
    assert process_due(store, lambda *_: pytest.fail("duplicate alert"), now=NOW) == 0
    assert store.list_records()[0]["notifiedAt"] is not None


def test_checkpoint_and_final_alerts_are_independent(tmp_path):
    store = StorageStore(tmp_path / "storage.sqlite3")
    store.add(row(startedAt=(NOW - timedelta(days=15)).isoformat(), targetDays=30,
                  checkpointDays=[14, 7]), now=NOW)
    record = store.list_records()[0]
    assert record["checkpointDays"] == [7.0, 14.0]
    assert [alert["kind"] for alert in record["alerts"]] == ["checkpoint", "checkpoint", "final"]

    notices = []
    assert process_due(store, lambda title, message: notices.append((title, message)), now=NOW) == 2
    assert {message.rsplit(" ", 1)[-1] for _, message in notices} == {"7일", "14일"}
    assert process_due(store, lambda *_: pytest.fail("duplicate checkpoint"), now=NOW) == 0
    assert process_due(store, lambda title, message: notices.append((title, message)),
                       now=NOW + timedelta(days=15)) == 1
    assert "최종 목표" in notices[-1][0]


def test_acknowledge_and_snooze_alert(tmp_path):
    store = StorageStore(tmp_path / "storage.sqlite3")
    store.add(row(checkpointDays=[0.5]), now=NOW)
    checkpoint, final = store.list_records()[0]["alerts"]

    store.acknowledge_alert("cell_01", checkpoint["id"], now=NOW)
    assert process_due(store, lambda *_: None, now=NOW) == 1
    store.snooze_alert("cell_01", final["id"], (NOW + timedelta(hours=2)).isoformat(), now=NOW)
    assert process_due(store, lambda *_: pytest.fail("snoozed alert sent early"),
                       now=NOW + timedelta(hours=1)) == 0
    assert process_due(store, lambda *_: None, now=NOW + timedelta(hours=2)) == 1


def test_failed_send_retries_and_completed_does_not_alert(tmp_path):
    store = StorageStore(tmp_path / "storage.sqlite3")
    store.add(row(), now=NOW)

    def fail(*_):
        raise OSError("notifications disabled")

    assert process_due(store, fail, now=NOW) == 0
    assert store.list_records()[0]["notifiedAt"] is None
    store.complete("cell_01", completed=True, now=NOW)
    assert process_due(store, lambda *_: pytest.fail("completed alerted"), now=NOW) == 0
    store.complete("cell_01", completed=False, now=NOW)
    assert process_due(store, lambda *_: None, now=NOW) == 1


def test_legacy_import_idempotent_atomic_and_opt_out(tmp_path):
    store = StorageStore(tmp_path / "storage.sqlite3")
    imported = store.import_legacy([row()], now=NOW)
    assert imported == {"inserted": 1, "alreadyPresent": 0}
    assert store.import_legacy([row()], now=NOW) == {"inserted": 0, "alreadyPresent": 1}
    assert store.list_records()[0]["notifyEnabled"] is False
    with pytest.raises(ValueError, match="충돌"):
        store.import_legacy([row(sample="Different")], now=NOW)
    assert store.list_records()[0]["sample"] == "Cell 01"


def test_heartbeat_and_validation(tmp_path):
    store = StorageStore(tmp_path / "storage.sqlite3")
    assert store.companion_status(now=NOW)["active"] is False
    store.heartbeat(now=NOW)
    assert store.companion_status(now=NOW)["active"] is True
    assert store.companion_status(now=NOW + timedelta(minutes=4))["active"] is False
    with pytest.raises(ValueError, match="미래"):
        store.add(row(startedAt=(NOW + timedelta(days=1)).isoformat()), now=NOW)
    with pytest.raises(ValueError, match="기간"):
        store.add(row(targetDays=0), now=NOW)
    with pytest.raises(ValueError, match="최종 목표일 미만"):
        store.add(row(targetDays=14, checkpointDays=[7, 14]), now=NOW)


def test_existing_database_schema_is_migrated(tmp_path):
    path = tmp_path / "storage.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE storage_records (
            id TEXT PRIMARY KEY, sample TEXT NOT NULL, temperature_c REAL NOT NULL,
            started_at TEXT NOT NULL, target_days REAL NOT NULL, due_at TEXT NOT NULL,
            notify_enabled INTEGER NOT NULL DEFAULT 0, completed_at TEXT,
            notified_at TEXT, claim_at TEXT
        )""")
        connection.execute("""INSERT INTO storage_records VALUES
            ('old', 'Old cell', 45, ?, 1, ?, 1, NULL, ?, NULL)""", (
            (NOW - timedelta(days=2)).isoformat(),
            (NOW - timedelta(days=1)).isoformat(), NOW.isoformat(),
        ))
    record = StorageStore(path).list_records()[0]
    assert record["checkpointDays"] == []
    assert len(record["alerts"]) == 1
    assert record["alerts"][0]["kind"] == "final"
    assert record["notifiedAt"] is not None


def test_api_storage_flow(tmp_path):
    pytest.importorskip("flask")
    from pne_scheduler.api.app import create_app

    client = create_app(tmp_path / "library", tmp_path / "storage.sqlite3").test_client()
    empty = client.get("/api/storage").get_json()
    assert empty["records"] == []
    created = client.post("/api/storage", json=row(checkpointDays=[0.5])).get_json()
    assert created["ok"] is True
    listed = client.get("/api/storage").get_json()["records"][0]
    assert listed["sample"] == "Cell 01"
    assert listed["checkpointDays"] == [0.5]
    assert [alert["kind"] for alert in listed["alerts"]] == ["checkpoint", "final"]
    alert_id = listed["alerts"][0]["id"]
    assert client.post(f"/api/storage/cell_01/alerts/{alert_id}/acknowledge", json={}).status_code == 200
    final_id = listed["alerts"][1]["id"]
    until = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    assert client.post(f"/api/storage/cell_01/alerts/{final_id}/snooze",
                       json={"until": until}).status_code == 200
    assert client.post("/api/storage/cell_01/complete", json={"completed": True}).status_code == 200
    assert client.get("/api/storage").get_json()["records"][0]["completedAt"] is not None
    assert client.post("/api/storage", json=row(targetDays=0)).status_code == 400
