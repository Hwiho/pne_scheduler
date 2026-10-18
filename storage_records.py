"""Persistent high-temperature storage records shared by web and Windows companion."""

from __future__ import annotations

import json
import math
import re
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
DAY_SECONDS = 86_400
MAX_CHECKPOINTS = 100


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


def _checkpoint_days(value: Any, target_days: float) -> list[float]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_CHECKPOINTS:
        raise ValueError(f"중간 확인일은 배열이며 최대 {MAX_CHECKPOINTS}개여야 합니다.")
    checkpoints: list[float] = []
    for item in value:
        if isinstance(item, bool):
            raise ValueError("중간 확인일은 숫자여야 합니다.")
        try:
            day = float(item)
        except (ValueError, TypeError) as exc:
            raise ValueError("중간 확인일은 숫자여야 합니다.") from exc
        if not math.isfinite(day) or not 0 < day < target_days:
            raise ValueError("중간 확인일은 0일 초과, 최종 목표일 미만이어야 합니다.")
        checkpoints.append(day)
    if len(set(checkpoints)) != len(checkpoints):
        raise ValueError("중간 확인일은 중복될 수 없습니다.")
    return sorted(checkpoints)


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
    checkpoints = _checkpoint_days(raw.get("checkpointDays"), days)
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
        "checkpointDays": checkpoints,
        "notifyEnabled": notify_enabled,
    }


def _alert_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "kind": row["kind"],
        "checkpointDay": row["checkpoint_day"],
        "dueAt": row["due_at"],
        "acknowledgedAt": row["acknowledged_at"],
        "snoozedUntil": row["snoozed_until"],
        "notifiedAt": row["notified_at"],
    }


