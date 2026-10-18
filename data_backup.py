"""Verified local backup and new-directory-only restore, shared by web and Tk."""
from __future__ import annotations

from contextlib import contextmanager, closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat
import tempfile
import time
import unicodedata
import zipfile

from . import __version__
from .companion_control import companion_status, notifier_lock, RUNTIME_KEYS
from .data_safety import database_lock, directory_lock, project_lock, file_lock, resource_locks, ResourceBusyError, publish_new_directory
from .ir.project import ScheduleProject
from .library import LIBRARY_SCHEMA, MethodLibrary, MethodVersion
from .storage_records import StorageStore
from .ui.document import AUTOSAVE_SCHEMA, ProjectDocument

SCHEMA = "pne_scheduler.backup/v1"
MAX_FILES = 2000
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
TABLES = {
    "storage_records": {"id", "sample", "temperature_c", "started_at", "target_days", "due_at", "notify_enabled",
                        "completed_at", "notified_at", "claim_at", "checkpoint_days", "archived_at", "archive_notify_enabled"},
    "storage_alerts": {"id", "record_id", "event_key", "kind", "checkpoint_day", "due_at", "acknowledged_at", "snoozed_until", "notified_at", "claim_at"},
    "storage_record_events": {"id", "record_id", "action", "occurred_at"},
    "storage_meta": {"key", "value"},
}


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _absolute(value):
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise ValueError("절대 경로를 입력하세요.")
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError("절대 경로를 입력하세요.")
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("심볼릭 링크 경로는 백업/복원에 사용할 수 없습니다.")
    return path.resolve()


def _name(name):
    parts = PurePosixPath(name).parts
    if (not parts or name != "/".join(parts) or any(p in {"", ".", ".."} or p.endswith((".", " "))
            or re.search(r'[\\:\x00-\x1f<>"|?*]', p) or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", p)
            for p in parts) or PurePosixPath(name).is_absolute()):
        raise ValueError("백업 안에 안전하지 않은 파일 경로가 있습니다.")
    return unicodedata.normalize("NFC", name).casefold()


def _project(raw):
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("schema") not in {"pne_scheduler.schproj/v1", "pne_scheduler.schproj/v2"}:
        raise ValueError("지원하는 .schproj 프로젝트가 아닙니다.")
    ScheduleProject.from_dict(data)
    return data


def _validate_file(name, raw):
    if name.startswith("projects/") and len(PurePosixPath(name).parts) == 2 and name.endswith(".schproj"):
        _project(raw)
    elif name.startswith("library/") and len(PurePosixPath(name).parts) == 3 and re.fullmatch(r"v\d+\.json", PurePosixPath(name).name):
        value = json.loads(raw)
        if value.get("schema") != LIBRARY_SCHEMA:
            raise ValueError("지원하지 않는 방법 라이브러리 형식입니다.")
        entry = MethodVersion.from_dict(value)
        if entry.method_id != PurePosixPath(name).parts[1] or entry.version != int(PurePosixPath(name).stem[1:]):
            raise ValueError("방법 파일의 이름/버전과 내용이 다릅니다.")
    elif re.fullmatch(r"recovery/autosave-[A-Za-z0-9_-]+\.json", name):
        value = json.loads(raw)
        if value.get("schema") != AUTOSAVE_SCHEMA:
            raise ValueError("지원하지 않는 자동 복구 형식입니다.")
        _project(_json(value.get("project")))
    elif name != "storage.sqlite3":
        raise ValueError("백업에 허용되지 않은 파일이 포함돼 있습니다.")


def _database_rows(path):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA trusted_schema=OFF")
        objects = connection.execute("SELECT type,name,sql FROM sqlite_master").fetchall()
        if {name for kind, name, _sql in objects if kind == "table"} != set(TABLES):
            raise ValueError("지원하지 않는 보관 DB 스키마입니다.")
        for kind, name, sql in objects:
            if kind not in {"table", "index"} or (sql and re.search(r"\b(CHECK|GENERATED|VIRTUAL)\b", sql, re.I)):
                raise ValueError("실행 가능한 사용자 DB 스키마는 복원하지 않습니다.")
            if kind == "index" and name != "storage_record_events_by_record" and not name.startswith("sqlite_autoindex_"):
                raise ValueError("지원하지 않는 보관 DB 인덱스입니다.")
        if connection.execute("PRAGMA quick_check").fetchall() != [("ok",)] or connection.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("보관 DB 무결성 검사에 실패했습니다.")
        result = {}
        for table, expected in TABLES.items():
            columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
            if set(columns) != expected or len(columns) != len(expected):
                raise ValueError("보관 DB 열이 현재 지원 형식과 다릅니다.")
            # Preserve event row order; application history is ordered by rowid.
            result[table] = (columns, connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall())
        return result


