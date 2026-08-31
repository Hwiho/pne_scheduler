"""Evidence-qualified SCH step fields for incremental reverse engineering."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .enums import SchFileVersion


class FieldConfidence(str, Enum):
    STRUCTURAL_VERIFIED = "structural_verified"
    CORPUS_INFERRED = "corpus_inferred"
    SEMANTIC_UNVERIFIED = "semantic_unverified"


@dataclass(frozen=True, slots=True)
class SchFieldDefinition:
    name: str
    offset: int
    dtype: str
    confidence: FieldConfidence
    evidence: str
    size: int = 4
    writable: bool = False


COMMON_STEP_FIELDS: tuple[SchFieldDefinition, ...] = (
    SchFieldDefinition(
        "step_no",
        0,
        "int32",
        FieldConfidence.STRUCTURAL_VERIFIED,
        "Sequential record number in all 102 fixtures.",
        writable=True,
    ),
    SchFieldDefinition(
        "process_word",
        4,
        "uint32",
        FieldConfidence.SEMANTIC_UNVERIFIED,
        "Present in the legacy field map; zero throughout the current corpus.",
    ),
    SchFieldDefinition(
        "step_type_word",
        8,
        "uint32",
        FieldConfidence.STRUCTURAL_VERIFIED,
        "Matches REST, CCCV, CC charge/discharge, LOOP, CYCLE, and END records.",
        writable=True,
    ),
    SchFieldDefinition(
        "mode_value",
        12,
        "float32",
        FieldConfidence.SEMANTIC_UNVERIFIED,
        "Mode-dependent nonzero values are observed, but semantics are not established.",
    ),
    SchFieldDefinition(
        "fVref",
        16,
        "float32",
        FieldConfidence.SEMANTIC_UNVERIFIED,
        "Legacy name retained for compatibility; UI units and scaling are unresolved.",
    ),
    SchFieldDefinition(
        "fIref",
        20,
        "float32",
        FieldConfidence.SEMANTIC_UNVERIFIED,
        "Legacy name retained for compatibility; UI units and scaling are unresolved.",
    ),
    SchFieldDefinition(
        "fEndTime",
        24,
        "float32",
        FieldConfidence.SEMANTIC_UNVERIFIED,
        "Legacy name retained; zero throughout the current corpus.",
    ),
    SchFieldDefinition(
        "fEndV",
        28,
        "float32",
        FieldConfidence.CORPUS_INFERRED,
        "Nonzero values occur on CC records and match voltage-like termination values.",
    ),
    SchFieldDefinition(
        "fEndI",
        32,
        "float32",
        FieldConfidence.CORPUS_INFERRED,
        "Nonzero values occur on CCCV records and match cutoff-like ratios.",
    ),
    SchFieldDefinition(
        "fEndC",
        36,
        "float32",
        FieldConfidence.SEMANTIC_UNVERIFIED,
        "Legacy name retained; no nonzero example exists in the current corpus.",
    ),
    SchFieldDefinition(
        "loop_target",
        48,
        "uint32",
        FieldConfidence.CORPUS_INFERRED,
        "LOOP-only target-like values verified in representative 612/696 fixtures.",
    ),
    SchFieldDefinition(
        "loop_count",
        52,
        "uint32",
        FieldConfidence.CORPUS_INFERRED,
        "LOOP-only repeat-like values verified in representative 612/696 fixtures.",
    ),
)

STEP_FIELDS_BY_VERSION: dict[int, tuple[SchFieldDefinition, ...]] = {
    int(SchFileVersion.V0X00010002): COMMON_STEP_FIELDS,
    int(SchFileVersion.V0X00010003): COMMON_STEP_FIELDS,
    int(SchFileVersion.V0X00010004): COMMON_STEP_FIELDS,
}

_DTYPE_SIZES = {
    "float32": 4,
    "int32": 4,
    "uint32": 4,
    "uint8": 1,
}


def get_step_fields(version: int) -> tuple[SchFieldDefinition, ...]:
    return STEP_FIELDS_BY_VERSION.get(int(version), ())


def get_step_field(version: int, offset: int) -> SchFieldDefinition | None:
    return next(
        (field for field in get_step_fields(version) if field.offset == offset),
        None,
    )


def validate_step_field_registry() -> tuple[str, ...]:
    """Return deterministic schema errors without requiring fixture data."""
    from .layouts import SCH_LAYOUTS

    errors: list[str] = []
    for version, layout in sorted(SCH_LAYOUTS.items()):
        fields = get_step_fields(version)
        if not fields:
            errors.append(f"0x{version:08x}: no step fields registered")
            continue

        names: set[str] = set()
        occupied: dict[int, str] = {}
        for field in fields:
            prefix = f"0x{version:08x}:{field.name}"
            if field.name in names:
                errors.append(f"{prefix}: duplicate field name")
            names.add(field.name)

            expected_size = _DTYPE_SIZES.get(field.dtype)
            if expected_size is None:
                errors.append(f"{prefix}: unsupported dtype {field.dtype!r}")
            elif field.size != expected_size:
                errors.append(
                    f"{prefix}: size {field.size} does not match {field.dtype} "
                    f"size {expected_size}"
                )

            if field.offset < 0 or field.offset + field.size > layout.step_size:
                errors.append(
                    f"{prefix}: byte range [{field.offset}, "
                    f"{field.offset + field.size}) exceeds step size {layout.step_size}"
                )
                continue

            for byte_offset in range(field.offset, field.offset + field.size):
                previous = occupied.get(byte_offset)
                if previous is not None:
                    errors.append(
                        f"{prefix}: overlaps {previous} at byte {byte_offset}"
                    )
                occupied[byte_offset] = field.name

            if field.writable and field.confidence == FieldConfidence.SEMANTIC_UNVERIFIED:
                errors.append(f"{prefix}: unverified semantic field cannot be writable")

    return tuple(errors)
