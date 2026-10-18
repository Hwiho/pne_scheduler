"""Build an unsigned, allowlisted Windows x64 offline distribution on Windows."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "PNE-Scheduler"
# No recursive repository collection: private data, archives, .env, .git,
# tests, web dependencies, and user libraries must never enter the package.
RESOURCES = (
    "planning/EQUIPMENT_CURRENT_RATINGS.json",
    "planning/EQUIPMENT_REGISTRY.json",
    "planning/GOLDEN_FIXTURES_LOCKED.json",
    "planning/Q_NOM_POLICY.json",
    "example/training/signature_category_labels.json",
    "example/training/verified_filename_labels.json",
    "example/fixtures/capacheck_zip/9)Bimodal_SJ1300_6040_NCN_capacheck.sch",
)


def build_command(output: Path) -> list[str]:
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
               "--onedir", "--windowed", "--noupx", "--name", APP_NAME,
               "--distpath", str(output / "app"), "--workpath", str(output / "work"),
               "--specpath", str(output / "spec"), "--paths", str(ROOT.parent),
               "--exclude-module", "flask", "--exclude-module", "pytest"]
    for relative in RESOURCES:
        source = ROOT / relative
        if not source.is_file():
            raise FileNotFoundError(source)
        destination = "pne_scheduler/" + Path(relative).parent.as_posix()
        command.extend(["--add-data", f"{source}:{destination}"])
    command.append(str(ROOT / "run_pne_scheduler_workspace.py"))
    return command


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build(output: Path) -> Path:
    if sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise RuntimeError("Windows x64에서 빌드해야 합니다. macOS/Linux 교차 빌드는 지원하지 않습니다.")
    # Refuse both reusing output and packaging an unrecorded working tree.
    if output.exists():
        raise FileExistsError(f"새 출력 폴더를 사용하세요: {output}")
    status = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=ROOT, text=True)
    if status.strip():
        raise RuntimeError("커밋된 깨끗한 작업 트리에서만 배포판을 빌드합니다.")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    output.mkdir(parents=True)
    subprocess.run(build_command(output), cwd=ROOT, check=True)
    app = output / "app" / APP_NAME
    shutil.copyfile(ROOT / "planning" / "WINDOWS_OFFLINE_GUIDE.md", app / "사용안내.md")
    metadata = {"schema": "pne.desktop-build/v1", "commit": commit, "platform": "windows-x64",
                "python": platform.python_version(), "pyinstaller": importlib.metadata.version("pyinstaller"),
                "signed": False, "equipmentApproved": False,
                "resourceHashes": {name: sha256(ROOT / name) for name in RESOURCES}}
    (app / "build-info.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    files = sorted(path for path in app.rglob("*") if path.is_file())
    checksums = "".join(f"{sha256(path)}  {path.relative_to(app).as_posix()}\n" for path in files)
    (app / "SHA256SUMS.txt").write_text(checksums, encoding="utf-8")
    archive = output / f"{APP_NAME}-Windows-x64-{commit[:12]}.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as package:
        for path in sorted(app.rglob("*")):
            if path.is_file():
                package.write(path, path.relative_to(app.parent))
    archive.with_suffix(".zip.sha256").write_text(f"{sha256(archive)}  {archive.name}\n", encoding="utf-8")
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build(args.output.resolve()))


if __name__ == "__main__":
    main()
