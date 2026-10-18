"""Reentrant, cross-process resource locks shared by desktop, API and backups.

Lock files are durable coordination points, never PID files to delete. The OS
releases their locks on process death. No lock permits overwriting user data.
"""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
from functools import wraps
import os
from pathlib import Path
import threading
import time
import sys


class ResourceBusyError(OSError):
    pass


_registry_guard = threading.Lock()
_registry: dict[str, threading.RLock] = {}
_held = threading.local()


def directory_lock(directory: Path) -> Path:
    return Path(directory).resolve() / ".maintenance.lock"


def database_lock(path: Path) -> Path:
    return Path(path).resolve().with_suffix(".maintenance.lock")


def project_lock(path: Path) -> Path:
    path = Path(path).resolve()
    return path.with_name(f".{path.name}.maintenance.lock")


@contextmanager
def file_lock(path: Path, *, timeout: float = 0):
    path = Path(path).absolute()
    if path.is_symlink():
        raise ValueError("잠금 경로는 심볼릭 링크일 수 없습니다.")
    key = str(path.resolve())
    with _registry_guard:
        gate = _registry.setdefault(key, threading.RLock())
    if not gate.acquire(timeout=timeout):
        raise ResourceBusyError("데이터를 다른 작업이 사용 중입니다. 잠시 후 다시 시도하세요.")
    held = getattr(_held, "paths", None)
    if held is None:
        held = _held.paths = set()
    stream = None
    locked = False
    nested = key in held
    try:
        if nested:
            yield
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        stream = os.fdopen(descriptor, "r+b")
        if os.fstat(descriptor).st_size == 0:
            stream.write(b"0")
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    stream.seek(0)
                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise ResourceBusyError("데이터 잠금이 사용 중입니다. 실행기 종료 또는 현재 작업 완료를 기다리세요.") from exc
                time.sleep(.05)
        held.add(key)
        yield
    finally:
        if not nested:
            held.discard(key)
        if stream is not None:
            try:
                if locked:
                    if os.name == "nt":
                        import msvcrt
                        stream.seek(0)
                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            finally:
                stream.close()
        gate.release()


def is_locked(path: Path) -> bool:
    try:
        with file_lock(path):
            return False
    except ResourceBusyError:
        return True


@contextmanager
def resource_locks(paths, *, timeout=10):
    with ExitStack() as stack:
        for path in sorted({Path(p).resolve() for p in paths}):
            stack.enter_context(file_lock(path, timeout=timeout))
        yield


def guard_paths(select):
    def decorate(function):
        @wraps(function)
        def guarded(*args, **kwargs):
            with resource_locks(select(*args, **kwargs)):
                return function(*args, **kwargs)
        return guarded
    return decorate


def publish_new_directory(source: Path, target: Path):
    """Atomic no-replace publication, including empty existing directories."""
    if os.name == "nt":
        os.rename(source, target)  # Windows refuses any existing target.
        return
    import ctypes
    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        function = library.renamex_np
        function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        result = function(os.fsencode(source), os.fsencode(target), 0x00000004)  # RENAME_EXCL
    elif hasattr(library, "renameat2"):
        function = library.renameat2
        function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        result = function(-100, os.fsencode(source), -100, os.fsencode(target), 1)  # RENAME_NOREPLACE
    else:
        raise OSError("이 시스템은 덮어쓰기 없는 폴더 게시를 지원하지 않습니다.")
    if result:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(target))
