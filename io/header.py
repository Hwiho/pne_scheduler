"""Build CTSPro-compatible SCH file headers (Gate C1).

Framing follows the Ensol sch_maker layout and observed 0x00010003 corpus files:
1760-byte header, magic ``0x000B4D71``, version at offset 4, safety floats at 0x3D8.
"""

from __future__ import annotations

import struct
from datetime import datetime
from typing import Mapping

from ..schema.ensol_v612 import (
    FILE_SIGNATURE,
    HEADER_SIZE_V3,
    HOFF_AUTHOR,
    HOFF_NAME,
    HOFF_SAFETY,
    HOFF_SIGNATURE,
    HOFF_TIMESTAMP_2,
    HOFF_TIMESTAMP_3,
)
from ..schema.enums import SchFileVersion
from ..schema.layouts import SCH_FILE_MAGIC

# Ensol writer also stamps these control words before the schedule name.
_HOFF_NAME_FLAG_A = 0x290
_HOFF_NAME_FLAG_B = 0x294
_HOFF_STEP_HINT = 0x404

_DEFAULT_SAFETY_MV_MA = {
    "max_voltage_mV": 4300.0,
    "min_voltage_mV": 1500.0,
    "max_current_mA": 0.0,
    "min_current_mA": 0.0,
    "max_capacity_mAh": 200.0,
    "max_temp_C": 70.0,
}


def build_sch_header_v00010003(
    *,
    schedule_name: str,
    author: str = "pne_scheduler",
    safety: Mapping[str, float] | None = None,
    created_at: datetime | None = None,
) -> bytes:
    """Return a 1760-byte ``0x00010003`` header (no 512-byte placeholder)."""
    header = bytearray(HEADER_SIZE_V3)
    struct.pack_into("<I", header, 0, SCH_FILE_MAGIC)
    struct.pack_into("<I", header, 4, int(SchFileVersion.V0X00010003))

    stamp = (created_at or datetime.now()).strftime("%Y-%m-%d %H:%M:%S.000")
    _write_ascii(header, 0x08, stamp, limit=63)
    _write_bytes(header, HOFF_SIGNATURE, FILE_SIGNATURE)
    _write_cp949(header, HOFF_AUTHOR, author, limit=60)
    _write_ascii(header, HOFF_TIMESTAMP_2, stamp, limit=63)

    header[_HOFF_NAME_FLAG_A] = 1
    header[_HOFF_NAME_FLAG_B] = 2
    file_label = schedule_name if schedule_name.lower().endswith(".sch") else f"{schedule_name}.sch"
    _write_cp949(header, HOFF_NAME, file_label, limit=100)
    _write_ascii(header, HOFF_TIMESTAMP_3, stamp, limit=63)

    limits = {**_DEFAULT_SAFETY_MV_MA, **dict(safety or {})}
    values = (
        float(limits["max_voltage_mV"]),
        float(limits["min_voltage_mV"]),
        float(limits["max_current_mA"]),
        float(limits["min_current_mA"]),
        float(limits["max_capacity_mAh"]),
        float(limits["max_temp_C"]),
    )
    for index, value in enumerate(values):
        struct.pack_into("<f", header, HOFF_SAFETY + index * 4, value)

    # Ensol writer stamps this nonzero control word; corpus often leaves it 0.
    struct.pack_into("<i", header, _HOFF_STEP_HINT, 7)
    return bytes(header)


def safety_limits_from_cell(
    *,
    v_max: float,
    v_min: float,
    nominal_capacity_mAh: float,
    max_current_mA: float | None = None,
    max_temp_C: float = 70.0,
) -> dict[str, float]:
    """Map CellProfile-style volts/amps into header safety millivolt/milliamp units."""
    return {
        "max_voltage_mV": float(v_max) * 1000.0,
        "min_voltage_mV": float(v_min) * 1000.0,
        "max_current_mA": float(max_current_mA or 0.0),
        "min_current_mA": 0.0,
        "max_capacity_mAh": max(float(nominal_capacity_mAh) * 10.0, float(nominal_capacity_mAh)),
        "max_temp_C": float(max_temp_C),
    }


def _write_ascii(buffer: bytearray, offset: int, text: str, *, limit: int) -> None:
    encoded = text.encode("ascii", errors="replace")[:limit]
    buffer[offset : offset + len(encoded)] = encoded


def _write_cp949(buffer: bytearray, offset: int, text: str, *, limit: int) -> None:
    try:
        encoded = text.encode("cp949", errors="replace")[:limit]
    except LookupError:
        encoded = text.encode("ascii", errors="replace")[:limit]
    buffer[offset : offset + len(encoded)] = encoded


def _write_bytes(buffer: bytearray, offset: int, data: bytes) -> None:
    buffer[offset : offset + len(data)] = data
