"""Compile StepIntent list to binary step records (Gate C2).

Writes the Ensol v612 / Gate B-verified 612-byte field map:
mode, end conditions, loop/goto, sampling, and SOC (dod_percent).

DC-IR window values remain on the IR only — Excel ``fDCR*`` offsets do not match
the Ensol binary map, and fixtures show no nonzero values at the Excel offsets.
"""

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
from ..schema.ensol_v612 import (
    CCDI_VLIM_DEFAULT_MV,
    OFF_CAP_MODE,
    OFF_CAP_REF_STEP,
    OFF_CURRENT_MA,
    OFF_CV_CUTOFF_MA,
    OFF_DOD_PERCENT,
    OFF_LOOP_COUNT,
    OFF_LOOP_GOTO_ENSOL,
    OFF_LOOP_GOTO_LEGACY,
    OFF_LOOP_RESET_FLAG,
    OFF_RECORD_DV_MV,
    OFF_RECORD_TIME_S,
    OFF_TIME_OR_REST_S,
    OFF_VOLT_OR_VLIM_MV,
    OFF_VOLTAGE_CUTOFF_MV,
)
from ..schema.fields import (
    OFFSET_F_END_C,
    OFFSET_N_GOTO_STEP_ID,
)
from .c_rate import capacity_mAh_from_fraction, current_mA_from_c_rate

if TYPE_CHECKING:
    from ..ir.cell_profile import CellProfile
    from ..ir.step_intent import StepIntent

DEFAULT_RECORD_TIME_S = 60.0
DEFAULT_RECORD_DV_MV = 10.0

_SAMPLING_STEP_TYPES = frozenset({"charge", "discharge", "rest", "ocv", "impedance"})


def compile_steps(intents: list[StepIntent], cell: CellProfile) -> list[bytes]:
    """Compile intents to 612-byte step records."""
    records: list[bytes] = []
    for index, intent in enumerate(intents, start=1):
        records.append(_compile_one_step(index, intent, cell))
    return records


def compile_step_warnings(intents: list[StepIntent]) -> list[str]:
    """Return non-fatal notes about IR fields the binary compiler cannot pack yet."""
    warnings: list[str] = []
    for index, intent in enumerate(intents, start=1):
        if intent.dcr_start_s is not None or intent.dcr_end_s is not None:
            warnings.append(
                f"Step {index}: dcr_start_s/dcr_end_s are kept on the IR only; "
                "binary DCR offsets are externally unresolved (Gate C2/D)."
            )
        if intent.goto_step_id is not None and intent.step_type != "loop":
            warnings.append(
                f"Step {index}: goto_step_id packs legacy nGotoStepID@92 "
                "(ASSB name; semantic still unverified)."
            )
    return warnings


def _resolve_step_type_code(intent: StepIntent) -> int:
    if intent.step_type == "charge":
        if intent.mode == "CC":
            return int(SCH_STEP_TYPE_CC_CHARGE)
        # Default CCCV (also covers mode=None / CV treated as CCCV charge).
        return int(SCH_STEP_TYPE_CCCV)
    if intent.step_type == "discharge":
        return int(SCH_STEP_TYPE_CC_DISCHARGE)
    if intent.step_type == "rest":
        return int(SCH_STEP_TYPE_REST)
    if intent.step_type == "ocv":
        return 0x04
    if intent.step_type == "impedance":
        return 0x05
    if intent.step_type == "cycle":
        return int(SCH_STEP_TYPE_CYCLE_MARKER)
    if intent.step_type == "loop":
        return int(SCH_STEP_TYPE_LOOP)
    if intent.step_type == "end":
        return int(SCH_STEP_TYPE_END)
    raise ValueError(f"Unsupported step_type: {intent.step_type!r}")


def _pack_current_mA(record: bytearray, intent: StepIntent, cell: CellProfile) -> None:
    if intent.current_mA is not None:
        struct.pack_into("<f", record, OFF_CURRENT_MA, float(intent.current_mA))
    elif intent.c_rate is not None:
        current = current_mA_from_c_rate(intent.c_rate, cell)
        struct.pack_into("<f", record, OFF_CURRENT_MA, float(current))


