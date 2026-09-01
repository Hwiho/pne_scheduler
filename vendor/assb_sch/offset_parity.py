"""Offset parity between vendored ASSB constants and pne_scheduler schema."""

from __future__ import annotations

from dataclasses import dataclass

from ...schema import fields as pne_fields
from .constants import (
    SCH_END_CURRENT_OFFSET,
    SCH_REFERENCE_CURRENT_OFFSET,
    SCH_V0X00010003_STEP612_CONDITION_FIELDS,
)

MetadataValue = object


@dataclass(frozen=True, slots=True)
class OffsetPair:
    assb_name: str
    assb_offset: int
    pne_name: str
    pne_offset: int


# Fields where ASSB and pne_scheduler intentionally use the same byte offset.
SHARED_OFFSET_PAIRS: tuple[OffsetPair, ...] = (
    OffsetPair(
        "SCH_REFERENCE_CURRENT_OFFSET",
        SCH_REFERENCE_CURRENT_OFFSET,
        "OFFSET_F_VREF",
        pne_fields.OFFSET_F_VREF,
    ),
    OffsetPair(
        "SCH_END_CURRENT_OFFSET",
        SCH_END_CURRENT_OFFSET,
        "OFFSET_F_END_I",
        pne_fields.OFFSET_F_END_I,
    ),
    OffsetPair(
        "fEndC",
        SCH_V0X00010003_STEP612_CONDITION_FIELDS["fEndC"][1],
        "OFFSET_F_END_C",
        pne_fields.OFFSET_F_END_C,
    ),
)


@dataclass(frozen=True, slots=True)
class DocumentedDivergence:
    assb_name: str
    assb_offset: int
    pne_name: str
    pne_offset: int
    reason: str


# pne_scheduler updated these after fixture corpus analysis; ASSB keeps legacy offsets.
DOCUMENTED_DIVERGENCES: tuple[DocumentedDivergence, ...] = (
    DocumentedDivergence(
        "nGotoStepID",
        SCH_V0X00010003_STEP612_CONDITION_FIELDS["nGotoStepID"][1],
        "OFFSET_N_GOTO_STEP_ID",
        pne_fields.OFFSET_N_GOTO_STEP_ID,
        "pne_scheduler corpus regression; ASSB legacy PNE_file_structures offset",
    ),
    DocumentedDivergence(
        "fSocRate",
        SCH_V0X00010003_STEP612_CONDITION_FIELDS["fSocRate"][1],
        "OFFSET_F_SOC_RATE",
        pne_fields.OFFSET_F_SOC_RATE,
        "pne_scheduler corpus regression (+8 bytes vs ASSB)",
    ),
    DocumentedDivergence(
        "fMaxCapacity",
        SCH_V0X00010003_STEP612_CONDITION_FIELDS["fMaxCapacity"][1],
        "OFFSET_F_MAX_CAPACITY",
        pne_fields.OFFSET_F_MAX_CAPACITY,
        "pne_scheduler corpus regression (+16 bytes vs ASSB)",
    ),
    DocumentedDivergence(
        "bUseActualCapa",
        SCH_V0X00010003_STEP612_CONDITION_FIELDS["bUseActualCapa"][1],
        "OFFSET_B_USE_ACTUAL_CAPA",
        pne_fields.OFFSET_B_USE_ACTUAL_CAPA,
        "pne_scheduler corpus regression (+16 bytes vs ASSB)",
    ),
    DocumentedDivergence(
        "bUseDataStepNo",
        SCH_V0X00010003_STEP612_CONDITION_FIELDS["bUseDataStepNo"][1],
        "OFFSET_B_USE_DATA_STEP_NO",
        pne_fields.OFFSET_B_USE_DATA_STEP_NO,
        "pne_scheduler corpus regression (+16 bytes vs ASSB)",
    ),
)

# Present in ASSB layout table but not yet tracked in pne_scheduler schema.
ASSB_ONLY_FIELDS: dict[str, int] = {
    "nLoopInfoEndSocGoto": SCH_V0X00010003_STEP612_CONDITION_FIELDS[
        "nLoopInfoEndSocGoto"
    ][1],
}


def assb_offset_table() -> dict[str, int]:
    table = {
        "SCH_REFERENCE_CURRENT_OFFSET": SCH_REFERENCE_CURRENT_OFFSET,
        "SCH_END_CURRENT_OFFSET": SCH_END_CURRENT_OFFSET,
    }
    for name, (_, offset) in SCH_V0X00010003_STEP612_CONDITION_FIELDS.items():
        table[name] = offset
    return table


def pne_scheduler_offset_table() -> dict[str, int]:
    return {
        "OFFSET_F_VREF": pne_fields.OFFSET_F_VREF,
        "OFFSET_F_IREF": pne_fields.OFFSET_F_IREF,
        "OFFSET_F_END_TIME": pne_fields.OFFSET_F_END_TIME,
        "OFFSET_F_END_V": pne_fields.OFFSET_F_END_V,
        "OFFSET_F_END_I": pne_fields.OFFSET_F_END_I,
        "OFFSET_F_END_C": pne_fields.OFFSET_F_END_C,
        "OFFSET_LOOP_GOTO": pne_fields.OFFSET_LOOP_GOTO,
        "OFFSET_LOOP_COUNT": pne_fields.OFFSET_LOOP_COUNT,
        "OFFSET_N_GOTO_STEP_ID": pne_fields.OFFSET_N_GOTO_STEP_ID,
        "OFFSET_F_SOC_RATE": pne_fields.OFFSET_F_SOC_RATE,
        "OFFSET_F_MAX_CAPACITY": pne_fields.OFFSET_F_MAX_CAPACITY,
        "OFFSET_B_USE_ACTUAL_CAPA": pne_fields.OFFSET_B_USE_ACTUAL_CAPA,
        "OFFSET_B_USE_DATA_STEP_NO": pne_fields.OFFSET_B_USE_DATA_STEP_NO,
    }