def _row_dict(row: sqlite3.Row, alerts: list[dict[str, Any]],
              history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    final = next((alert for alert in alerts if alert["kind"] == "final"), None)
    return {
        "id": row["id"],
        "sample": row["sample"],
        "temperatureC": row["temperature_c"],
        "startedAt": row["started_at"],
        "targetDays": row["target_days"],
        "dueAt": row["due_at"],
        "checkpointDays": json.loads(row["checkpoint_days"]),
        "notifyEnabled": bool(row["notify_enabled"]),
        "completedAt": row["completed_at"],
        "archivedAt": row["archived_at"],
        "notifyBeforeArchive": (bool(row["archive_notify_enabled"])
                                if row["archive_notify_enabled"] is not None else None),
        "archiveHistory": history or [],
        # Kept for older clients; this is the final alert's delivery time.
        "notifiedAt": final["notifiedAt"] if final else row["notified_at"],
        "alerts": alerts,
    }


class StorageStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        # SQLite's journal-mode switch can return BUSY immediately instead of
        # using the connection timeout when two processes upgrade together.
        deadline = time.monotonic() + 10
        while True:
            try:
                connection.execute("PRAGMA journal_mode=WAL")
                break
            except sqlite3.OperationalError as exc:
                if ("locked" not in str(exc).lower() or time.monotonic() >= deadline):
                    connection.close()
                    raise
                time.sleep(0.05)
        connection.execute("PRAGMA foreign_keys=ON")
        # Serialize schema inspection and migration across the web API and
        # companion so neither sees a stale column list during an upgrade.
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("""CREATE TABLE IF NOT EXISTS storage_records (
            id TEXT PRIMARY KEY, sample TEXT NOT NULL, temperature_c REAL NOT NULL,
            started_at TEXT NOT NULL, target_days REAL NOT NULL, due_at TEXT NOT NULL,
            notify_enabled INTEGER NOT NULL DEFAULT 0, completed_at TEXT,
            notified_at TEXT, claim_at TEXT, checkpoint_days TEXT NOT NULL DEFAULT '[]'
        )""")
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(storage_records)")}
        if "checkpoint_days" not in columns:
            connection.execute(
                "ALTER TABLE storage_records ADD COLUMN checkpoint_days TEXT NOT NULL DEFAULT '[]'"
            )
        if "archived_at" not in columns:
            connection.execute("ALTER TABLE storage_records ADD COLUMN archived_at TEXT")
        if "archive_notify_enabled" not in columns:
            connection.execute("ALTER TABLE storage_records ADD COLUMN archive_notify_enabled INTEGER")
        connection.execute("""CREATE TABLE IF NOT EXISTS storage_record_events (
            id TEXT PRIMARY KEY, record_id TEXT NOT NULL, action TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            FOREIGN KEY(record_id) REFERENCES storage_records(id) ON DELETE CASCADE
        )""")
        connection.execute("""CREATE INDEX IF NOT EXISTS storage_record_events_by_record
            ON storage_record_events(record_id)""")
        connection.execute("""CREATE TABLE IF NOT EXISTS storage_alerts (
            id TEXT PRIMARY KEY, record_id TEXT NOT NULL, event_key TEXT NOT NULL,
            kind TEXT NOT NULL, checkpoint_day REAL, due_at TEXT NOT NULL,
            acknowledged_at TEXT, snoozed_until TEXT, notified_at TEXT, claim_at TEXT,
            UNIQUE(record_id, event_key),
            FOREIGN KEY(record_id) REFERENCES storage_records(id) ON DELETE CASCADE
        )""")
        self._sync_alerts(connection)
        connection.execute("""CREATE TABLE IF NOT EXISTS storage_meta (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        )""")
        # Schema setup and alert backfill must finish before claim_due starts
        # its explicit IMMEDIATE transaction on this connection.
        connection.commit()
        return connection

    @staticmethod
    def _sync_alerts(connection: sqlite3.Connection, record_id: str | None = None) -> None:
        where = " WHERE id=?" if record_id else ""
        args = (record_id,) if record_id else ()
        rows = connection.execute(f"SELECT * FROM storage_records{where}", args).fetchall()
        for row in rows:
            started = _parse_time(row["started_at"], "시작")
            checkpoints = json.loads(row["checkpoint_days"] or "[]")
            for day in checkpoints:
                connection.execute("""INSERT OR IGNORE INTO storage_alerts
                    (id, record_id, event_key, kind, checkpoint_day, due_at)
                    VALUES (?, ?, ?, 'checkpoint', ?, ?)""", (
                        uuid.uuid4().hex, row["id"], f"checkpoint:{float(day):.12g}", day,
                        _utc_iso(started + timedelta(seconds=float(day) * DAY_SECONDS)),
                    ))
            connection.execute("""INSERT OR IGNORE INTO storage_alerts
                (id, record_id, event_key, kind, checkpoint_day, due_at, notified_at, claim_at)
                VALUES (?, ?, 'final', 'final', NULL, ?, ?, ?)""", (
                    uuid.uuid4().hex, row["id"], row["due_at"], row["notified_at"], row["claim_at"],
                ))

    @staticmethod
    def _alerts(connection: sqlite3.Connection, record_id: str) -> list[dict[str, Any]]:
        rows = connection.execute("""SELECT * FROM storage_alerts WHERE record_id=?
            ORDER BY due_at, kind, id""", (record_id,)).fetchall()
        return [_alert_dict(row) for row in rows]

    def list_records(self, *, include_archived: bool = False) -> list[dict[str, Any]]:
        with self._connect() as connection:
            where = "" if include_archived else "WHERE archived_at IS NULL"
            rows = connection.execute(
                f"SELECT * FROM storage_records {where} "
                "ORDER BY archived_at IS NOT NULL, completed_at IS NOT NULL, due_at, id"
            ).fetchall()
            records = [_row_dict(row, self._alerts(connection, row["id"]), [
                {"action": event["action"], "at": event["occurred_at"]}
                for event in connection.execute(
                    "SELECT action, occurred_at FROM storage_record_events WHERE record_id=? ORDER BY rowid",
                    (row["id"],),
                )
            ]) for row in rows]
        return records

    def set_archived(self, record_id: str, archived: bool,
                     *, now: datetime | None = None) -> None:
        """Soft archive only: preserve the record, alert state and audit trail."""
        if not isinstance(archived, bool):
            raise ValueError("보관함 이동 여부는 true 또는 false여야 합니다.")
        stamp = _utc_iso(now or datetime.now(timezone.utc))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT archived_at FROM storage_records WHERE id=?", (record_id,),
            ).fetchone()
            if row is None:
                raise ValueError("보관 기록을 찾을 수 없습니다.")
            if bool(row["archived_at"]) == archived:
                return
            if archived:
                # Also turn off the legacy flag: an older installed companion
                # does not know archived_at, but it already respects this flag.
                connection.execute("""UPDATE storage_records SET archived_at=?,
                    archive_notify_enabled=notify_enabled, notify_enabled=0 WHERE id=?""",
                    (stamp, record_id))
            else:
                connection.execute("""UPDATE storage_records SET archived_at=NULL,
                    notify_enabled=COALESCE(archive_notify_enabled, notify_enabled),
                    archive_notify_enabled=NULL WHERE id=?""", (record_id,))
            connection.execute("""INSERT INTO storage_record_events
                (id, record_id, action, occurred_at) VALUES (?, ?, ?, ?)""",
                (uuid.uuid4().hex, record_id, "archived" if archived else "restored", stamp))

    def add(self, raw: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
        record = _validated(raw, now=now or datetime.now(timezone.utc), imported=False)
        try:
            with self._connect() as connection:
                connection.execute("""INSERT INTO storage_records
                    (id, sample, temperature_c, started_at, target_days, due_at,
                     checkpoint_days, notify_enabled)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (
                    record["id"], record["sample"], record["temperatureC"],
                    record["startedAt"], record["targetDays"], record["dueAt"],
                    json.dumps(record["checkpointDays"]), int(record["notifyEnabled"]),
                ))
                self._sync_alerts(connection, record["id"])
                row = connection.execute(
                    "SELECT * FROM storage_records WHERE id=?", (record["id"],)
                ).fetchone()
                result = _row_dict(row, self._alerts(connection, record["id"]))
        except sqlite3.IntegrityError as exc:
            raise ValueError("같은 보관 기록 ID가 이미 있습니다.") from exc
        return result

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
                previous = connection.execute(
                    "SELECT * FROM storage_records WHERE id=?", (record["id"],)
                ).fetchone()
                if previous:
                    existing = _row_dict(previous, self._alerts(connection, record["id"]))
                    keys = ("sample", "temperatureC", "startedAt", "targetDays", "dueAt", "checkpointDays")
                    if any(existing[key] != record[key] for key in keys):
                        raise ValueError(f"기록 ID 충돌: {record['id']}. 기존 기록은 덮어쓰지 않았습니다.")
                    continue
                connection.execute("""INSERT INTO storage_records
                    (id, sample, temperature_c, started_at, target_days, due_at,
                     checkpoint_days, notify_enabled)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0)""", (
                    record["id"], record["sample"], record["temperatureC"],
                    record["startedAt"], record["targetDays"], record["dueAt"],
                    json.dumps(record["checkpointDays"]),
                ))
                self._sync_alerts(connection, record["id"])
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

    def set_notifications(self, record_id: str, enabled: bool) -> None:
        if not isinstance(enabled, bool):
            raise ValueError("알림 설정은 true 또는 false여야 합니다.")
        with self._connect() as connection:
            result = connection.execute("UPDATE storage_records SET notify_enabled=? WHERE id=? AND archived_at IS NULL", (int(enabled), record_id))
            if not result.rowcount:
                if connection.execute("SELECT id FROM storage_records WHERE id=?", (record_id,)).fetchone():
                    raise ValueError("보관함에서 복원한 후 알림을 설정하세요.")
                raise ValueError("보관 기록을 찾을 수 없습니다.")

    def acknowledge_alert(self, record_id: str, alert_id: str,
                          *, now: datetime | None = None) -> None:
        with self._connect() as connection:
            result = connection.execute("""UPDATE storage_alerts
                SET acknowledged_at=?, claim_at=NULL WHERE id=? AND record_id=?""", (
                _utc_iso(now or datetime.now(timezone.utc)), alert_id, record_id,
            ))
            if not result.rowcount:
                raise ValueError("보관 알림을 찾을 수 없습니다.")

    def snooze_alert(self, record_id: str, alert_id: str, until: Any,
                     *, now: datetime | None = None) -> None:
        moment = now or datetime.now(timezone.utc)
        wake = _parse_time(until, "다시 알림")
        if not moment < wake <= moment + timedelta(days=3650):
            raise ValueError("다시 알림 시각은 현재보다 이후, 3650일 이내여야 합니다.")
        with self._connect() as connection:
            result = connection.execute("""UPDATE storage_alerts SET acknowledged_at=NULL,
                snoozed_until=?, notified_at=NULL, claim_at=NULL WHERE id=? AND record_id=?""", (
                _utc_iso(wake), alert_id, record_id,
            ))
            if not result.rowcount:
                raise ValueError("보관 알림을 찾을 수 없습니다.")

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
            rows = connection.execute("""SELECT a.*, r.sample, r.temperature_c, r.target_days
                FROM storage_alerts a JOIN storage_records r ON r.id=a.record_id
                WHERE r.notify_enabled=1 AND r.completed_at IS NULL AND r.archived_at IS NULL
                AND a.acknowledged_at IS NULL AND a.notified_at IS NULL
                AND COALESCE(a.snoozed_until, a.due_at)<=?
                AND (a.claim_at IS NULL OR a.claim_at<?)
                ORDER BY COALESCE(a.snoozed_until, a.due_at), a.id LIMIT ?""",
                (stamp, expired, limit)).fetchall()
            for row in rows:
                connection.execute("UPDATE storage_alerts SET claim_at=? WHERE id=?", (stamp, row["id"]))
        return [{
            **_alert_dict(row), "recordId": row["record_id"], "sample": row["sample"],
            "temperatureC": row["temperature_c"], "targetDays": row["target_days"],
        } for row in rows]

    def mark_delivered(self, alert_id: str, *, now: datetime | None = None) -> None:
        stamp = _utc_iso(now or datetime.now(timezone.utc))
        with self._connect() as connection:
            row = connection.execute(
                "SELECT record_id, kind FROM storage_alerts WHERE id=?", (alert_id,)
            ).fetchone()
            if not row:
                raise ValueError("보관 알림을 찾을 수 없습니다.")
            connection.execute(
                "UPDATE storage_alerts SET notified_at=?, claim_at=NULL WHERE id=?", (stamp, alert_id)
            )
            if row["kind"] == "final":
                connection.execute(
                    "UPDATE storage_records SET notified_at=?, claim_at=NULL WHERE id=?",
                    (stamp, row["record_id"]),
                )

    def alert_can_notify(self, alert_id: str) -> bool:
        """Recheck after claim: a user may have archived/finished the record."""
        with self._connect() as connection:
            row = connection.execute("""SELECT 1 FROM storage_alerts a
                JOIN storage_records r ON r.id=a.record_id WHERE a.id=?
                AND r.notify_enabled=1 AND r.archived_at IS NULL AND r.completed_at IS NULL
                AND a.acknowledged_at IS NULL AND a.notified_at IS NULL
                AND a.claim_at IS NOT NULL""", (alert_id,)).fetchone()
        return row is not None

    def release_claim(self, alert_id: str) -> None:
        with self._connect() as connection:
            connection.execute("UPDATE storage_alerts SET claim_at=NULL WHERE id=?", (alert_id,))
