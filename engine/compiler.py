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
from ..schema.fields import (
    OFFSET_F_END_C,
    OFFSET_F_END_I,
    OFFSET_F_END_TIME,
    OFFSET_F_END_V,
    OFFSET_F_IREF,
    OFFSET_LOOP_COUNT,
    OFFSET_LOOP_GOTO,
    OFFSET_N_GOTO_STEP_ID,
)
from .c_rate import capacity_mAh_from_fraction, current_mA_from_c_rate

if TYPE_CHECKING:
    from ..ir.cell_profile import CellProfile
    from ..ir.step_intent import StepIntent


def compile_steps(intents: list[StepIntent], cell: CellProfile) -> list[bytes]:
    records: list[bytes] = []
    for index, intent in enumerate(intents, start=1):
        records.append(_compile_one_step(index, intent, cell))
    return records


def voltage_to_raw_mV(voltage_v: float) -> float:
    """Encode a volt-scale IR value the way the current corpus stores fEndV."""
    if voltage_v > 20.0:
        return float(voltage_v)
    return float(voltage_v) * 1000.0


def _compile_one_step(step_no: int, intent: StepIntent, cell: CellProfile) -> bytes:
    record = bytearray(STEP_RECORD_SIZE)
    struct.pack_into("<i", record, 0, step_no)
    struct.pack_into("<i", record, 8, _step_type_code(intent))

    if intent.step_type == "rest":
        duration = intent.end_time_s or 0.0
        struct.pack_into("<f", record, OFFSET_F_IREF, float(duration))
        return bytes(record)

    if intent.end_voltage_v is not None:
        struct.pack_into(
            "<f",
            record,
            OFFSET_F_END_V,
            voltage_to_raw_mV(intent.end_voltage_v),
        )
    elif intent.voltage_v is not None:
        struct.pack_into(
            "<f",
            record,
            OFFSET_F_END_V,
            voltage_to_raw_mV(intent.voltage_v),
        )

    if intent.step_type not in {"cycle", "loop", "end"} and intent.end_time_s is not None:
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

    if intent.loop_goto_step is not None:
        struct.pack_into("<I", record, OFFSET_LOOP_GOTO, int(intent.loop_goto_step))
    if intent.loop_count is not None:
        struct.pack_into("<I", record, OFFSET_LOOP_COUNT, int(intent.loop_count))
    if intent.goto_step_id is not None:
        struct.pack_into("<I", record, OFFSET_N_GOTO_STEP_ID, int(intent.goto_step_id))

    return bytes(record)


def _step_type_code(intent: StepIntent) -> int:
    if intent.step_type == "charge":
        if intent.mode == "CCCV":
            return int(SCH_STEP_TYPE_CCCV)
        return int(SCH_STEP_TYPE_CC_CHARGE)
    if intent.step_type == "discharge":
        return int(SCH_STEP_TYPE_CC_DISCHARGE)
    if intent.step_type == "rest":
        return int(SCH_STEP_TYPE_REST)
    if intent.step_type == "cycle":
        return int(SCH_STEP_TYPE_CYCLE_MARKER)
    if intent.step_type == "loop":
        return int(SCH_STEP_TYPE_LOOP)
    if intent.step_type == "end":
        return int(SCH_STEP_TYPE_END)
    if intent.step_type == "ocv":
        return 0x04
    if intent.step_type == "impedance":
        return 0x05
    raise ValueError(f"Unsupported step type: {intent.step_type}")
