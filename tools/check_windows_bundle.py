"""Smoke the extracted executable away from the checkout with Python off PATH."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile


def check_bundle(archive: Path, reports: Path):
    reports.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pne-bundle-") as temporary:
        folder = Path(temporary) / "한글 경로 with spaces"
        with zipfile.ZipFile(archive) as package:
            # Our own artifact; still reject accidental absolute/traversal paths.
            for item in package.infolist():
                target = (folder / item.filename).resolve()
                if not target.is_relative_to(folder.resolve()):
                    raise ValueError("Unsafe archive member")
            package.extractall(folder)
        app = folder / "PNE-Scheduler"
        for line in (app / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
            digest, name = line.split("  ", 1)
            path = (app / name).resolve()
            if not path.is_relative_to(app.resolve()):
                raise ValueError("Unsafe checksum path")
            with path.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                    raise ValueError(f"Package checksum mismatch: {name}")
        executable = app / "PNE-Scheduler.exe"
        env = {key: value for key, value in os.environ.items()
               if not key.upper().startswith("PYTHON") and key.upper() not in {"TCL_LIBRARY", "TK_LIBRARY"}}
        env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
        # Windowed executable's exit code must be awaited, not assumed.
        for mode in ("self-test", "gui-self-test"):
            report = (reports / f"{mode}.json").resolve()
            subprocess.run([str(executable), f"--{mode}", str(report)], cwd=folder,
                           env=env, check=True, timeout=90)
            data = json.loads(report.read_text(encoding="utf-8"))
            if not data.get("ok") or not data.get("frozen"):
                raise RuntimeError(f"Packaged runtime failed: {data}")
        # The companion path must dispatch to its own parser, not open a second
        # workspace or require pythonw. This does NOT display an OS notification.
        subprocess.run([str(executable), "--storage-companion", "--help"],
                       cwd=folder, env=env, check=True, timeout=30)
    print("Extracted offline executable: checksums, headless, Tk and companion dispatch passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--reports", type=Path, required=True)
    arguments = parser.parse_args()
    check_bundle(arguments.archive, arguments.reports)
