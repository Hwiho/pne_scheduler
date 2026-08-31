"""612-byte FILE_STEP_CONDITION layout for SCH version 0x00010003.

Offsets below are verified against ASSB/Ensol pne_converter tests and
`sch_file_structure_20250211.xlsx`. Full 612-byte field map is Phase 0.1.
"""

from __future__ import annotations

from dataclasses import dataclass

from .enums import DEFAULT_SCH_VERSION, DEFAULT_STEP_SIZE

SCH_FILE_VERSION = DEFAULT_SCH_VERSION
STEP_RECORD_SIZE = DEFAULT_STEP_SIZE

# Header
HEADER_SIZE = 320  # approximate; exact layout TBD in Phase 0.1

# Step field byte offsets (0x00010003 / 612 layout)
OFFSET_STEP_NO = 0
OFFSET_STEP_TYPE = 8
OFFSET_F_VREF = 16
OFFSET_F_IREF = 20
OFFSET_F_END_TIME = 24
OFFSET_F_END_CV_TIME = 28
OFFSET_F_END_V = 32
OFFSET_F_END_I = 36
OFFSET_F_END_C = 40
OFFSET_N_GOTO_STEP_ID = 92
OFFSET_F_SOC_RATE = 392
OFFSET_F_MAX_CAPACITY = 428
OFFSET_B_USE_ACTUAL_CAPA = 512
OFFSET_B_USE_DATA_STEP_NO = 513

# ASSB converter aliases (some names differ from Excel column order)
SCH_REFERENCE_CURRENT_OFFSET = OFFSET_F_VREF
SCH_END_CURRENT_OFFSET = OFFSET_F_END_I


@dataclass(frozen=True, slots=True)
class SchFieldOffset:
    name: str
    offset: int
    dtype: str
    size: int = 4


VERIFIED_STEP_FIELDS: tuple[SchFieldOffset, ...] = (
    SchFieldOffset("chStepNo", OFFSET_STEP_NO, "int32"),
    SchFieldOffset("nProcType", 4, "int32"),
    SchFieldOffset("step_type_word", OFFSET_STEP_TYPE, "int32"),
    SchFieldOffset("fVref", OFFSET_F_VREF, "float32"),
    SchFieldOffset("fIref", OFFSET_F_IREF, "float32"),
    SchFieldOffset("fEndTime", OFFSET_F_END_TIME, "float32"),
    SchFieldOffset("fEndCVTime", OFFSET_F_END_CV_TIME, "float32"),
    SchFieldOffset("fEndV", OFFSET_F_END_V, "float32"),
    SchFieldOffset("fEndI", OFFSET_F_END_I, "float32"),
    SchFieldOffset("fEndC", OFFSET_F_END_C, "float32"),
    SchFieldOffset("nGotoStepID", OFFSET_N_GOTO_STEP_ID, "uint32"),
    SchFieldOffset("fSocRate", OFFSET_F_SOC_RATE, "float32"),
    SchFieldOffset("fMaxCapacity", OFFSET_F_MAX_CAPACITY, "float32"),
    SchFieldOffset("bUseActualCapa", OFFSET_B_USE_ACTUAL_CAPA, "uint8", 1),
    SchFieldOffset("bUseDataStepNo", OFFSET_B_USE_DATA_STEP_NO, "uint8", 1),
)
