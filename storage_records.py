"""Persistent high-temperature storage records shared by web and Windows companion."""

from __future__ import annotations

import math
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
DAY_SECONDS = 86_400


def default_storage_db() -> Path:
    return Path.home() / ".pne_scheduler" / "storage.sqlite3"


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_time(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{label}은(는) 시간대가 포함된 시각이어야 합니다.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} 시각을 읽을 수 없습니다.") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label}에 시간대가 없습니다.")
    return parsed.astimezone(timezone.utc)


def _validated(raw: dict[str, Any], *, now: datetime, imported: bool) -> dict[str, Any]:
    record_id = str(raw.get("id") or ("" if imported else uuid.uuid4().hex))
    if not ID_PATTERN.fullmatch(record_id):
        raise ValueError("보관 기록 ID가 올바르지 않습니다.")
    sample = str(raw.get("sample", "")).strip()
    if not 1 <= len(sample) <= 120:
        raise ValueError("시료명은 1–120자여야 합니다.")
    try:
        temperature = float(raw.get("temperatureC"))
        days = float(raw.get("targetDays"))
    except (ValueError, TypeError) as exc:
        raise ValueError("온도와 목표 일수는 숫자여야 합니다.") from exc
    if not math.isfinite(temperature) or not -100 <= temperature <= 300:
        raise ValueError("온도는 -100–300°C 범위여야 합니다.")
    if not math.isfinite(days) or not 0 < days <= 3650:
        raise ValueError("목표 기간은 0 초과 3650일 이하여야 합니다.")
    started = _parse_time(raw.get("startedAt"), "시작")
    if started > now:
        raise ValueError("시작 시각은 미래일 수 없습니다.")
    due = started + timedelta(seconds=days * DAY_SECONDS)
    notify_enabled = raw.get("notifyEnabled", False)
    if not isinstance(notify_enabled, bool):
        raise ValueError("알림 설정은 true 또는 false여야 합니다.")
    return {
        "id": record_id,
        "sample": sample,
        "temperatureC": temperature,
        "startedAt": _utc_iso(started),
        "targetDays": days,
        "dueAt": _utc_iso(due),
        "notifyEnabled": notify_enabled,
    }


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "sample": row["sample"],
        "temperatureC": row["temperature_c"],
        "startedAt": row["started_at"],
        "targetDays": row["target_days"],
        "dueAt": row["due_at"],
        "notifyEnabled": bool(row["notify_enabled"]),
        "completedAt": row["completed_at"],
        "notifiedAt": row["notified_at"],
    }


class StorageStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("""CREATE TABLE IF NOT EXISTS storage_records (
            id TEXT PRIMARY KEY, sample TEXT NOT NULL, temperature_c REAL NOT NULL,
            started_at TEXT NOT NULL, target_days REAL NOT NULL, due_at TEXT NOT NULL,
            notify_enabled INTEGER NOT NULL DEFAULT 0, completed_at TEXT,
            notified_at TEXT, claim_at TEXT
        )""")
        connection.execute("""CREATE TABLE IF NOT EXISTS storage_meta (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        )""")
        return connection

    def list_records(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM storage_records ORDER BY completed_at IS NOT NULL, due_at, id"
            ).fetchall()
        return [_row_dict(row) for row in rows]

    def add(self, raw: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
        record = _validated(raw, now=now or datetime.now(timezone.utc), imported=False)
        try:
            with self._connect() as connection:
                connection.execute("""INSERT INTO storage_records
                    (id, sample, temperature_c, started_at, target_days, due_at, notify_enabled)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""", (
                    record["id"], record["sample"], record["temperatureC"],
                    record["startedAt"], record["targetDays"], record["dueAt"],
                    int(record["notifyEnabled"]),
                ))
        except sqlite3.IntegrityError as exc:
            raise ValueError("같은 보관 기록 ID가 이미 있습니다.") from exc
        return record

    def import_legacy(self, rows: Any, *, now: datetime | None = None) -> dict[str, int]:
        if not isinstance(rows, list) or not 1 <= len(rows) <= 1000:
            raise ValueError("가져올 브라우저 기록은 1–1000개여야 합니다.")
        moment = now or datetime.now(timezone.utc)
        prepared = [_validated(raw, now=moment, imported=True) for raw in rows if isinstance(raw, dict)]
        if len(prepared) != len(rows) or len({r["id"] for r in prepared}) != len(rows):
            raise ValueError("브라우저 기록에 잘못된 항목이나 중복 ID가 있습니다.")
        inserted = 0
        with self._connect() as connection:
            for record in prepared:
                previous = connection.execute("SELECT * FROM storage_records WHERE id=?", (record["id"],)).fetchone()
                if previous:
                    existing = _row_dict(previous)
                    keys = ("sample", "temperatureC", "startedAt", "targetDays", "dueAt")
                    if any(existing[key] != record[key] for key in keys):
                        raise ValueError(f"기록 ID 충돌: {record['id']}. 기존 기록은 덮어쓰지 않았습니다.")
                    continue
                connection.execute("""INSERT INTO storage_records
                    (id, sample, temperature_c, started_at, target_days, due_at, notify_enabled)
                    VALUES (?, ?, ?, ?, ?, ?, 0)""", (
                    record["id"], record["sample"], record["temperatureC"],
                    record["startedAt"], record["targetDays"], record["dueAt"],
                ))
                inserted += 1
        return {"inserted": inserted, "alreadyPresent": len(prepared) - inserted}

    def complete(self, record_id: str, *, completed: bool, now: datetime | None = None) -> None:
        stamp = _utc_iso(now or datetime.now(timezone.utc)) if completed else None
        with self._connect() as connection:
            result = connection.execute(
                "UPDATE storage_records SET completed_at=? WHERE id=?", (stamp, record_id)
            )
            if not result.rowcount:
                raise ValueError("보관 기록을 찾을 수 없습니다.")

    def heartbeat(self, *, now: datetime | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO storage_meta (key, value) VALUES ('lastHeartbeatAt', ?)",
                (_utc_iso(now or datetime.now(timezone.utc)),),
            )

    def companion_status(self, *, now: datetime | None = None) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM storage_meta WHERE key='lastHeartbeatAt'"
            ).fetchone()
        last = row["value"] if row else None
        age = (now or datetime.now(timezone.utc)) - _parse_time(last, "heartbeat") if last else None
        active = bool(age is not None and timedelta(0) <= age < timedelta(minutes=3))
        return {"active": active, "lastHeartbeatAt": last}

    def claim_due(self, *, now: datetime | None = None, limit: int = 10) -> list[dict[str, Any]]:
        moment = now or datetime.now(timezone.utc)
        stamp = _utc_iso(moment)
        expired = _utc_iso(moment - timedelta(minutes=5))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute("""SELECT * FROM storage_records
                WHERE notify_enabled=1 AND completed_at IS NULL AND notified_at IS NULL
                AND due_at<=? AND (claim_at IS NULL OR claim_at<?)
                ORDER BY due_at, id LIMIT ?""", (stamp, expired, limit)).fetchall()
            for row in rows:
                connection.execute("UPDATE storage_records SET claim_at=? WHERE id=?", (stamp, row["id"]))
        return [_row_dict(row) for row in rows]

    def mark_delivered(self, record_id: str, *, now: datetime | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE storage_records SET notified_at=?, claim_at=NULL WHERE id=?",
                (_utc_iso(now or datetime.now(timezone.utc)), record_id),
            )

    def release_claim(self, record_id: str) -> None:
        with self._connect() as connection:
            connection.execute("UPDATE storage_records SET claim_at=NULL WHERE id=?", (record_id,))
