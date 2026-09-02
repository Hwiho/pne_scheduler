"""Scale charge/discharge currents in a .sch while preserving C-rate intent.

Adopted from Ensol sch_maker (`vendor/ensol_sch_maker_ref/battery_scheduler/sch_current_rescaler.py`).
Updates only CCCV/CC charge/CC discharge currents at offsets +16 and +32 (Ensol v612 map).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any

from ..schema.ensol_v612 import (
    HEADER_SIZE_V2,
    HEADER_SIZE_V3,
    OFF_CURRENT_MA,
    OFF_CV_CUTOFF_MA,
    OFF_STEP_TYPE,
    STEP_SIZE,
)
from ..schema.enums import (
    SCH_STEP_TYPE_CC_CHARGE,
    SCH_STEP_TYPE_CC_DISCHARGE,
    SCH_STEP_TYPE_CCCV,
)

CURRENT_DIGITS = 3
C_RATE_DIGITS = 2
ONE_THIRD_C_RATE = 1.0 / 3.0
FRACTION_C_RATE_TOLERANCE = 0.0005

_TYPE_CCCV = int(SCH_STEP_TYPE_CCCV)
_TYPE_CCCH = int(SCH_STEP_TYPE_CC_CHARGE)
_TYPE_CCDI = int(SCH_STEP_TYPE_CC_DISCHARGE)


def detect_header_size(data: bytes) -> int:
    candidates: list[int] = []
    for header_size in (HEADER_SIZE_V3, HEADER_SIZE_V2):
        if len(data) >= header_size and (len(data) - header_size) % STEP_SIZE == 0:
            candidates.append(header_size)
    if not candidates:
        raise ValueError("Unsupported .sch size: cannot align header and 612-byte steps")
    if HEADER_SIZE_V3 in candidates and HEADER_SIZE_V2 not in candidates:
        return HEADER_SIZE_V3
    return HEADER_SIZE_V2


def canonical_c_rate_info(
    current_mA: float,
    capacity_mAh: float,
    *,
    digits: int = C_RATE_DIGITS,
    fraction_tolerance: float = FRACTION_C_RATE_TOLERANCE,
) -> dict[str, Any]:
    if capacity_mAh <= 0:
        raise ValueError("capacity_mAh must be greater than zero")
    raw = float(current_mA) / float(capacity_mAh)
    if fraction_tolerance > 0 and abs(raw - ONE_THIRD_C_RATE) <= fraction_tolerance:
        return {"raw": raw, "value": ONE_THIRD_C_RATE, "label": "1/3"}
    return {"raw": raw, "value": round(raw, digits), "label": None}


def current_from_c_rate(
    c_rate: float,
    capacity_mAh: float,
    *,
    digits: int = CURRENT_DIGITS,
) -> float:
    if capacity_mAh <= 0:
        raise ValueError("capacity_mAh must be greater than zero")
    return round(float(c_rate) * float(capacity_mAh), digits)


def _step_kind(type_code: int) -> str:
    if type_code == _TYPE_CCCV:
        return "CCCV"
    if type_code == _TYPE_CCCH:
        return "CC Charge"
    if type_code == _TYPE_CCDI:
        return "CC Discharge"
    return "Other"


@dataclass(frozen=True, slots=True)
class CurrentFieldRow:
    step: int
    field: str
    kind: str
    value: float
    canonical_c_rate: float | None
    c_rate_label: str | None


def collect_current_fields(
    data: bytes,
    capacity_mAh: float | None = None,
    *,
    current_digits: int = CURRENT_DIGITS,
    c_rate_digits: int = C_RATE_DIGITS,
    fraction_tolerance: float = FRACTION_C_RATE_TOLERANCE,
) -> dict[str, Any]:
    header_size = detect_header_size(data)
    step_count = (len(data) - header_size) // STEP_SIZE
    fields: list[CurrentFieldRow] = []

    for step_index in range(step_count):
        base = header_size + step_index * STEP_SIZE
        block = memoryview(data)[base : base + STEP_SIZE]
        step_num = struct.unpack_from("<i", block, 0)[0]
        type_code = struct.unpack_from("<i", block, OFF_STEP_TYPE)[0] & 0xFFFF

        if type_code in (_TYPE_CCCV, _TYPE_CCCH, _TYPE_CCDI):
            current = struct.unpack_from("<f", block, OFF_CURRENT_MA)[0]
            c_info = (
                canonical_c_rate_info(
                    current,
                    capacity_mAh,
                    digits=c_rate_digits,
                    fraction_tolerance=fraction_tolerance,
                )
                if capacity_mAh
                else {"value": None, "label": None}
            )
            fields.append(
                CurrentFieldRow(
                    step=step_num,
                    field="current_mA",
                    kind=_step_kind(type_code),
                    value=current,
                    canonical_c_rate=c_info["value"],
                    c_rate_label=c_info["label"],
                )
            )

        if type_code == _TYPE_CCCV:
            cvco = struct.unpack_from("<f", block, OFF_CV_CUTOFF_MA)[0]
            c_info = (
                canonical_c_rate_info(
                    cvco,
                    capacity_mAh,
                    digits=c_rate_digits,
                    fraction_tolerance=fraction_tolerance,
                )
                if capacity_mAh
                else {"value": None, "label": None}
            )
            fields.append(
                CurrentFieldRow(
                    step=step_num,
                    field="cv_cutoff_mA",
                    kind="CCCV",
                    value=cvco,
                    canonical_c_rate=c_info["value"],
                    c_rate_label=c_info["label"],
                )
            )

    return {
        "header_size": header_size,
        "step_count": step_count,
        "fields": fields,
    }


def scale_current_fields(
    data: bytes,
    old_capacity_mAh: float,
    new_capacity_mAh: float,
    *,
    current_digits: int = CURRENT_DIGITS,
    c_rate_digits: int = C_RATE_DIGITS,
    fraction_tolerance: float = FRACTION_C_RATE_TOLERANCE,
) -> tuple[bytes, dict[str, Any]]:
    if old_capacity_mAh <= 0 or new_capacity_mAh <= 0:
        raise ValueError("capacity values must be greater than zero")

    factor = float(new_capacity_mAh) / float(old_capacity_mAh)
    out = bytearray(data)
    header_size = detect_header_size(out)
    step_count = (len(out) - header_size) // STEP_SIZE
    changes: list[dict[str, Any]] = []

    for step_index in range(step_count):
        base = header_size + step_index * STEP_SIZE
        block = memoryview(out)[base : base + STEP_SIZE]
        step_num = struct.unpack_from("<i", block, 0)[0]
        type_code = struct.unpack_from("<i", block, OFF_STEP_TYPE)[0] & 0xFFFF

        if type_code in (_TYPE_CCCV, _TYPE_CCCH, _TYPE_CCDI):
            old_current = struct.unpack_from("<f", block, OFF_CURRENT_MA)[0]
            old_c = canonical_c_rate_info(
                old_current,
                old_capacity_mAh,
                digits=c_rate_digits,
                fraction_tolerance=fraction_tolerance,
            )
            new_current = current_from_c_rate(
                old_c["value"],
                new_capacity_mAh,
                digits=current_digits,
            )
            struct.pack_into("<f", block, OFF_CURRENT_MA, float(new_current))
            new_c = canonical_c_rate_info(
                new_current,
                new_capacity_mAh,
                digits=c_rate_digits,
                fraction_tolerance=fraction_tolerance,
            )
            changes.append(
                {
                    "step": step_num,
                    "field": "current_mA",
                    "kind": _step_kind(type_code),
                    "old": old_current,
                    "new": new_current,
                    "old_c": old_c["value"],
                    "old_c_label": old_c["label"],
                    "new_c": new_c["value"],
                    "new_c_label": old_c["label"] or new_c["label"],
                }
            )

        if type_code == _TYPE_CCCV:
            old_cvco = struct.unpack_from("<f", block, OFF_CV_CUTOFF_MA)[0]
            old_c = canonical_c_rate_info(
                old_cvco,
                old_capacity_mAh,
                digits=c_rate_digits,
                fraction_tolerance=fraction_tolerance,
            )
            new_cvco = current_from_c_rate(
                old_c["value"],
                new_capacity_mAh,
                digits=current_digits,
            )
            struct.pack_into("<f", block, OFF_CV_CUTOFF_MA, float(new_cvco))
            new_c = canonical_c_rate_info(
                new_cvco,
                new_capacity_mAh,
                digits=c_rate_digits,
                fraction_tolerance=fraction_tolerance,
            )
            changes.append(
                {
                    "step": step_num,
                    "field": "cv_cutoff_mA",
                    "kind": "CCCV",
                    "old": old_cvco,
                    "new": new_cvco,
                    "old_c": old_c["value"],
                    "old_c_label": old_c["label"],
                    "new_c": new_c["value"],
                    "new_c_label": old_c["label"] or new_c["label"],
                }
            )

    return bytes(out), {
        "header_size": header_size,
        "step_count": step_count,
        "factor": factor,
        "changes": changes,
    }
