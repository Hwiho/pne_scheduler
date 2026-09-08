"""Build guarded reopen candidates from the proven PNE02 v3 lab header.

This is not a production writer.  It preserves the unknown header bytes from a
CTSPro-authored fixture, replaces only the evidence-qualified common fields,
and appends software-compiled 612-byte steps.  Callers must label every result
as reopen-only until the exact output hash has passed CTSPro review.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path

from ..engine.compiler import compile_step_warnings, compile_steps
from ..ir.project import ScheduleProject
from ..schema.ensol_v612 import (
    HEADER_SIZE_V3,
    HOFF_CTS_COMMON_SAFETY,
    HOFF_CTS_STEP_HINT,
    HOFF_CTS_TIMESTAMP,
    HOFF_NAME,
    HOFF_SAFETY,
)
from ..validate.preflight import validate_project
from .header import safety_limits_from_cell

ROOT = Path(__file__).resolve().parents[1]
PNE02_LAB_HEADER_TEMPLATE = (
    ROOT
    / "example"
    / "fixtures"
    / "capacheck_zip"
    / "9)Bimodal_SJ1300_6040_NCN_capacheck.sch"
)


@dataclass(frozen=True, slots=True)
class LabHeaderCandidate:
    data: bytes
    step_count: int
    template_path: Path
    template_sha256: str
    warnings: tuple[str, ...]


def build_pne02_reopen_candidate(
    project: ScheduleProject,
    *,
    timestamp: str,
    template_path: Path = PNE02_LAB_HEADER_TEMPLATE,
) -> LabHeaderCandidate:
    """Return a non-executable PNE02/0x00010003 reopen candidate."""
    if project.sch_version != 0x00010003:
        raise ValueError("PNE02 lab-header candidates require sch_version 0x00010003")
    encoded_timestamp = timestamp.encode("ascii")
    if len(encoded_timestamp) > 63:
        raise ValueError("timestamp must fit the 63-byte CTS header field")

    preflight = validate_project(project, purpose="experimental_build")
    if preflight.errors:
        detail = "; ".join(f"{issue.code}: {issue.message}" for issue in preflight.errors)
        raise ValueError(f"Candidate preflight failed: {detail}")

    source = template_path.read_bytes()
    if len(source) < HEADER_SIZE_V3:
        raise ValueError(f"Lab header template is shorter than {HEADER_SIZE_V3} bytes")
    header = bytearray(source[:HEADER_SIZE_V3])
    _replace_ascii(header, 0x08, 63, encoded_timestamp)
    _replace_ascii(header, HOFF_CTS_TIMESTAMP, 63, encoded_timestamp)
    name = f"{project.name}.sch".encode("ascii", errors="replace")[:100]
    _replace_ascii(header, HOFF_NAME, 100, name)

    cell = project.cell_profile
    limits = safety_limits_from_cell(
        v_max=cell.v_max,
        v_min=cell.v_min,
        nominal_capacity_mAh=cell.nominal_capacity_mAh,
        max_current_mA=cell.max_current_mA,
    )
    max_capacity = float(limits["max_capacity_mAh"])
    ensol_values = (
        limits["max_voltage_mV"],
        limits["min_voltage_mV"],
        limits["max_current_mA"],
        max_capacity,
        0.0,
        limits["max_temp_C"],
    )
    cts_common = (
        limits["max_voltage_mV"],
        limits["min_voltage_mV"],
        0.0,
        max_capacity,
        0.0,
        limits["max_temp_C"],
    )
    for index, value in enumerate(ensol_values):
        struct.pack_into("<f", header, HOFF_SAFETY + index * 4, float(value))
    for index, value in enumerate(cts_common):
        struct.pack_into("<f", header, HOFF_CTS_COMMON_SAFETY + index * 4, float(value))

    # All secured PNE02 v3 corpus files carry the constant value 7 here,
    # independent of their actual 11/15/73/167 record count.
    struct.pack_into("<i", header, HOFF_CTS_STEP_HINT, 7)

    steps = project.expand_steps()
    records = compile_steps(steps, cell)
    warnings = [
        *(f"{issue.code}: {issue.message}" for issue in preflight.warnings),
        *compile_step_warnings(steps),
    ]
    return LabHeaderCandidate(
        data=bytes(header) + b"".join(records),
        step_count=len(records),
        template_path=template_path,
        template_sha256=hashlib.sha256(source).hexdigest(),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _replace_ascii(buffer: bytearray, offset: int, size: int, value: bytes) -> None:
    buffer[offset : offset + size] = b"\x00" * size
    buffer[offset : offset + len(value)] = value


__all__ = [
    "LabHeaderCandidate",
    "PNE02_LAB_HEADER_TEMPLATE",
    "build_pne02_reopen_candidate",
]
