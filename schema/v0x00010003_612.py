"""Compatibility exports for the partial 0x00010003/612 step layout.

`schema.fields` is the canonical evidence-qualified registry. The legacy
`VERIFIED_STEP_FIELDS` name is retained for callers and includes unverified entries.
"""

from __future__ import annotations

from dataclasses import dataclass

from .enums import DEFAULT_SCH_VERSION, DEFAULT_STEP_SIZE
from .fields import (
    OFFSET_B_USE_ACTUAL_CAPA,
    OFFSET_B_USE_DATA_STEP_NO,
    OFFSET_F_END_C,
    OFFSET_F_END_I,
    OFFSET_F_END_TIME,
    OFFSET_F_END_V,
    OFFSET_F_IREF,
    OFFSET_F_MAX_CAPACITY,
    OFFSET_F_SOC_RATE,
    OFFSET_F_VREF,
    OFFSET_N_GOTO_STEP_ID,
    OFFSET_STEP_NO,
    OFFSET_STEP_TYPE,
    get_step_fields,
)

SCH_FILE_VERSION = DEFAULT_SCH_VERSION
STEP_RECORD_SIZE = DEFAULT_STEP_SIZE

# Header
HEADER_SIZE = 320  # approximate; exact layout TBD in Phase 0.1

# ASSB converter aliases (some names differ from Excel column order)
SCH_REFERENCE_CURRENT_OFFSET = OFFSET_F_VREF
SCH_END_CURRENT_OFFSET = OFFSET_F_END_I


@dataclass(frozen=True, slots=True)
class SchFieldOffset:
    name: str
    offset: int
    dtype: str
    size: int = 4


VERIFIED_STEP_FIELDS: tuple[SchFieldOffset, ...] = tuple(
    SchFieldOffset(field.name, field.offset, field.dtype, field.size)
    for field in get_step_fields(SCH_FILE_VERSION)
)
