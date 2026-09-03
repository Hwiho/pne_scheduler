"""Evidence-qualified SCH step fields for incremental reverse engineering."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .enums import SchFileVersion

OFFSET_STEP_NO = 0
OFFSET_PROCESS_WORD = 4
OFFSET_STEP_TYPE = 8
OFFSET_MODE_VALUE = 12
OFFSET_F_VREF = 16
OFFSET_F_IREF = 20
OFFSET_F_END_TIME = 24
OFFSET_F_END_V = 28
OFFSET_F_END_I = 32
OFFSET_F_END_C = 36
OFFSET_LOOP_GOTO = 48
OFFSET_LOOP_COUNT = 52
OFFSET_LOOP_RESET_FLAG = 88
OFFSET_N_GOTO_STEP_ID = 92
OFFSET_RECORD_DV_MV = 332
OFFSET_RECORD_TIME_S = 340
OFFSET_DOD_PERCENT = 384
OFFSET_F_SOC_RATE = 392
OFFSET_F_MAX_CAPACITY = 428
OFFSET_CAP_MODE = 496
OFFSET_CAP_REF_STEP = 497
OFFSET_B_USE_ACTUAL_CAPA = 512
OFFSET_B_USE_DATA_STEP_NO = 513
OFFSET_LOOP_GOTO_ENSOL = 564


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
    writer_ready: bool = False


COMMON_STEP_FIELDS: tuple[SchFieldDefinition, ...] = (
    SchFieldDefinition(
        "step_no",
        OFFSET_STEP_NO,
        "int32",
        FieldConfidence.STRUCTURAL_VERIFIED,
        "Sequential record number in all 102 fixtures.",
    ),
    SchFieldDefinition(
        "process_word",
        OFFSET_PROCESS_WORD,
        "int32",
        FieldConfidence.SEMANTIC_UNVERIFIED,
        "Present in the legacy field map; zero throughout the current corpus.",
    ),
    SchFieldDefinition(
        "step_type_word",
        OFFSET_STEP_TYPE,
        "int32",
        FieldConfidence.STRUCTURAL_VERIFIED,
        "Matches REST, CCCV, CC charge/discharge, LOOP, CYCLE, and END records.",
    ),
    SchFieldDefinition(
        "mode_value",
        OFFSET_MODE_VALUE,
        "float32",
        FieldConfidence.CORPUS_INFERRED,
        "Ensol v612: volt_or_vlim_mV @+12 — CCCV charge V (mV), CCDi discharge V-limit (mV); "
        "golden capacheck PNE02 verified.",
    ),
    SchFieldDefinition(
        "fVref",
        OFFSET_F_VREF,
        "float32",
        FieldConfidence.CORPUS_INFERRED,
        "Ensol v612 current_mA @+16. Gate B: pne02-charge-current (10→17 mA), "
        "pne02-discharge-current (10→19 mA); CTSEditorPro reopen verified.",
        writer_ready=True,
    ),
    SchFieldDefinition(
        "fIref",
        OFFSET_F_IREF,
        "float32",
        FieldConfidence.CORPUS_INFERRED,
        "Ensol v612 time_or_rest_s @+20. Gate B: pne02-rest-duration (60→123 s); "
        "CTSEditorPro reopen verified.",
        writer_ready=True,
    ),
    SchFieldDefinition(
        "fEndTime",
        OFFSET_F_END_TIME,
        "float32",
        FieldConfidence.SEMANTIC_UNVERIFIED,
        "Legacy name retained; zero throughout the current corpus.",
    ),
    SchFieldDefinition(
        "fEndV",
        OFFSET_F_END_V,
        "float32",
        FieldConfidence.CORPUS_INFERRED,
        "Ensol v612 voltage_cutoff_mV @+28. Gate B: pne02-end-voltage; "
        "CTSEditorPro reopen verified.",
        writer_ready=True,
    ),
    SchFieldDefinition(
        "fEndI",
        OFFSET_F_END_I,
        "float32",
        FieldConfidence.CORPUS_INFERRED,
        "Ensol v612 cv_cutoff_mA @+32. Gate B: pne02-cv-cutoff (2→3 mA, cap496 "
        "normalized); CTSEditorPro reopen verified.",
        writer_ready=True,
    ),
    SchFieldDefinition(
        "fEndC",
        OFFSET_F_END_C,
        "float32",
        FieldConfidence.SEMANTIC_UNVERIFIED,
        "Legacy name retained; no nonzero example exists in the current corpus.",
    ),
    SchFieldDefinition(
        "loop_target",
        OFFSET_LOOP_GOTO,
        "uint32",
        FieldConfidence.CORPUS_INFERRED,
        "LOOP goto @+48. Gate B: pne02-loop-goto (baseline3, step 17, 1→7); "
        "CTSEditorPro reopen verified. PNE02 UI writes here, not loop_goto_ensol@564.",
        writer_ready=True,
    ),
    SchFieldDefinition(
        "loop_count",
        OFFSET_LOOP_COUNT,
        "uint32",
        FieldConfidence.CORPUS_INFERRED,
        "LOOP repeat count @+52. Gate B: pne02-loop-count; CTSEditorPro reopen verified.",
        writer_ready=True,
    ),
)

V3_612_LEGACY_STEP_FIELDS: tuple[SchFieldDefinition, ...] = (
    SchFieldDefinition(
        "nGotoStepID",
        OFFSET_N_GOTO_STEP_ID,
        "uint32",
        FieldConfidence.SEMANTIC_UNVERIFIED,
        "Legacy name retained; this word is zero in all 102 checked-in fixtures.",
    ),
    SchFieldDefinition(
        "fSocRate",
        OFFSET_F_SOC_RATE,
        "float32",
        FieldConfidence.SEMANTIC_UNVERIFIED,
        "Legacy 0x00010003 offset; controlled semantic evidence is unavailable.",
    ),
    SchFieldDefinition(
        "fMaxCapacity",
        OFFSET_F_MAX_CAPACITY,
        "float32",
        FieldConfidence.SEMANTIC_UNVERIFIED,
        "Legacy 0x00010003 offset; units and equipment scaling are unresolved.",
    ),
    SchFieldDefinition(
        "bUseActualCapa",
        OFFSET_B_USE_ACTUAL_CAPA,
        "uint8",
        FieldConfidence.SEMANTIC_UNVERIFIED,
        "Legacy 0x00010003 flag; controlled semantic evidence is unavailable.",
        size=1,
    ),
    SchFieldDefinition(
        "bUseDataStepNo",
        OFFSET_B_USE_DATA_STEP_NO,
        "uint8",
        FieldConfidence.SEMANTIC_UNVERIFIED,
        "Legacy 0x00010003 flag; controlled semantic evidence is unavailable.",
        size=1,
    ),
)

V3_612_CORPUS_STEP_FIELDS: tuple[SchFieldDefinition, ...] = (
    SchFieldDefinition(
        "loop_reset_flag",
        OFFSET_LOOP_RESET_FLAG,
        "uint32",
        FieldConfidence.CORPUS_INFERRED,
        "Near-pair corpus evidence: changed in 388 normalized 612-byte pair comparisons.",
    ),
    SchFieldDefinition(
        "record_dV_mV",
        OFFSET_RECORD_DV_MV,
        "float32",
        FieldConfidence.CORPUS_INFERRED,
        "Ensol map plus 79 normalized 612-byte pair comparisons with changes in this word.",
    ),
    SchFieldDefinition(
        "record_time_s",
        OFFSET_RECORD_TIME_S,
        "float32",
        FieldConfidence.CORPUS_INFERRED,
        "Ensol sampling Δt @+340. Gate B: pne02-sampling-interval (60→120 s) and "
        "pne02-sampling-interval-discharge; CTSEditorPro reopen verified.",
        writer_ready=True,
    ),
    SchFieldDefinition(
        "dod_percent",
        OFFSET_DOD_PERCENT,
        "float32",
        FieldConfidence.CORPUS_INFERRED,
        "Across filename-labelled schedules, 554/856 SOC values match stored 100-SOC; "
        "93 normalized pairs change this word.",
    ),
    SchFieldDefinition(
        "cap_mode",
        OFFSET_CAP_MODE,
        "uint8",
        FieldConfidence.CORPUS_INFERRED,
        "Ensol map, golden capacheck value, and 658 normalized 612-byte pair comparisons.",
        size=1,
    ),
    SchFieldDefinition(
        "cap_ref_step",
        OFFSET_CAP_REF_STEP,
        "uint8",
        FieldConfidence.CORPUS_INFERRED,
        "Ensol map and 28 normalized 612-byte pair comparisons.",
        size=1,
    ),
    SchFieldDefinition(
        "loop_goto_ensol",
        OFFSET_LOOP_GOTO_ENSOL,
        "uint32",
        FieldConfidence.CORPUS_INFERRED,
        "Ensol writer location; changed in 14 normalized pairs. Controlled target-only "
        "evidence is still required before writing.",
    ),
)

STEP_FIELDS_BY_VERSION: dict[int, tuple[SchFieldDefinition, ...]] = {
    # 0x10002 shares the 612-byte Ensol map with 0x10003 (PNE02 Gate B pairs).
    int(SchFileVersion.V0X00010002): (
        *COMMON_STEP_FIELDS,
        *V3_612_CORPUS_STEP_FIELDS,
    ),
    int(SchFileVersion.V0X00010003): (
        *COMMON_STEP_FIELDS,
        *V3_612_CORPUS_STEP_FIELDS,
        *V3_612_LEGACY_STEP_FIELDS,
    ),
    # 0x10004/696: shared-prefix fields only until C6 maps the 84-byte tail.
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


def get_writer_ready_fields(version: int) -> tuple[str, ...]:
    """Return the explicitly evidence-promoted writable field names."""
    return tuple(
        field.name for field in get_step_fields(version) if field.writer_ready
    )


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

            if (
                field.writer_ready
                and field.confidence == FieldConfidence.SEMANTIC_UNVERIFIED
            ):
                errors.append(
                    f"{prefix}: unverified semantic field cannot be writer-ready"
                )

    return tuple(errors)