class DataManager:
    def __init__(self, storage: StorageStore, library_root: Path, recovery_root: Path):
        self.storage = storage
        self.library_root = Path(library_root).resolve()
        self.recovery_root = Path(recovery_root).resolve()

    def status(self):
        return {"ok": True, "database": str(self.storage.path.resolve()), "library": str(self.library_root),
                "recovery": str(self.recovery_root), "companion": companion_status(self.storage)}

    def action(self, action, payload=None):
        from .companion_control import request_stop, start_companion
        data = payload or {}
        if not isinstance(data, dict):
            raise ValueError("작업 입력은 객체여야 합니다.")
        if action == "status":
            return self.status()
        if action == "companionStart":
            start_companion(self.storage)
            return self.status()
        if action == "companionStop":
            request_stop(self.storage, data.get("runId", ""))
            return self.status()
        if action == "resumeNotifications":
            if data.get("confirmed") is not True:
                raise ValueError("복원된 일정·지연 알림 검토를 확인하세요.")
            return self.resume_notifications()
        if action in {"backupPreview", "backupCreate"}:
            if type(data.get("includeCurrent", False)) is not bool:
                raise ValueError("현재 프로젝트 포함 여부를 확인하세요.")
            current = data.get("project") if data.get("includeCurrent") else None
            if data.get("includeCurrent") and current is None:
                raise ValueError("포함할 현재 프로젝트가 없습니다.")
            if action == "backupPreview":
                return self.preview_backup(data.get("projectPaths", []), current)
            return self.create_backup(data.get("outputPath"), data.get("token"), paths=data.get("projectPaths", []),
                                      current_project=current, external_writes_stopped=data.get("externalWritesStopped", False))
        if action == "restoreInspect":
            return self.inspect_backup(data.get("archivePath"))
        if action == "restoreApply":
            return self.restore_backup(data.get("archivePath"), data.get("destination"), data.get("token"))
        raise ValueError("알 수 없는 데이터 관리 작업입니다.")

    def _paths(self, paths):
        if not isinstance(paths, list) or len(paths) > 100:
            raise ValueError("추가 프로젝트는 최대 100개 경로 목록이어야 합니다.")
        result = [_absolute(p) for p in paths]
        if len({str(p).casefold() for p in result}) != len(result) or any(p.suffix.lower() != ".schproj" or not p.is_file() for p in result):
            raise ValueError("중복되지 않는 실제 .schproj 파일만 선택하세요.")
        return result

    def _inventory(self, projects):
        result = {}
        for root, pattern, prefix in ((self.library_root, "*/v*.json", "library"), (self.recovery_root, "autosave-*.json", "recovery")):
            if root.exists():
                for path in sorted(root.glob(pattern)):
                    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
                        raise ValueError("백업 대상에 링크 또는 일반 파일이 아닌 항목이 있습니다.")
                    result[f"{prefix}/{path.relative_to(root).as_posix()}"] = path
        for i, path in enumerate(projects, 1):
            result[f"projects/project-{i:03d}.schproj"] = path
        if len(result) > MAX_FILES - 2:
            raise ValueError("백업 파일 수 제한을 초과했습니다.")
        return result

    @contextmanager
    def _snapshot(self, paths, current_project):
        projects = self._paths(paths)
        # The notifier lock is acquired first, as it is by the runtime itself.
        # A legacy runtime holding it is also blocked; no PID is trusted.
        with file_lock(notifier_lock(self.storage)), resource_locks([
                database_lock(self.storage.path), directory_lock(self.library_root), directory_lock(self.recovery_root),
                *(project_lock(p) for p in projects)]):
            status = companion_status(self.storage)
            if not status["backupReady"]:
                raise ResourceBusyError("알림 실행기 종료가 확인되지 않았습니다. 안전 종료 후 다시 백업하세요.")
            with self.storage._connect():
                pass  # Finish a supported old-schema migration before snapshotting.
            inventory = self._inventory(projects)
            with tempfile.TemporaryDirectory(prefix="pne-backup-") as temporary:
                snapshot = Path(temporary) / "storage.sqlite3"
                # IMMEDIATE blocks even older SQLite writers, while a different
                # read connection performs backup (not from a write transaction).
                with closing(sqlite3.connect(self.storage.path, timeout=2)) as fence:
                    fence.execute("BEGIN IMMEDIATE")
                    try:
                        payloads = {}
                        total = 0
                        for name, path in inventory.items():
                            if path.stat().st_size > MAX_FILE_BYTES:
                                raise ValueError("백업 파일 하나가 32 MiB 제한을 초과했습니다.")
                            raw = path.read_bytes()
                            _validate_file(name, raw)
                            total += len(raw)
                            if total > MAX_TOTAL_BYTES:
                                raise ValueError("백업 크기 제한을 초과했습니다.")
                            payloads[name] = raw
                        if current_project is not None:
                            raw = _json(current_project)
                            _project(raw)
                            payloads["projects/current.schproj"] = raw
                        deadline = time.monotonic() + 30
                        def progress(_status, _remaining, _total):
                            if time.monotonic() > deadline:
                                raise ValueError("DB 백업 제한 시간을 초과했습니다. 다른 작업을 마친 후 다시 시도하세요.")
                        with closing(sqlite3.connect(self.storage.path)) as source, closing(sqlite3.connect(snapshot)) as target:
                            source.backup(target, pages=128, progress=progress, sleep=.05)
                        _database_rows(snapshot)
                        payloads["storage.sqlite3"] = snapshot.read_bytes()
                        if sum(map(len, payloads.values())) > MAX_TOTAL_BYTES or any(len(p) > MAX_FILE_BYTES for p in payloads.values()):
                            raise ValueError("백업 크기 제한을 초과했습니다.")
                        files = [{"path": name, "size": len(raw), "sha256": _digest(raw),
                                  "source": str(inventory[name]) if name in inventory else "current-project" if name.startswith("projects/") else str(self.storage.path.resolve())}
                                 for name, raw in sorted(payloads.items())]
                        normalized = [_name(item["path"]) for item in files]
                        if len(set(normalized)) != len(normalized):
                            raise ValueError("Windows에서 중복되는 파일명이 있습니다.")
                        plan = {"ok": True, "token": _digest(_json(files)), "files": files,
                                "totalBytes": sum(item["size"] for item in files), "currentProjectIncluded": current_project is not None,
                                "excluded": ["선택하지 않은 외부 프로젝트·원자료·SCH 출력", "로그·잠금 파일·설정/키 파일", "선택하지 않은 브라우저 미저장 초안"]}
                        def unchanged():
                            if self._inventory(projects) != inventory or any(not p.is_file() or p.is_symlink() or _digest(p.read_bytes()) != _digest(payloads[n]) for n, p in inventory.items()):
                                raise ValueError("백업 도중 파일이 바뀌었습니다. 부분 백업은 게시하지 않았습니다.")
                        unchanged()
                        yield plan, payloads, unchanged
                    finally:
                        fence.rollback()

    def preview_backup(self, paths=None, current_project=None):
        with self._snapshot(paths or [], current_project) as (plan, _payloads, _unchanged):
            return plan

    def create_backup(self, output, token, *, paths=None, current_project=None, external_writes_stopped=False):
        if external_writes_stopped is not True:
            raise ValueError("다른 구버전 앱·외부 편집기의 쓰기를 중지했는지 확인해 주세요.")
        output = _absolute(output)
        if output.suffix.lower() != ".zip" or not output.parent.is_dir() or output.exists():
            raise ValueError("기존 폴더 안의 새 ZIP 파일 경로를 지정하세요. 덮어쓰지 않습니다.")
        if any(output.is_relative_to(root) for root in (self.library_root, self.recovery_root)):
            raise ValueError("라이브러리/복구 폴더 밖에 백업을 저장하세요.")
        with self._snapshot(paths or [], current_project) as (plan, payloads, unchanged):
            if not token or token != plan["token"]:
                raise ValueError("백업 대상이 미리보기 후 바뀌었습니다. 다시 미리보기 하세요.")
            manifest = {"schema": SCHEMA, "appVersion": __version__, "createdAt": datetime.now(timezone.utc).isoformat(),
                        "storageSchema": 1, "files": plan["files"], "excluded": plan["excluded"]}
            fd, name = tempfile.mkstemp(prefix=".pne-backup-", suffix=".zip", dir=output.parent)
            staging = Path(name)
            try:
                with os.fdopen(fd, "w+b") as stream:
                    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
                        for path, raw in payloads.items():
                            archive.writestr(path, raw)
                        archive.writestr("manifest.json", _json(manifest))
                    stream.flush()
                    os.fsync(stream.fileno())
                self.inspect_backup(staging)
                unchanged()
                os.link(staging, output)  # exclusive publish, never overwrite
            finally:
                staging.unlink(missing_ok=True)
        return {"ok": True, "path": str(output), "sha256": _digest(output.read_bytes()), "files": len(payloads)}

    def _read_archive(self, archive_path):
        path = _absolute(archive_path)
        if not path.is_file() or path.stat().st_size > MAX_TOTAL_BYTES:
            raise ValueError("백업 파일이 없거나 크기 제한을 초과했습니다.")
        raw_archive = path.read_bytes()
        import io
        with zipfile.ZipFile(io.BytesIO(raw_archive)) as archive:
            entries = archive.infolist()
            names = [_name(item.filename) for item in entries]
            if (len(entries) > MAX_FILES or len(set(names)) != len(names) or sum(i.file_size for i in entries) > MAX_TOTAL_BYTES
                    or any(i.is_dir() or i.flag_bits & 1 or i.file_size > MAX_FILE_BYTES
                           or stat.S_IFMT(i.external_attr >> 16) not in {0, stat.S_IFREG} for i in entries)):
                raise ValueError("백업의 파일 수·크기·중복·링크·암호화 항목을 확인하세요.")
            payloads = {item.filename: archive.read(item) for item in entries}
        manifest = json.loads(payloads.pop("manifest.json"))
        if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA or type(manifest.get("storageSchema")) is not int or manifest["storageSchema"] != 1:
            raise ValueError("지원하지 않는 백업 형식/버전입니다.")
        files = manifest.get("files")
        if not isinstance(files, list) or len(files) != len(payloads) or {f["path"] for f in files} != set(payloads) or "storage.sqlite3" not in payloads:
            raise ValueError("백업 manifest와 실제 파일 목록이 다릅니다.")
        for item in files:
            raw = payloads[item["path"]]
            if item.get("size") != len(raw) or item.get("sha256") != _digest(raw):
                raise ValueError("백업 파일 해시/크기 검사에 실패했습니다.")
            _validate_file(item["path"], raw)
        with tempfile.TemporaryDirectory(prefix="pne-verify-") as temporary:
            db = Path(temporary) / "storage.sqlite3"
            db.write_bytes(payloads["storage.sqlite3"])
            rows = _database_rows(db)
        return manifest, payloads, rows, _digest(raw_archive)

    def inspect_backup(self, archive_path):
        manifest, _payloads, rows, digest = self._read_archive(archive_path)
        return {"ok": True, "token": digest, "createdAt": manifest["createdAt"], "appVersion": manifest["appVersion"],
                "files": manifest["files"], "counts": {table: len(data[1]) for table, data in rows.items()},
                "note": "새 폴더에만 복원합니다. 원본은 보존하고 알림은 일시 정지합니다. 복구본은 원래 저장 경로와 분리됩니다."}

    def restore_backup(self, archive_path, destination, token):
        target = _absolute(destination)
        if not target.parent.is_dir() or target.exists():
            raise ValueError("기존 폴더 안에 아직 존재하지 않는 새 복원 폴더 경로를 지정하세요.")
        if any(target.is_relative_to(root) for root in (self.library_root, self.recovery_root)):
            raise ValueError("라이브러리/복구 폴더 안으로는 복원하지 않습니다.")
        manifest, payloads, rows, digest = self._read_archive(archive_path)
        if not token or token != digest:
            raise ValueError("검토 후 백업 파일이 바뀌었습니다. 다시 검사하세요.")
        with file_lock(project_lock(target)), tempfile.TemporaryDirectory(prefix=".pne-restore-", dir=target.parent) as temporary:
            staging = Path(temporary) / "data"
            staging.mkdir()
            for name, raw in payloads.items():
                if name == "storage.sqlite3":
                    continue
                if name.startswith("recovery/"):
                    data = json.loads(raw)
                    data["backup_original_source_path"] = data.get("source_path")
                    data["source_path"] = None  # saving a recovery must not overwrite an old original
                    raw = _json(data)
                path = staging / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            # Rebuild in our known schema with bound values; never activate
            # schema SQL supplied by an archive. Preserve event/alert history.
            restored = StorageStore(staging / "storage.sqlite3")
            with restored._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                for table in ("storage_records", "storage_alerts", "storage_record_events", "storage_meta"):
                    columns, records = rows[table]
                    connection.executemany(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", records)
                settings = dict(connection.execute("SELECT id,notify_enabled FROM storage_records"))
                # Preserve a previously paused backup's original settings.
                previous = connection.execute("SELECT value FROM storage_meta WHERE key='restoreNotifySettings'").fetchone()
                if previous:
                    settings = json.loads(previous[0])
                if not isinstance(settings, dict) or any(type(v) is not int or v not in (0, 1) for v in settings.values()):
                    raise ValueError("복원 알림 설정이 손상됐습니다.")
                connection.execute("UPDATE storage_records SET notify_enabled=0,claim_at=NULL")
                connection.execute("UPDATE storage_alerts SET claim_at=NULL")
                connection.executemany("DELETE FROM storage_meta WHERE key=?", [(key,) for key in RUNTIME_KEYS])
                connection.executemany("INSERT OR REPLACE INTO storage_meta(key,value) VALUES(?,?)", [
                    ("restoreNotificationsPaused", "1"), ("restoreNotifySettings", json.dumps(settings)), ("restoredFromSha256", digest)])
            actual = restored.list_records(include_archived=True)
            if len(actual) != len(rows["storage_records"][1]):
                raise ValueError("복원 후 기록 수가 일치하지 않습니다.")
            for path in staging.glob("projects/*.schproj"):
                ProjectDocument.open(path, autosave_dir=staging / "recovery")
            library = MethodLibrary(staging / "library")
            for path in staging.glob("library/*/v*.json"):
                if not any(v.path == path for v in library.versions(path.parent.name)):
                    raise ValueError("복원한 방법을 앱에서 읽지 못했습니다.")
            _database_rows(restored.path)
            report = {"schema": "pne_scheduler.restore/v1", "archiveSha256": digest, "files": len(payloads),
                      "records": len(actual), "notificationsPaused": True, "sourceUntouched": True}
            (staging / "restore-report.json").write_bytes(_json(report))
            for path in staging.rglob("*"):
                if path.is_file():
                    with path.open("r+b") as stream:
                        os.fsync(stream.fileno())
            # A no-clobber sibling reservation and final existence check; all
            # application restores use this same destination lock.
            if target.exists():
                raise ValueError("복원 대상이 사용 중입니다. 다른 새 폴더를 지정하세요.")
            publish_new_directory(staging, target)
        return {"ok": True, "path": str(target), **report,
                "note": "복원 검사가 끝났습니다. 현재 데이터 경로는 바뀌지 않았습니다. 새 데이터 폴더로 다시 실행한 뒤 알림을 검토하세요."}

    def resume_notifications(self):
        with self.storage._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT value FROM storage_meta WHERE key='restoreNotifySettings'").fetchone()
            if row:
                settings = json.loads(row[0])
                if not isinstance(settings, dict) or any(type(v) is not int or v not in (0, 1) for v in settings.values()):
                    raise ValueError("복원 알림 설정이 손상됐습니다.")
                connection.executemany("UPDATE storage_records SET notify_enabled=? WHERE id=? AND archived_at IS NULL", [(v, k) for k, v in settings.items()])
            connection.execute("DELETE FROM storage_meta WHERE key IN ('restoreNotifySettings','restoreNotificationsPaused')")
        return self.status()
