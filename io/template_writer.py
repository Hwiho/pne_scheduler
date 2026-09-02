"""Template-preserving SCH field writer with explicit evidence gates."""

from __future__ import annotations

import hashlib
import json
import math
import os
import struct
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..schema.fields import SchFieldDefinition, get_step_fields
from .sch_binary import read_sch_binary
from .validation_manifest import VALIDATION_MANIFEST_SCHEMA

SCH_PATCH_SCHEMA = "pne_scheduler.sch_patch/v1"
_IDENTITY_FIELDS = {"step_no", "step_type_word"}
_STRUCT_FORMATS = {
    "uint8": "<B",
    "uint32": "<I",
    "int32": "<i",
    "float32": "<f",
}


@dataclass(frozen=True, slots=True)
class SchFieldPatch:
    step_no: int
    field: str
    value: int | float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SchFieldPatch:
        return cls(
            step_no=int(data["step_no"]),
            field=str(data["field"]),
            value=data["value"],
        )


@dataclass(frozen=True, slots=True)
class SchPatchPlan:
    template_sha256: str
    patches: tuple[SchFieldPatch, ...]
    schema: str = SCH_PATCH_SCHEMA
    expected_version: int | None = None
    target_profile: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SchPatchPlan:
        schema = str(data.get("schema", SCH_PATCH_SCHEMA))
        if schema != SCH_PATCH_SCHEMA:
            raise ValueError(f"Unsupported patch schema: {schema}")
        raw_version = data.get("expected_version")
        if isinstance(raw_version, str):
            expected_version = int(raw_version, 0)
        elif raw_version is None:
            expected_version = None
        else:
            expected_version = int(raw_version)
        return cls(
            schema=schema,
            template_sha256=str(data["template_sha256"]).lower(),
            expected_version=expected_version,
            target_profile=_parse_target_profile(data.get("target_profile")),
            patches=tuple(
                SchFieldPatch.from_dict(item) for item in data.get("patches", [])
            ),
        )

    @classmethod
    def load(cls, path: str | Path) -> SchPatchPlan:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass(frozen=True, slots=True)
class SchPatchResult:
    output_path: Path
    report: dict[str, Any]


def _parse_target_profile(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("target_profile must be an object or null")
    for key, item in value.items():
        if not isinstance(key, str) or not key:
            raise ValueError("target_profile keys must be non-empty strings")
        if item is not None and not isinstance(item, (str, int, float, bool)):
            raise ValueError(
                f"target_profile.{key} must be a scalar value or null"
            )
    return dict(value)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pack_value(field: SchFieldDefinition, value: int | float) -> bytes:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field.name}: value must be numeric")
    if field.dtype == "float32" and not math.isfinite(float(value)):
        raise ValueError(f"{field.name}: value must be finite")
    try:
        return struct.pack(_STRUCT_FORMATS[field.dtype], value)
    except (KeyError, struct.error, OverflowError) as exc:
        raise ValueError(
            f"{field.name}: {value!r} is invalid for {field.dtype}"
        ) from exc


