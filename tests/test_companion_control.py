"""Cooperative stop with real process locks, never real Windows notifications."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys
import time

import pytest

from pne_scheduler.companion_control import companion_status, notifier_lock, request_stop
from pne_scheduler.data_backup import DataManager
from pne_scheduler.data_safety import ResourceBusyError, file_lock, is_locked
from pne_scheduler.storage_companion import process_due, run_companion
from pne_scheduler.storage_records import StorageStore


def until(predicate):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.03)
    pytest.fail("Timed out waiting for isolated test process")


@contextmanager
def child(code, path):
    process = subprocess.Popen([sys.executable, "-c", code, str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               cwd=Path(__file__).resolve().parents[2], text=True)
    try:
        yield process
    finally:
        if process.poll() is None:
            process.terminate()  # only this explicitly owned silent test process
        out, err = process.communicate(timeout=8)
        if process.returncode not in (0, -15, 1):
            pytest.fail(f"Test process failed: {out} {err}")


SILENT = """
import sys
from pathlib import Path
from pne_scheduler.storage_records import StorageStore
from pne_scheduler.storage_companion import run_companion
run_companion(StorageStore(Path(sys.argv[1])), notify=lambda *args: None, poll_seconds=3600)
"""

BALLOON_WAIT = """
import sys
from pathlib import Path
from pne_scheduler.storage_records import StorageStore
import pne_scheduler.storage_companion as companion
store = StorageStore(Path(sys.argv[1]))
def silent_balloon(title, message, wait):
    store.update_runtime({'testBalloonEntered': '1'})
    wait(3600)
companion.send_windows_balloon = silent_balloon
companion.run_companion(store, poll_seconds=3600)
"""


@pytest.mark.parametrize("code", [SILENT, BALLOON_WAIT])
def test_safe_stop_interrupts_long_wait_and_allows_restart(tmp_path, code):
    store = StorageStore(tmp_path / "storage.sqlite3")
    if code == BALLOON_WAIT:
        store.add({"sample": "silent", "temperatureC": 45, "targetDays": 1,
                   "startedAt": "2025-01-01T00:00:00Z", "notifyEnabled": True})
    with child(code, store.path) as process:
        until(lambda: companion_status(store)["state"] == "running")
        if code == BALLOON_WAIT:
            until(lambda: store.runtime_meta().get("testBalloonEntered"))
        status = companion_status(store)
        assert status["lockHeld"] and not status["backupReady"]
        with pytest.raises(ResourceBusyError):
            DataManager(store, tmp_path / "library", tmp_path / "recovery").preview_backup()
        old_run = status["runId"]
        start = time.monotonic()
        request_stop(store, old_run)
        assert process.wait(timeout=5) == 0
        assert time.monotonic() - start < 5
        done = companion_status(store)
        assert done["state"] == "stopped" and done["backupReady"] and not done["lockHeld"]
    with child(SILENT, store.path) as process:
        until(lambda: companion_status(store)["state"] == "running")
        status = companion_status(store)
        assert status["runId"] != old_run
        with pytest.raises(ValueError, match="바뀌"):
            request_stop(store, old_run)
        request_stop(store, status["runId"])
        assert process.wait(timeout=5) == 0


def test_legacy_lock_stale_heartbeat_cannot_be_deleted_or_claimed_stopped(tmp_path):
    store = StorageStore(tmp_path / "db.sqlite3")
    code = """
import sys,time
from pathlib import Path
from pne_scheduler.data_safety import file_lock
with file_lock(Path(sys.argv[1])):
    print('ready', flush=True)
    time.sleep(60)
"""
    lock = notifier_lock(store)
    with child(code, lock) as process:
        assert process.stdout.readline().strip() == "ready"
        assert is_locked(lock)
        status = companion_status(store)
        assert status["state"] == "unresponsive" and not status["backupReady"]
        with pytest.raises(ValueError):
            request_stop(store, "")
        with pytest.raises(ResourceBusyError):
            DataManager(store, tmp_path / "library", tmp_path / "recovery").preview_backup()
    assert lock.exists() and not is_locked(lock)


def test_reentrant_lock_and_other_thread_exclusion(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path = tmp_path / "lock"
    with file_lock(path), file_lock(path), ThreadPoolExecutor(1) as pool:
        assert pool.submit(is_locked, path).result() is True
    assert not is_locked(path)


def test_stop_polling_is_read_only_after_schema_creation(tmp_path, monkeypatch):
    store = StorageStore(tmp_path / "db.sqlite3")
    store.update_runtime({"companionRunId": "example"})
    monkeypatch.setattr(store, "_initialize", lambda c: pytest.fail("Polling reinitialized/backfilled the database"))
    for _ in range(10):
        assert store.runtime_meta()["companionRunId"] == "example"


def test_restore_pause_blocks_runtime_and_claims(tmp_path):
    store = StorageStore(tmp_path / "db.sqlite3")
    store.update_runtime({"restoreNotificationsPaused": "1"})
    store.add({"sample": "silent", "temperatureC": 45, "targetDays": 1,
               "startedAt": "2025-01-01T00:00:00Z", "notifyEnabled": True})
    with pytest.raises(ValueError, match="검토"):
        run_companion(store, notify=lambda *args: pytest.fail("Notification sent"))
    assert store.claim_due() == [] and not is_locked(notifier_lock(store))


def test_stop_between_batch_items_releases_unprocessed_claims(tmp_path):
    store = StorageStore(tmp_path / "db.sqlite3")
    for i in range(3):
        store.add({"sample": str(i), "temperatureC": 45, "targetDays": 1,
                   "startedAt": "2025-01-01T00:00:00Z", "notifyEnabled": True})
    sent = []
    assert process_due(store, lambda *args: sent.append(args), checkpoint=lambda: bool(sent)) == 1
    assert len(store.claim_due()) == 2


def test_start_reservation_prevents_duplicate_and_cleans_launch_failure(tmp_path, monkeypatch):
    import pne_scheduler.companion_control as control
    store = StorageStore(tmp_path / "db.sqlite3")
    monkeypatch.setattr(control.sys, "platform", "win32")
    monkeypatch.setattr("pne_scheduler.desktop_runtime.companion_command", lambda path: ["test-no-launch"])
    calls = []
    monkeypatch.setattr(control.subprocess, "Popen", lambda *a, **kw: calls.append((a, kw)))
    result = control.start_companion(store)
    assert result["state"] == "starting" and len(calls) == 1
    with pytest.raises(ValueError):
        control.start_companion(store)
    assert len(calls) == 1
    store.update_runtime({"companionState": "stopped"})
    def fail(*a, **kw):
        raise OSError("missing runtime")
    monkeypatch.setattr(control.subprocess, "Popen", fail)
    with pytest.raises(OSError):
        control.start_companion(store)
    assert companion_status(store)["state"] == "interrupted"
    assert "missing runtime" in companion_status(store)["lastError"]
