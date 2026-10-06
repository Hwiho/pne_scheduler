"""Windows user-session companion for local high-temperature storage alerts.

Run with ``pythonw -m pne_scheduler.storage_companion`` in the same installed
environment and user account as the local API. This never controls equipment.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .storage_records import StorageStore, default_storage_db

LOG = logging.getLogger(__name__)


def send_windows_balloon(title: str, message: str) -> None:
    """Show a Windows notification-area balloon from the current user session.

    Shell_NotifyIcon acceptance is not proof the OS displayed it; Focus Assist,
    notification policy, or session state may suppress the visual notification.
    """
    if sys.platform != "win32":
        raise RuntimeError("Windows 사용자 세션에서만 알림을 보낼 수 있습니다.")

    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD), ("Data4", ctypes.c_byte * 8)]

    class NOTIFYICONDATAW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
                    ("uID", wintypes.UINT), ("uFlags", wintypes.UINT),
                    ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
                    ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD),
                    ("dwStateMask", wintypes.DWORD), ("szInfo", wintypes.WCHAR * 256),
                    ("uTimeoutOrVersion", wintypes.UINT), ("szInfoTitle", wintypes.WCHAR * 64),
                    ("dwInfoFlags", wintypes.DWORD), ("guidItem", GUID),
                    ("hBalloonIcon", wintypes.HICON)]

    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.LoadIconW.restype = wintypes.HICON
    shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
    shell32.Shell_NotifyIconW.restype = wintypes.BOOL
    window = user32.CreateWindowExW(0, "STATIC", "PNE Storage Alerts", 0,
                                   0, 0, 0, 0, None, None, None, None)
    if not window:
        raise OSError("Windows 알림용 창을 생성하지 못했습니다.")
    icon = NOTIFYICONDATAW()
    icon.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    icon.hWnd = window
    icon.uID = 1
    icon.uFlags = 0x2 | 0x4  # NIF_ICON | NIF_TIP
    icon.hIcon = user32.LoadIconW(None, ctypes.c_void_p(32516))  # IDI_INFORMATION
    icon.szTip = "PNE Scheduler 보관 알림"
    try:
        if not shell32.Shell_NotifyIconW(0, ctypes.byref(icon)):  # NIM_ADD
            raise OSError("Windows 알림 영역 아이콘을 등록하지 못했습니다.")
        icon.uFlags = 0x10  # NIF_INFO
        icon.szInfoTitle = title[:63]
        icon.szInfo = message[:255]
        icon.dwInfoFlags = 0x1  # NIIF_INFO
        if not shell32.Shell_NotifyIconW(1, ctypes.byref(icon)):  # NIM_MODIFY
            raise OSError("Windows 알림을 전달하지 못했습니다.")
        # Keep the notification owner alive long enough for the shell to show it.
        time.sleep(10)
    finally:
        shell32.Shell_NotifyIconW(2, ctypes.byref(icon))  # NIM_DELETE
        user32.DestroyWindow(window)


def process_due(store: StorageStore, notify: Callable[[str, str], None],
                *, now: datetime | None = None) -> int:
    """Claim, send, and record due alerts; failed sends remain retryable."""
    moment = now or datetime.now(timezone.utc)
    sent = 0
    for record in store.claim_due(now=moment):
        try:
            title = "고온저장 목표 시각 도달"
            message = f"{record['sample']} · {record['temperatureC']:g}°C · 목표 {record['targetDays']:g}일"
            notify(title, message)
            store.mark_delivered(record["id"], now=moment)
            sent += 1
        except Exception:
            store.release_claim(record["id"])
            LOG.exception("Storage notification failed for %s", record["id"])
    return sent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PNE Scheduler Windows storage alerts")
    parser.add_argument("--db", type=Path, default=default_storage_db())
    parser.add_argument("--poll-seconds", type=int, default=30)
    args = parser.parse_args(argv)
    if sys.platform != "win32":
        parser.error("이 알림 실행기는 Windows 사용자 세션에서만 실행됩니다.")
    if not 5 <= args.poll_seconds <= 3600:
        parser.error("--poll-seconds는 5–3600 범위여야 합니다.")
    # Windows file lock prevents a second login/startup process from claiming
    # the same notifications. The DB can still be shared with the local API.
    import msvcrt
    lock_path = args.db.with_suffix(".notifier.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(args.db.with_suffix(".notifier.log")),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    with lock_path.open("a+b") as lock_file:
        lock_file.seek(0)
        lock_file.write(b"0")
        lock_file.flush()
        lock_file.seek(0)
        try:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            LOG.error("보관 알림 실행기가 이미 실행 중입니다.")
            return 2
        store = StorageStore(args.db)
        while True:
            try:
                store.heartbeat()
                process_due(store, send_windows_balloon)
            except Exception:
                LOG.exception("Storage notifier iteration failed")
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