def apply_sch_patch(
    template_path: str | Path,
    plan: SchPatchPlan,
    output_path: str | Path,
    *,
    allow_analysis_output: bool = False,
    allow_unverified_fields: bool = False,
) -> SchPatchResult:
    """Write a byte-preserving clone with only declared field ranges changed."""
    if not allow_analysis_output:
        raise ValueError(
            "Analysis-only output was not acknowledged; explicitly allow it "
            "before writing"
        )
    template = Path(template_path)
    output = Path(output_path)
    if template.resolve() == output.resolve():
        raise ValueError("Output path must differ from the template path")
    if not output.parent.exists():
        raise ValueError(f"Output directory does not exist: {output.parent}")
    if not plan.patches:
        raise ValueError("Patch plan must contain at least one patch")

    source = template.read_bytes()
    source_hash = _sha256(source)
    if source_hash != plan.template_sha256:
        raise ValueError(
            "Template SHA-256 mismatch: "
            f"expected {plan.template_sha256}, got {source_hash}"
        )

    doc = read_sch_binary(template)
    version = doc.sch_version
    if version is None:
        raise ValueError("Template does not declare an SCH version")
    if plan.expected_version is not None and version != plan.expected_version:
        raise ValueError(
            f"Template version 0x{version:08x} does not match expected "
            f"0x{plan.expected_version:08x}"
        )

    step_indexes = {step.step_no: index for index, step in enumerate(doc.steps)}
    if len(step_indexes) != len(doc.steps):
        raise ValueError("Template contains duplicate step numbers")

    seen: set[tuple[int, str]] = set()
    body = bytearray(source)
    applied: list[dict[str, Any]] = []
    expected_changed_offsets: set[int] = set()
    warnings: list[str] = []
    for patch in plan.patches:
        key = (patch.step_no, patch.field)
        if key in seen:
            raise ValueError(
                f"Duplicate patch for step {patch.step_no} field {patch.field}"
            )
        seen.add(key)

        step_index = step_indexes.get(patch.step_no)
        if step_index is None:
            raise ValueError(f"Unknown template step: {patch.step_no}")
        field = next(
            (
                candidate
                for candidate in get_step_fields(version)
                if candidate.name == patch.field
            ),
            None,
        )
        if field is None:
            raise ValueError(
                f"Field {patch.field!r} is not registered for version 0x{version:08x}"
            )
        if field.name in _IDENTITY_FIELDS:
            raise ValueError(f"Topology field {field.name!r} cannot be patched")
        if not field.writer_ready and not allow_unverified_fields:
            raise ValueError(
                f"Field {field.name!r} is not writer-ready; collect controlled "
                "evidence or explicitly allow unverified offline output"
            )
        if not field.writer_ready:
            warnings.append(
                f"Step {patch.step_no} field {field.name} is not writer-ready."
            )

        packed = _pack_value(field, patch.value)
        absolute = doc.payload_offset + step_index * doc.step_size + field.offset
        before = bytes(body[absolute : absolute + field.size])
        body[absolute : absolute + field.size] = packed
        expected_changed_offsets.update(range(absolute, absolute + field.size))
        applied.append(
            {
                **asdict(patch),
                "offset_in_step": field.offset,
                "absolute_offset": absolute,
                "dtype": field.dtype,
                "confidence": field.confidence.value,
                "evidence": field.evidence,
                "writer_ready": field.writer_ready,
                "before_hex": before.hex(),
                "after_hex": packed.hex(),
            }
        )

    changed_offsets = {
        index
        for index, (before, after) in enumerate(zip(source, body))
        if before != after
    }
    if len(source) != len(body):
        raise AssertionError("Template-preserving writer changed file length")
    if not changed_offsets:
        raise ValueError("Patch plan produced no byte changes")
    if not changed_offsets.issubset(expected_changed_offsets):
        raise AssertionError("Writer changed bytes outside declared field ranges")

    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_bytes(body)
    os.replace(temporary, output)

    written = read_sch_binary(output)
    if (
        written.sch_version != doc.sch_version
        or written.payload_offset != doc.payload_offset
        or written.step_size != doc.step_size
        or tuple(step.step_no for step in written.steps)
        != tuple(step.step_no for step in doc.steps)
    ):
        output.unlink(missing_ok=True)
        raise ValueError("Patched output failed structural re-read validation")

    output_bytes = bytes(body)
    validation_checks = [
        {
            "name": "template_sha256",
            "passed": source_hash == plan.template_sha256,
        },
        {
            "name": "header_preserved",
            "passed": output_bytes[: doc.payload_offset] == doc.header,
        },
        {
            "name": "file_length_preserved",
            "passed": len(output_bytes) == len(source),
        },
        {
            "name": "declared_ranges_only",
            "passed": changed_offsets.issubset(expected_changed_offsets),
        },
        {
            "name": "structural_reread",
            "passed": True,
        },
    ]
    return SchPatchResult(
        output_path=output,
        report={
            "schema": VALIDATION_MANIFEST_SCHEMA,
            "writer": "template_patch",
            "status": "analysis_only",
            "equipment_executable": False,
            "target_profile": plan.target_profile
            or {
                "status": "unspecified",
                "equipment": None,
                "channel_profile": None,
                "ctspro_version": None,
            },
            "template": {
                "path": str(template),
                "sha256": source_hash,
                "size": len(source),
                "version": f"0x{version:08x}",
                "payload_offset": doc.payload_offset,
                "step_size": doc.step_size,
                "step_count": doc.step_count,
            },
            "output": {
                "path": str(output),
                "sha256": _sha256(output_bytes),
                "size": len(output_bytes),
            },
            "changed_fields": applied,
            "applied": applied,
            "changed_byte_count": len(changed_offsets),
            "header_preserved": output_bytes[: doc.payload_offset] == doc.header,
            "file_length_preserved": len(output_bytes) == len(source),
            "validation": {
                "all_passed": all(check["passed"] for check in validation_checks),
                "checks": validation_checks,
                "equipment_smoke_test": "not_run",
            },
            "warnings": warnings,
        },
    )
