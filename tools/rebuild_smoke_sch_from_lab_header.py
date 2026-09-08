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

from pne_scheduler.io.lab_header_writer import (
    PNE02_LAB_HEADER_TEMPLATE,
    build_pne02_reopen_candidate,
)
from pne_scheduler.ir.project import ScheduleProject
from pne_scheduler.schema.ensol_v612 import (
    HOFF_CTS_COMMON_SAFETY,
    HOFF_CTS_STEP_HINT,
    HOFF_SAFETY,
)

ROOT = Path(__file__).resolve().parents[1]
LAB_TEMPLATE = PNE02_LAB_HEADER_TEMPLATE
DEFAULT_PROJECT = ROOT / "example" / "smoke_rest_cc_end.schproj"


def build_from_lab_header(project_path: Path) -> bytes:
    project = ScheduleProject.load(project_path)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.000")
    return build_pne02_reopen_candidate(project, timestamp=timestamp).data


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
