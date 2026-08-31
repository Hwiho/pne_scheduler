"""Compile StepIntent list to binary step records."""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

from ..schema import (
    SCH_STEP_TYPE_CC_CHARGE,
    SCH_STEP_TYPE_CC_DISCHARGE,
    SCH_STEP_TYPE_CCCV,
    SCH_STEP_TYPE_CYCLE_MARKER,
    SCH_STEP_TYPE_END,
    SCH_STEP_TYPE_LOOP,
    SCH_STEP_TYPE_REST,
    STEP_RECORD_SIZE,
)
from ..schema.v0x00010003_612 import (
    OFFSET_F_END_C,
    OFFSET_F_END_I,
    OFFSET_F_END_TIME,
    OFFSET_F_END_V,
    OFFSET_F_IREF,
    OFFSET_F_VREF,
    OFFSET_N_GOTO_STEP_ID,
)
from .c_rate import capacity_mAh_from_fraction, current_mA_from_c_rate

if TYPE_CHECKING:
    from ..ir.cell_profile import CellProfile
    from ..ir.step_intent import StepIntent

_STEP_KIND_TO_TYPE = {
    "charge": int(SCH_STEP_TYPE_CCCV),
    "discharge": int(SCH_STEP_TYPE_CC_DISCHARGE),
    "rest": int(SCH_STEP_TYPE_REST),
    "ocv": 0x04,
    "impedance": 0x05,
    "cycle": int(SCH_STEP_TYPE_CYCLE_MARKER),
    "loop": int(SCH_STEP_TYPE_LOOP),
    "end": int(SCH_STEP_TYPE_END),
}


def compile_steps(intents: list[StepIntent], cell: CellProfile) -> list[bytes]:
    records: list[bytes] = []
    for index, intent in enumerate(intents, start=1):
        records.append(_compile_one_step(index, intent, cell))
    return records


def _compile_one_step(step_no: int, intent: StepIntent, cell: CellProfile) -> bytes:
    record = bytearray(STEP_RECORD_SIZE)
    step_type = _STEP_KIND_TO_TYPE[intent.step_type]
    struct.pack_into("<i", record, 0, step_no)
    struct.pack_into("<i", record, 8, step_type)

    if intent.voltage_v is not None:
        struct.pack_into("<f", record, OFFSET_F_VREF, float(intent.voltage_v))
    if intent.end_voltage_v is not None:
        struct.pack_into("<f", record, OFFSET_F_END_V, float(intent.end_voltage_v))
    if intent.end_time_s is not None:
        struct.pack_into("<f", record, OFFSET_F_END_TIME, float(intent.end_time_s))

    if intent.c_rate is not None:
        current = current_mA_from_c_rate(intent.c_rate, cell)
        struct.pack_into("<f", record, OFFSET_F_IREF, float(current))

    if intent.cv_cutoff_c_rate is not None:
        cutoff = current_mA_from_c_rate(intent.cv_cutoff_c_rate, cell)
        struct.pack_into("<f", record, OFFSET_F_END_I, float(cutoff))

    if intent.end_capacity_fraction is not None:
        capacity = capacity_mAh_from_fraction(intent.end_capacity_fraction, cell)
        struct.pack_into("<f", record, OFFSET_F_END_C, float(capacity))

    if intent.goto_step_id is not None:
        struct.pack_into("<I", record, OFFSET_N_GOTO_STEP_ID, int(intent.goto_step_id))

    return bytes(record)
