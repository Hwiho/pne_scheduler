"""Validation manifests for guarded SCH writer outputs."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

VALIDATION_MANIFEST_SCHEMA = "pne_scheduler.sch_validation_manifest/v1"
_REQUIRED_KEYS = {
    "schema",
    "writer",
    "status",
    "equipment_executable",
    "template",
    "target_profile",
    "output",
    "changed_fields",
    "evidence",
    "validation",
    "warnings",
}


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


def template_derived_manifest(
    source_path: str | Path,
    output_path: str | Path,
    *,
    writer: str,
    changed_fields: list[dict[str, Any]],
    evidence: list[str],
    validation_checks: list[dict[str, Any]],
    warnings: list[str],
    target_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a manifest for an analysis-only template-derived SCH."""
    source = Path(source_path)
    output = Path(output_path)
    checks = list(validation_checks)
    return {
        "schema": VALIDATION_MANIFEST_SCHEMA,
        "writer": writer,
        "status": "analysis_only",
        "equipment_executable": False,
        "template": {
            "path": str(source),
            "sha256": sha256_file(source),
            "size": source.stat().st_size,
        },
        "target_profile": target_profile
        or {
            "status": "unspecified",
            "equipment": None,
            "channel_profile": None,
            "ctspro_version": None,
        },
        "output": {
            "path": str(output),
            "sha256": sha256_file(output),
            "size": output.stat().st_size,
        },
        "changed_fields": changed_fields,
        "evidence": evidence,
        "validation": {
            "all_passed": all(check.get("passed") is True for check in checks),
            "checks": checks,
            "equipment_smoke_test": "not_run",
        },
        "warnings": warnings,
    }


def validate_manifest(manifest: dict[str, Any]) -> tuple[str, ...]:
    """Return deterministic structural errors for a validation manifest."""
    errors: list[str] = []
    if manifest.get("schema") != VALIDATION_MANIFEST_SCHEMA:
        errors.append(f"schema: expected {VALIDATION_MANIFEST_SCHEMA!r}")
    missing = sorted(_REQUIRED_KEYS - manifest.keys())
    errors.extend(f"{key}: required" for key in missing)

    if not isinstance(manifest.get("writer"), str) or not manifest.get("writer"):
        errors.append("writer: required non-empty string")
    if not isinstance(manifest.get("equipment_executable"), bool):
        errors.append("equipment_executable: required boolean")
    if not isinstance(manifest.get("target_profile"), dict):
        errors.append("target_profile: required object")
    if not isinstance(manifest.get("changed_fields"), list):
        errors.append("changed_fields: required array")
    if not isinstance(manifest.get("evidence"), list):
        errors.append("evidence: required array")
    if not isinstance(manifest.get("warnings"), list):
        errors.append("warnings: required array")

    output = manifest.get("output")
    if not isinstance(output, dict):
        errors.append("output: required object")
    else:
        digest = output.get("sha256")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            errors.append("output.sha256: required lowercase SHA-256")
        if not isinstance(output.get("size"), int) or output["size"] <= 0:
            errors.append("output.size: required positive integer")

    validation = manifest.get("validation")
    if not isinstance(validation, dict):
        errors.append("validation: required object")
    else:
        if not isinstance(validation.get("all_passed"), bool):
            errors.append("validation.all_passed: required boolean")
        if not isinstance(validation.get("checks"), list):
            errors.append("validation.checks: required array")
        if validation.get("equipment_smoke_test") not in {
            "not_run",
            "passed",
            "failed",
        }:
            errors.append(
                "validation.equipment_smoke_test: expected not_run, passed, or failed"
            )
    return tuple(errors)


def write_validation_manifest(
    manifest_path: str | Path,
    manifest: dict[str, Any],
) -> Path:
    """Atomically write a validation manifest."""
    path = Path(manifest_path)
    if not path.parent.exists():
        raise ValueError(f"Manifest directory does not exist: {path.parent}")
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("Invalid validation manifest: " + "; ".join(errors))
    rendered = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(rendered, encoding="utf-8")
    os.replace(temporary, path)
    return path
