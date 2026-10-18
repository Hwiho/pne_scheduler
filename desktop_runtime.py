"""Process launch helpers for source installs and offline frozen desktops."""
from __future__ import annotations

from pathlib import Path
import sys


def companion_command(db_path: Path, *, executable=None, frozen=None) -> list[str]:
    executable = Path(executable or sys.executable)
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    options = ["--db", str(Path(db_path).resolve()), "--poll-seconds", "30"]
    if frozen:
        return [str(executable), "--storage-companion", *options]
    pythonw = executable.with_name("pythonw.exe")
    if not pythonw.is_file():
        raise FileNotFoundError(f"현재 Python 환경에 pythonw.exe가 없습니다: {pythonw}")
    return [str(pythonw), "-m", "pne_scheduler.storage_companion", *options]