def _pack_sampling(record: bytearray, intent: StepIntent) -> None:
    if intent.step_type not in _SAMPLING_STEP_TYPES:
        return
    record_time = (
        DEFAULT_RECORD_TIME_S if intent.record_time_s is None else float(intent.record_time_s)
    )
    struct.pack_into("<f", record, OFF_RECORD_TIME_S, record_time)
    if intent.record_dV_mV is not None:
        struct.pack_into("<f", record, OFF_RECORD_DV_MV, float(intent.record_dV_mV))
    elif intent.step_type in {"charge", "discharge"}:
        struct.pack_into("<f", record, OFF_RECORD_DV_MV, DEFAULT_RECORD_DV_MV)


def _compile_one_step(step_no: int, intent: StepIntent, cell: CellProfile) -> bytes:
    record = bytearray(STEP_RECORD_SIZE)
    step_type = _resolve_step_type_code(intent)
    struct.pack_into("<i", record, 0, step_no)
    struct.pack_into("<i", record, 8, step_type)

    if intent.end_time_s is not None:
        struct.pack_into("<f", record, OFF_TIME_OR_REST_S, float(intent.end_time_s))

    if intent.step_type == "charge":
        if intent.voltage_v is not None:
            struct.pack_into(
                "<f", record, OFF_VOLT_OR_VLIM_MV, float(intent.voltage_v) * 1000.0
            )
        _pack_current_mA(record, intent, cell)
        if intent.cv_cutoff_mA is not None:
            struct.pack_into("<f", record, OFF_CV_CUTOFF_MA, float(intent.cv_cutoff_mA))
        elif intent.cv_cutoff_c_rate is not None:
            cutoff = current_mA_from_c_rate(intent.cv_cutoff_c_rate, cell)
            struct.pack_into("<f", record, OFF_CV_CUTOFF_MA, float(cutoff))
    elif intent.step_type == "discharge":
        struct.pack_into("<f", record, OFF_VOLT_OR_VLIM_MV, float(CCDI_VLIM_DEFAULT_MV))
        _pack_current_mA(record, intent, cell)
        if intent.end_voltage_v is not None:
            struct.pack_into(
                "<f",
                record,
                OFF_VOLTAGE_CUTOFF_MV,
                float(intent.end_voltage_v) * 1000.0,
            )
    elif intent.voltage_v is not None:
        struct.pack_into(
            "<f", record, OFF_VOLT_OR_VLIM_MV, float(intent.voltage_v) * 1000.0
        )

    if intent.end_capacity_fraction is not None:
        capacity = capacity_mAh_from_fraction(intent.end_capacity_fraction, cell)
        struct.pack_into("<f", record, OFFSET_F_END_C, float(capacity))

    if intent.dod_percent is not None:
        struct.pack_into("<f", record, OFF_DOD_PERCENT, float(intent.dod_percent))

    if intent.step_type == "loop":
        if intent.loop_count is not None:
            struct.pack_into("<I", record, OFF_LOOP_COUNT, int(intent.loop_count))
        goto = intent.loop_goto_step
        if goto is not None:
            # Gate B PNE02 UI writes loop_target@48; Ensol writer uses @564.
            struct.pack_into("<I", record, OFF_LOOP_GOTO_LEGACY, int(goto))
            struct.pack_into("<I", record, OFF_LOOP_GOTO_ENSOL, int(goto))
        if intent.loop_reset_capacity:
            struct.pack_into("<I", record, OFF_LOOP_RESET_FLAG, 1)

    if intent.goto_step_id is not None:
        struct.pack_into("<I", record, OFFSET_N_GOTO_STEP_ID, int(intent.goto_step_id))

    _pack_sampling(record, intent)

    if intent.step_type in {"charge", "discharge", "rest"}:
        # Ensol default capacity-reference flag on active steps.
        record[OFF_CAP_MODE] = 0x01
        if intent.extra.get("cap_ref_step") is not None:
            record[OFF_CAP_REF_STEP] = int(intent.extra["cap_ref_step"]) & 0xFF

    return bytes(record)
