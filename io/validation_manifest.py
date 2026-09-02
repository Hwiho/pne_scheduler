"""Validation manifests for guarded SCH writer outputs."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

VALIDATION_MANIFEST_SCHEMA = "pne_scheduler.sch_validation_manifest/v1"


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 digest of a file."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def default_manifest_path(output_path: str | Path) -> Path:
    """Return the sidecar path used for an SCH output."""
    output = Path(output_path)
    return output.with_suffix(output.suffix + ".manifest.json")


def experimental_build_manifest(
    project_path: str | Path,
    output_path: str | Path,
    *,
    sch_version: int,
    cell_profile: dict[str, Any],
) -> dict[str, Any]:
    """Describe an intentionally non-equipment-ready from-scratch build."""
    project = Path(project_path)
    output = Path(output_path)
    output_size = output.stat().st_size
    checks = [
        {"name": "output_written", "passed": output.is_file()},
        {"name": "output_nonempty", "passed": output_size > 0},
    ]
    return {
        "schema": VALIDATION_MANIFEST_SCHEMA,
        "writer": "experimental_from_scratch",
        "status": "experimental",
        "equipment_executable": False,
        "source_project": {
            "path": str(project),
            "sha256": sha256_file(project),
        },
        "template": None,
        "target_profile": {
            "status": "unspecified",
            "equipment": None,
            "channel_profile": None,
            "ctspro_version": None,
            "sch_version": f"0x{sch_version:08x}",
            "cell_profile": cell_profile,
        },
        "output": {
            "path": str(output),
            "sha256": sha256_file(output),
            "size": output_size,
        },
        "changed_fields": [],
        "evidence": [],
        "validation": {
            "all_passed": all(check["passed"] for check in checks),
            "checks": checks,
            "structural_reread": "not_run",
            "equipment_smoke_test": "not_run",
        },
        "warnings": [
            "The writer uses a placeholder header.",
            "No target equipment profile was supplied.",
            "Do not load or execute this file on PNE equipment.",
        ],
    }


def write_validation_manifest(
    manifest_path: str | Path,
    manifest: dict[str, Any],
) -> Path:
    """Atomically write a validation manifest."""
    path = Path(manifest_path)
    if not path.parent.exists():
        raise ValueError(f"Manifest directory does not exist: {path.parent}")
    rendered = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(rendered, encoding="utf-8")
    os.replace(temporary, path)
    return path
