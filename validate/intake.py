"""Validate controlled-pair intake metadata (Gate B5)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

INTAKE_SCHEMA_ID = "pne_scheduler.validation_intake/v1"
ALLOWED_EQUIPMENT_SOURCES = frozenset(
    {"user_confirmed", "user_attributed", "fixture_catalog", "unknown"}
)
ALLOWED_SCOPES = frozenset(
    {"fixture_specific_provenance", "operational_context_only", "discovery"}
)


@dataclass(frozen=True, slots=True)
class IntakeValidationResult:
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_mapping(
    data: Any,
    *,
    path: str,
    errors: list[str],
) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        errors.append(f"{path}: expected object")
        return None
    return data


def validate_intake_metadata(data: Any) -> IntakeValidationResult:
    """Validate intake JSON without external jsonschema dependency."""
    errors: list[str] = []
    warnings: list[str] = []

    root = _require_mapping(data, path="$", errors=errors)
    if root is None:
        return IntakeValidationResult(False, tuple(errors), tuple(warnings))

    if root.get("schema") != INTAKE_SCHEMA_ID:
        errors.append(f"schema: expected {INTAKE_SCHEMA_ID!r}")

    equipment = _require_mapping(root.get("equipment"), path="equipment", errors=errors)
    if equipment is not None:
        for key in ("label", "rating", "source"):
            value = equipment.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"equipment.{key}: required non-empty string")
        source = equipment.get("source")
        if source not in ALLOWED_EQUIPMENT_SOURCES:
            errors.append(
                f"equipment.source: must be one of {sorted(ALLOWED_EQUIPMENT_SOURCES)}"
            )
        if source == "unknown":
            warnings.append(
                "equipment.source is unknown; evidence promotion should stay blocked"
            )
        for optional in ("ctspro_version", "channel_profile"):
            value = equipment.get(optional)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                errors.append(f"equipment.{optional}: must be non-empty string or null")
        if not equipment.get("ctspro_version"):
            warnings.append("equipment.ctspro_version missing; add CYCC/CTSMonPro build")

    scope = root.get("scope")
    if scope not in ALLOWED_SCOPES:
        errors.append(f"scope: must be one of {sorted(ALLOWED_SCOPES)}")

    for key in ("before_file", "after_file", "ui_field"):
        value = root.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{key}: required non-empty string")

    changed_step = root.get("changed_step")
    if not isinstance(changed_step, int) or isinstance(changed_step, bool) or changed_step < 1:
        errors.append("changed_step: required integer >= 1")

    for label in ("before_value", "after_value"):
        measured = _require_mapping(root.get(label), path=label, errors=errors)
        if measured is None:
            continue
        value = measured.get("value")
        if not _is_number(value):
            errors.append(f"{label}.value: required number")
        unit = measured.get("unit")
        if not isinstance(unit, str) or not unit.strip():
            errors.append(f"{label}.unit: required non-empty string")

    expected_field = root.get("expected_field")
    if expected_field is not None and (
        not isinstance(expected_field, str) or not expected_field.strip()
    ):
        errors.append("expected_field: must be non-empty string or null")

    if root.get("executed_on_equipment") is not False:
        errors.append("executed_on_equipment: must be false for schema probe pairs")

    reopen = root.get("ctspro_reopen_verified")
    if not isinstance(reopen, bool):
        errors.append("ctspro_reopen_verified: required boolean")
    elif reopen is False:
        warnings.append(
            "ctspro_reopen_verified is false; field cannot be marked writer-ready yet"
        )

    screenshots = root.get("screenshots", [])
    if screenshots is None:
        screenshots = []
    if not isinstance(screenshots, list):
        errors.append("screenshots: must be an array")
    else:
        for index, item in enumerate(screenshots):
            if not isinstance(item, str) or not item.strip():
                errors.append(f"screenshots[{index}]: must be non-empty string")

    notes = root.get("notes")
    if notes is not None and not isinstance(notes, str):
        errors.append("notes: must be string or null")

    allowed_top = {
        "schema",
        "equipment",
        "scope",
        "before_file",
        "after_file",
        "changed_step",
        "ui_field",
        "before_value",
        "after_value",
        "expected_field",
        "executed_on_equipment",
        "ctspro_reopen_verified",
        "screenshots",
        "notes",
    }
    for key in root:
        if key not in allowed_top:
            errors.append(f"unknown top-level key: {key!r}")

    return IntakeValidationResult(not errors, tuple(errors), tuple(warnings))


def load_intake_metadata(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("intake metadata root must be an object")
    return payload


def validate_intake_file(path: str | Path) -> IntakeValidationResult:
    return validate_intake_metadata(load_intake_metadata(path))


def validate_intake_with_compare_report(
    intake: dict[str, Any],
    compare_report: dict[str, Any],
) -> IntakeValidationResult:
    """Cross-check intake metadata against a compare_sch JSON report."""
    base = validate_intake_metadata(intake)
    errors = list(base.errors)
    warnings = list(base.warnings)

    if compare_report.get("schema") != "pne_scheduler.sch_diff/v2":
        errors.append("compare_report.schema: expected pne_scheduler.sch_diff/v2")
        return IntakeValidationResult(False, tuple(errors), tuple(warnings))

    if not compare_report.get("compatible"):
        errors.append("compare_report: files are not layout-compatible")

    summary = compare_report.get("summary") or {}
    if not summary.get("controlled_pair_clean"):
        errors.append(
            "compare_report: pair is not a clean single-field controlled change"
        )
        for item in compare_report.get("warnings") or []:
            warnings.append(f"compare_report: {item}")

    changed_step = intake.get("changed_step")
    step_changes = compare_report.get("step_changes") or []
    if isinstance(changed_step, int) and step_changes:
        reported_steps = {item.get("step_no") for item in step_changes}
        if reported_steps != {changed_step}:
            errors.append(
                f"changed_step={changed_step} but compare report changed steps "
                f"{sorted(reported_steps)}"
            )

    expected_field = intake.get("expected_field")
    if expected_field and step_changes:
        reported_fields = {
            word.get("field")
            for change in step_changes
            for word in change.get("words") or []
        }
        if expected_field not in reported_fields:
            warnings.append(
                f"expected_field {expected_field!r} not among changed fields "
                f"{sorted(reported_fields)}"
            )

    return IntakeValidationResult(not errors, tuple(errors), tuple(warnings))
