"""Rebuild Gate C5 smoke SCH using a lab-proven 1760-byte header."""

from __future__ import annotations

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
PROJECT = ROOT / "example" / "smoke_rest_cc_end.schproj"
OUTPUT = ROOT / "example" / "smoke_rest_cc_end.sch"


def main() -> None:
    header = bytearray(LAB_TEMPLATE.read_bytes()[:HEADER_SIZE_V3])
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.000").encode("ascii")
    header[0x08 : 0x08 + 63] = b"\x00" * 63
    header[0x08 : 0x08 + len(stamp)] = stamp
    header[HOFF_CTS_TIMESTAMP : HOFF_CTS_TIMESTAMP + 63] = b"\x00" * 63
    header[HOFF_CTS_TIMESTAMP : HOFF_CTS_TIMESTAMP + len(stamp)] = stamp

    name = b"smoke_rest_cc_end.sch"
    header[HOFF_NAME : HOFF_NAME + 100] = b"\x00" * 100
    header[HOFF_NAME : HOFF_NAME + len(name)] = name

    # Lab files leave Ensol 0x3D8 empty; CTS UI uses 0x458.
    for index in range(6):
        struct.pack_into("<f", header, HOFF_SAFETY + index * 4, 0.0)

    limits = safety_limits_from_cell(
        v_max=4.2,
        v_min=2.5,
        nominal_capacity_mAh=80.0,
        max_current_mA=800.0,
    )
    cts_common = (
        limits["max_voltage_mV"],
        limits["min_voltage_mV"],
        0.0,
        limits["cell_capacity_mAh"],
        0.0,
        limits["max_temp_C"],
    )
    for index, value in enumerate(cts_common):
        struct.pack_into("<f", header, HOFF_CTS_COMMON_SAFETY + index * 4, float(value))

    struct.pack_into("<i", header, HOFF_CTS_STEP_HINT, 7)

    project = ScheduleProject.load(PROJECT)
    step_records = compile_steps(project.expand_steps(), project.cell_profile)
    OUTPUT.write_bytes(bytes(header) + b"".join(step_records))

    data = OUTPUT.read_bytes()
    print("wrote", OUTPUT, "size", len(data))
    print("cts@0x458", struct.unpack_from("<6f", data, HOFF_CTS_COMMON_SAFETY))
    print("ensol@0x3d8", struct.unpack_from("<6f", data, HOFF_SAFETY))
    print("capacity@0x464", struct.unpack_from("<f", data, 0x464)[0])
    print("hint@0x484", struct.unpack_from("<i", data, HOFF_CTS_STEP_HINT)[0])


if __name__ == "__main__":
    main()
