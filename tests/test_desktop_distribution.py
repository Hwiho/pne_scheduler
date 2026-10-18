"""Background-only packaging checks; no test here constructs a Tk root."""
from __future__ import annotations

import json
import subprocess
import sys
import tomllib

import pytest

from pne_scheduler import desktop
from pne_scheduler.desktop_runtime import companion_command
from pne_scheduler.tools.build_windows import RESOURCES, ROOT, build_command


def test_frozen_companion_uses_same_executable_not_pythonw(tmp_path):
    exe = tmp_path / "한글 경로" / "PNE-Scheduler.exe"
    result = companion_command(tmp_path / "data.sqlite3", executable=exe, frozen=True)
    assert result[:2] == [str(exe), "--storage-companion"]
    assert result[2:] == ["--db", str((tmp_path / "data.sqlite3").resolve()), "--poll-seconds", "30"]


def test_source_companion_uses_adjacent_pythonw(tmp_path):
    with pytest.raises(FileNotFoundError):
        companion_command(tmp_path / "data.db", executable=tmp_path / "python.exe", frozen=False)
    pythonw = tmp_path / "pythonw.exe"
    pythonw.touch()
    command = companion_command(tmp_path / "data.db", executable=tmp_path / "python.exe", frozen=False)
    assert command[:3] == [str(pythonw), "-m", "pne_scheduler.storage_companion"]


def test_companion_dispatch_does_not_import_gui(monkeypatch):
    import pne_scheduler.storage_companion as notifier
    received = []
    monkeypatch.setattr(notifier, "main", lambda args: received.append(args) or 7)
    monkeypatch.setattr(desktop, "_run", lambda _: pytest.fail("Companion opened GUI"))
    assert desktop.main(["--storage-companion", "--help"]) == 7
    assert received == [["--help"]]


def test_windowed_entry_logs_without_console(tmp_path, monkeypatch):
    def run(args):
        print("windowed stdout")
        print("windowed stderr", file=sys.stderr)
        return 0
    monkeypatch.setattr(desktop, "_run", run)
    with monkeypatch.context() as context:
        context.setattr(sys, "stdout", None)
        context.setattr(sys, "stderr", None)
        assert desktop.main(["--data-dir", str(tmp_path)]) == 0
    text = (tmp_path / "logs" / "desktop.log").read_text(encoding="utf-8")
    assert "windowed stdout" in text and "windowed stderr" in text


def test_self_test_failure_report_and_existing_file_protection(tmp_path, monkeypatch):
    def broken(args):
        raise RuntimeError("missing resource")
    monkeypatch.setattr(desktop, "_run", broken)
    path = tmp_path / "failure.json"
    assert desktop.main(["--self-test", str(path)]) == 1
    assert json.loads(path.read_text())["ok"] is False
    original = path.read_bytes()
    assert desktop.main(["--self-test", str(path)]) == 2
    assert path.read_bytes() == original


def test_package_resources_are_explicit_and_in_wheel_metadata(tmp_path):
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert set(data["tool"]["setuptools"]["package-data"]["pne_scheduler"]) == set(RESOURCES)
    command = build_command(tmp_path / "build")
    assert "--windowed" in command and "--onedir" in command and "--noupx" in command
    files = [command[index + 1] for index, arg in enumerate(command) if arg == "--add-data"]
    assert len(files) == len(RESOURCES)
    assert all("*" not in f and ".env" not in f and ".git" not in f for f in files)
    for relative in RESOURCES:
        assert (ROOT / relative).is_file()


def test_real_self_check_is_offline_and_never_imports_tk(tmp_path):
    report = tmp_path / "한글 결과.json"
    # A fresh process proves it does not borrow Flask/Tk from the test runner.
    code = """
import builtins, socket, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'tkinter', '_tkinter', 'flask'}:
        raise AssertionError('Offline check imported ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
def no_socket(*args, **kwargs):
    raise AssertionError('Offline check opened a socket')
socket.socket = no_socket
from pne_scheduler.desktop import main
raise SystemExit(main(['--self-test', sys.argv[1]]))
"""
    result = subprocess.run([sys.executable, "-c", code, str(report)], cwd=ROOT.parent,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["ok"] and not data["guiTested"] and not data["equipmentApproved"]
    assert "80-90mAh-batch-current" in data["checks"]
