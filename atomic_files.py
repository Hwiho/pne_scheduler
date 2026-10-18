"""Small dependency-free file primitive shared by project and recovery saving."""
from __future__ import annotations

import os
from pathlib import Path
import stat
import tempfile


def atomic_write_text(path: Path, text: str) -> None:
    """Replace only after a complete, flushed write on the same filesystem.

    Follow an existing symlink as normal text saving does. A failed write or
    replace leaves the previous file intact; this is not an overwrite approval.
    """
    path = Path(path).resolve()
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=".pne-save-")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
