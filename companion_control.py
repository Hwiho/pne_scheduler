"""Cooperative lifecycle control for one user's one storage database."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import uuid

from . import __version__
from .data_safety import database_lock, file_lock, is_locked
from .storage_records import StorageStore, _parse_time, _utc_iso

CONTROL_VERSION = "1"
RUNTIME_KEYS = ("companionRunId", "companionState", "companionVersion", "companionControlVersion",
                "companionStartedAt", "companionStoppedAt", "stopRequestedRunId", "lastHeartbeatAt", "lastError")


def notifier_lock(store: StorageStore) -> Path:
    return store.path.resolve().with_suffix(".notifier.lock")


def companion_status(store: StorageStore, *, now=None):
    moment = now or datetime.now(timezone.utc)
    meta = store.runtime_meta()
    last = meta.get("lastHeartbeatAt") or None
    try:
        fresh = last is not None and timedelta(0) <= moment - _parse_time(last, "heartbeat") < timedelta(minutes=3)
    except ValueError:
        fresh = False
    held = is_locked(notifier_lock(store))
    run_id = meta.get("companionRunId", "")
    control = meta.get("companionControlVersion") == CONTROL_VERSION and bool(run_id)
    paused = meta.get("restoreNotificationsPaused") == "1"
    recorded = meta.get("companionState", "")
    stopping = control and meta.get("stopRequestedRunId") == run_id
    starting = recorded == "starting" and fresh
    if held:
        state = "stopping" if stopping else "running" if control and fresh else "unresponsive"
    elif starting:
        state = "stopping" if stopping else "starting"
    elif recorded == "stopped":
        state = "stopped"
    elif not control and fresh:
        state = "legacy"
    elif run_id:
        state = "interrupted"
    else:
        state = "offline"
    labels = {"running": "실행 중", "stopping": "종료 요청됨 · 종료 확인 중", "starting": "시작 확인 중",
              "unresponsive": "종료 미확인 · 잠금 사용 중", "legacy": "구버전 실행 상태 · 안전 종료 제어 미지원",
              "stopped": "안전 종료 확인", "interrupted": "비정상 종료 또는 시작 실패 · 잠금 해제 확인", "offline": "미실행"}
    return {"active": held or starting or state == "legacy", "state": state, "label": labels[state],
            "runId": run_id, "version": meta.get("companionVersion", "미확인"),
            "lastHeartbeatAt": last, "stoppedAt": meta.get("companionStoppedAt") or None,
            "lastError": meta.get("lastError", ""), "lockHeld": held,
            "canStop": control and (held or starting), "canStart": sys.platform == "win32" and not (held or starting or state == "legacy" or paused),
            "restorePaused": paused,
            "backupReady": not (held or starting or state == "legacy"),
            "pendingCount": store.pending_alert_count(now=moment),
            "deliveryMeaning": "전송 기록은 Windows에 요청했다는 뜻이며 실제 화면 표시·사용자 확인과 다릅니다."}


def request_stop(store: StorageStore, run_id: str):
    with file_lock(database_lock(store.path), timeout=10):
        status = companion_status(store)
        if not status["canStop"]:
            if status["backupReady"]:
                return status
            raise ValueError("이 실행기는 안전 종료 요청을 지원하지 않습니다. 해당 실행기를 직접 종료한 뒤 상태를 다시 확인하세요.")
        if not run_id or run_id != status["runId"]:
            raise ValueError("실행기가 바뀌었습니다. 최신 상태를 확인한 뒤 다시 요청하세요.")
        if not store.update_runtime({"stopRequestedRunId": run_id}, expected_run=run_id):
            raise ValueError("실행기가 바뀌어 종료 요청을 보내지 않았습니다.")
    return companion_status(store)


def start_companion(store: StorageStore):
    if sys.platform != "win32":
        raise ValueError("알림 실행기는 Windows 사용자 세션에서만 시작합니다.")
    from .desktop_runtime import companion_command
    command = companion_command(store.path)
    with file_lock(database_lock(store.path), timeout=10):
        status = companion_status(store)
        if not status["canStart"]:
            raise ValueError("실행 중이거나 종료/복원 알림 검토가 끝나지 않았습니다. 상태를 새로 확인하세요.")
        run_id = uuid.uuid4().hex
        store.update_runtime({"companionRunId": run_id, "companionState": "starting",
                              "companionVersion": __version__, "companionControlVersion": CONTROL_VERSION,
                              "lastHeartbeatAt": _utc_iso(datetime.now(timezone.utc)),
                              "stopRequestedRunId": "", "companionStoppedAt": "", "lastError": ""})
        command += ["--run-id", run_id]
        cwd = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
        try:
            subprocess.Popen(command, cwd=str(cwd), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, close_fds=True,
                             creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        except OSError as exc:
            store.update_runtime({"companionState": "failed", "lastError": str(exc)[:500]}, expected_run=run_id)
            raise
    return companion_status(store)
