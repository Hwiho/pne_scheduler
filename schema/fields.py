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


def get_step_fields(version: int) -> tuple[SchFieldDefinition, ...]:
    return STEP_FIELDS_BY_VERSION.get(int(version), ())


def get_step_field(version: int, offset: int) -> SchFieldDefinition | None:
    return next(
        (field for field in get_step_fields(version) if field.offset == offset),
        None,
    )
