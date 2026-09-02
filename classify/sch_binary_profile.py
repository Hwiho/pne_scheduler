"""Compact binary fingerprints for SCH schedule clustering."""

from __future__ import annotations

import struct

from ..io.layout import detect_sch_layout
from ..schema.ensol_v612 import (
    OFF_CURRENT_MA,
    OFF_LOOP_COUNT,
    OFF_LOOP_GOTO_ENSOL,
    OFF_LOOP_GOTO_LEGACY,
    OFF_STEP_TYPE,
)
from ..schema.enums import (
    SCH_STEP_TYPE_CC_CHARGE,
    SCH_STEP_TYPE_CC_DISCHARGE,
    SCH_STEP_TYPE_CCCV,
    SCH_STEP_TYPE_END,
    SCH_STEP_TYPE_LOOP,
)

_TYPE_SHORT = {
    int(SCH_STEP_TYPE_CCCV): "CCCV",
    int(SCH_STEP_TYPE_CC_CHARGE): "CC_CHG",
    int(SCH_STEP_TYPE_CC_DISCHARGE): "CC_DCHG",
    int(SCH_STEP_TYPE_LOOP): "LOOP",
    int(SCH_STEP_TYPE_END): "END",
    0x0301: "REST",
    0x0401: "OCV",
    0x0501: "IMP",
}


def _read_f32(record: bytes, offset: int) -> float:
    return struct.unpack_from("<f", record, offset)[0]


def _read_u32(record: bytes, offset: int) -> int:
    return struct.unpack_from("<I", record, offset)[0]


def _read_i32(record: bytes, offset: int) -> int:
    return struct.unpack_from("<i", record, offset)[0]


def _type_short(type_code: int) -> str:
    masked = type_code & 0xFFFF
    return _TYPE_SHORT.get(masked, f"T{masked:04x}")


def step_signature_from_data(data: bytes) -> str | None:
    """Return a compact step-type sequence, e.g. ``CCCV-REST-CC_DCHG-LOOP-END``."""
    profile = binary_profile(data)
    if profile is None:
        return None
    return profile["step_signature"]


def binary_profile(data: bytes) -> dict | None:
    layout = detect_sch_layout(data)
    if layout is None:
        return None

    payload, step_size = layout.payload_offset, layout.step_size
    version = struct.unpack_from("<I", data, 4)[0] if len(data) >= 8 else None
    steps: list[tuple[int, int, bytes]] = []
    index = 0
    while payload + index * step_size + 12 <= len(data):
        record = data[payload + index * step_size : payload + (index + 1) * step_size]
        step_no = _read_i32(record, 0)
        type_code = _read_i32(record, OFF_STEP_TYPE) & 0xFFFF
        if step_no <= 0:
            break
        steps.append((step_no, type_code, record))
        if type_code == int(SCH_STEP_TYPE_END):
            break
        index += 1

    loop_goto = {"only_48": 0, "only_564": 0, "both": 0, "neither": 0}
    currents: list[float] = []
    max_current = 0.0
    loop_counts: list[int] = []
    sig_parts: list[str] = []
    for _step_no, type_code, record in steps:
        sig_parts.append(_type_short(type_code))
        if type_code == int(SCH_STEP_TYPE_LOOP):
            g48 = _read_u32(record, OFF_LOOP_GOTO_LEGACY)
            g564 = (
                _read_u32(record, OFF_LOOP_GOTO_ENSOL)
                if len(record) > OFF_LOOP_GOTO_ENSOL + 4
                else 0
            )
            if g48 and g564:
                loop_goto["both"] += 1
            elif g48:
                loop_goto["only_48"] += 1
            elif g564:
                loop_goto["only_564"] += 1
            else:
                loop_goto["neither"] += 1
            if len(record) > OFF_LOOP_COUNT + 4:
                loop_counts.append(_read_u32(record, OFF_LOOP_COUNT))
        if type_code in (0x0101, 0x0201, 0x0202):
            i_ma = _read_f32(record, OFF_CURRENT_MA)
            if i_ma > 0:
                currents.append(i_ma)
                max_current = max(max_current, i_ma)

    return {
        "version": f"0x{version:08x}" if version is not None else None,
        "payload_offset": payload,
        "step_size": step_size,
        "file_bytes": len(data),
        "step_count": len(steps),
        "step_signature": "-".join(sig_parts),
        "loop_steps": sum(1 for _, tc, _ in steps if tc == int(SCH_STEP_TYPE_LOOP)),
        "loop_goto": loop_goto,
        "loop_count_max": max(loop_counts) if loop_counts else None,
        "current_mA_max": round(max_current, 4) if max_current else None,
        "current_mA_p50": round(sorted(currents)[len(currents) // 2], 4) if currents else None,
    }
