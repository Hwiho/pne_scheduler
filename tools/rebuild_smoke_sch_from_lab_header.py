"""Rebuild Gate C5 smoke/probe SCH files using a lab-proven 1760-byte header.

Starts from bytes copied out of a real CTS-authored file instead of
``build_sch_header()``'s all-zero-elsewhere framing, and only overwrites the
offsets this project has already evidence-qualified (timestamp, name, CTS
common-safety block, step hint). Every other header byte stays exactly as a
real CTSEditorPro export wrote it, minimizing unexplained bytes going into a
physical equipment reopen.

Cell-profile-derived values (voltage/current limits, capacity) are read from
the target ``.schproj`` itself rather than hardcoded, so this stays correct
for any project sharing the same header layout.
"""

from __future__ import annotations

import argparse
import struct
from datetime import datetime
from pathlib import Path

from pne_scheduler.engine.compiler import compile_steps
from pne_scheduler.io.header import safety_limits_from_cell
from pne_scheduler.ir.project import ScheduleProject
from pne_scheduler.schema.ensol_v612 import (
    HEADER_SIZE_V3,
    HOFF_CTS_COMMON_SAFETY,
    HOFF_CTS_STEP_HINT,
    HOFF_CTS_TIMESTAMP,
    HOFF_NAME,
    HOFF_SAFETY,
)

ROOT = Path(__file__).resolve().parents[1]
LAB_TEMPLATE = (
    ROOT
    / "example"
    / "fixtures"
    / "capacheck_zip"
    / "9)Bimodal_SJ1300_6040_NCN_capacheck.sch"
)
DEFAULT_PROJECT = ROOT / "example" / "smoke_rest_cc_end.schproj"


def build_from_lab_header(project_path: Path) -> bytes:
    project = ScheduleProject.load(project_path)
    cell = project.cell_profile

    header = bytearray(LAB_TEMPLATE.read_bytes()[:HEADER_SIZE_V3])
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.000").encode("ascii")
    header[0x08 : 0x08 + 63] = b"\x00" * 63
    header[0x08 : 0x08 + len(stamp)] = stamp
    header[HOFF_CTS_TIMESTAMP : HOFF_CTS_TIMESTAMP + 63] = b"\x00" * 63
    header[HOFF_CTS_TIMESTAMP : HOFF_CTS_TIMESTAMP + len(stamp)] = stamp

    name = f"{project.name}.sch".encode("ascii", errors="replace")[:100]
    header[HOFF_NAME : HOFF_NAME + 100] = b"\x00" * 100
    header[HOFF_NAME : HOFF_NAME + len(name)] = name

    limits = safety_limits_from_cell(
        v_max=cell.v_max,
        v_min=cell.v_min,
        nominal_capacity_mAh=cell.nominal_capacity_mAh,
        max_current_mA=cell.max_current_mA,
    )
    max_capacity = float(limits["max_capacity_mAh"])
    # PNE02: capacity at +12 on both safety blocks (see io/header.py notes).
    ensol_values = (
        limits["max_voltage_mV"],
        limits["min_voltage_mV"],
        limits["max_current_mA"],
        max_capacity,
        0.0,
        limits["max_temp_C"],
    )
    for index, value in enumerate(ensol_values):
        struct.pack_into("<f", header, HOFF_SAFETY + index * 4, float(value))

    cts_common = (
        limits["max_voltage_mV"],
        limits["min_voltage_mV"],
        0.0,
        max_capacity,
        0.0,
        limits["max_temp_C"],
    )
    for index, value in enumerate(cts_common):
        struct.pack_into("<f", header, HOFF_CTS_COMMON_SAFETY + index * 4, float(value))

    struct.pack_into("<i", header, HOFF_CTS_STEP_HINT, 7)

    step_records = compile_steps(project.expand_steps(), cell)
    return bytes(header) + b"".join(step_records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "project",
        type=Path,
        nargs="?",
        default=DEFAULT_PROJECT,
        help="Path to a .schproj file (default: %(default)s)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output .sch path (default: <project>.sch next to the project file)",
    )
    args = parser.parse_args()
    output = args.output or args.project.with_suffix(".sch")

    data = build_from_lab_header(args.project)
    output.write_bytes(data)

    print("wrote", output, "size", len(data))
    print("cts@0x458", struct.unpack_from("<6f", data, HOFF_CTS_COMMON_SAFETY))
    print("ensol@0x3d8", struct.unpack_from("<6f", data, HOFF_SAFETY))
    print("capacity@0x3e4/0x464", struct.unpack_from("<f", data, HOFF_SAFETY + 12)[0], struct.unpack_from("<f", data, HOFF_CTS_COMMON_SAFETY + 12)[0])
    print("hint@0x484", struct.unpack_from("<i", data, HOFF_CTS_STEP_HINT)[0])


if __name__ == "__main__":
    main()
