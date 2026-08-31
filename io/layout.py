"""Detect SCH framing using the version registry with a guarded fallback."""

from __future__ import annotations

import struct

from ..schema.enums import ALTERNATE_STEP_SIZE, DEFAULT_STEP_SIZE, SCH_STEP_TYPES
from ..schema.layouts import SCH_FILE_MAGIC, SchLayout, get_sch_layout


def detect_sch_layout(data: bytes) -> SchLayout | None:
    version = struct.unpack_from("<I", data, 4)[0] if len(data) >= 8 else 0
    magic = struct.unpack_from("<I", data, 0)[0] if len(data) >= 4 else 0

    registered = get_sch_layout(version)
    if magic == SCH_FILE_MAGIC and registered is not None:
        if _score_layout(data, registered.payload_offset, registered.step_size) >= 3:
            return registered

    best: tuple[int, int, int] | None = None
    scan_limit = min(max(len(data) - 12, 0), 5000)
    for payload_offset in range(0, scan_limit, 4):
        if len(data) < payload_offset + 12:
            break
        step_no = struct.unpack_from("<i", data, payload_offset)[0]
        step_type = struct.unpack_from("<i", data, payload_offset + 8)[0] & 0xFFFF
        if step_no != 1 or step_type not in SCH_STEP_TYPES:
            continue
        for step_size in (DEFAULT_STEP_SIZE, ALTERNATE_STEP_SIZE):
            score = _score_layout(data, payload_offset, step_size)
            if best is None or score > best[0]:
                best = (score, payload_offset, step_size)

    if best is None or best[0] < 3:
        return None
    return SchLayout(version=version, payload_offset=best[1], step_size=best[2])


def _score_layout(data: bytes, payload_offset: int, step_size: int) -> int:
    score = 0
    for expected in range(1, 8):
        base = payload_offset + (expected - 1) * step_size
        if base + 12 > len(data):
            break
        step_no = struct.unpack_from("<i", data, base)[0]
        step_type = struct.unpack_from("<i", data, base + 8)[0] & 0xFFFF
        if step_no == expected and step_type in SCH_STEP_TYPES:
            score += 1
    return score
