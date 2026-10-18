"""Windows file locks must be released without depending on garbage collection."""
from __future__ import annotations

import sqlite3

import pytest

from pne_scheduler.storage_records import StorageStore


@pytest.fixture
def tracked(monkeypatch):
    real_connect = sqlite3.connect
    # Retain strong references: these tests cannot accidentally pass because
    # refcounting/GC closed the handle for us.
    connections = []
    def connect(*args, **kwargs):
        connection = real_connect(*args, **kwargs)
        connections.append(connection)
        return connection
    monkeypatch.setattr(sqlite3, "connect", connect)
    return connections


def assert_closed(connections):
    assert connections
    for connection in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")


def test_storage_read_write_and_failure_close_handles(tmp_path, tracked):
    store = StorageStore(tmp_path / "storage.sqlite3")
    store.heartbeat()
    assert store.list_records() == []
    assert store.companion_status()
    with pytest.raises(ValueError):
        store.complete("not-a-record", completed=True)
    assert_closed(tracked)
    # On Windows this rename used to fail until the interpreter collected DBs.
    store.path.rename(tmp_path / "renamed.sqlite3")


def test_schema_failure_also_closes_connection(tmp_path, tracked, monkeypatch):
    store = StorageStore(tmp_path / "storage.sqlite3")
    def broken(_connection):
        raise RuntimeError("migration unavailable")
    monkeypatch.setattr(store, "_initialize", broken)
    with pytest.raises(RuntimeError, match="migration unavailable"):
        store.list_records()
    assert_closed(tracked)


def test_failed_operation_rolls_back_before_close(tmp_path, tracked):
    store = StorageStore(tmp_path / "storage.sqlite3")
    with pytest.raises(RuntimeError, match="abort"):
        with store._connect() as connection:
            connection.execute("INSERT INTO storage_meta VALUES ('test', 'not-committed')")
            raise RuntimeError("abort")
    with store._connect() as connection:
        assert connection.execute("SELECT * FROM storage_meta WHERE key='test'").fetchone() is None
    assert_closed(tracked)
