"""Export PNE02 baseline3-loop-goto.sch — 6-step schedule for LOOP goto controlled pairs."""

from __future__ import annotations

import argparse
import json
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from pne_scheduler.io.sch_binary import (  # noqa: E402
    SchBinaryDocument,
    SchBinaryStep,
    read_sch_binary,
    write_sch_binary,
)
from pne_scheduler.io.sch_parser import parse_schedule_file  # noqa: E402
from pne_scheduler.schema.ensol_v612 import (  # noqa: E402
    HOFF_SAFETY,
    OFF_CAP_MODE,
    OFF_LOOP_GOTO_ENSOL,
    OFF_LOOP_COUNT,
    OFF_TIME_OR_REST_S,
)
from pne_scheduler.tools.export_baseline2_pne02 import (  # noqa: E402
    CHARGE_CV_MV,
    CHARGE_CURRENT_MA,
    CV_CUTOFF_MA,
    DISCHARGE_CURRENT_MA,
    DISCHARGE_END_V_MV,
    DISCHARGE_VLIM_MV,
    LOOP_COUNT,
    PNE02_ZIP,
    RECORD_INTERVAL_S,
    REST_DURATION_S,
    SAFETY_LIMITS,
    _discharge_step_template,
    _patch_step_record,
    _with_step_identity,
    read_sch_binary_bytes,
)

DEFAULT_OUT = ROOT / "example" / "gate_b_pairs" / "baseline3-loop-goto.sch"
REST_STEP_TYPE = 3
EXPECTED_SIGNATURE = (0x101, REST_STEP_TYPE, 0x202, REST_STEP_TYPE, 8, 6)


def _find_pne02_6step_loop_template(zip_path: Path) -> tuple[str, bytes]:
    """CCCV → REST → CC_DCHG → REST → LOOP → END (0x10003/612, 5432 bytes)."""
    import zipfile

    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if not name.lower().endswith(".sch"):
                continue
            data = archive.read(name)
            if len(data) != 5432:
                continue
            doc = read_sch_binary_bytes(data)
            if doc.sch_version != 0x00010003 or doc.step_count != 6:
                continue
            codes = tuple(step.step_type_code for step in doc.steps)
            if codes != EXPECTED_SIGNATURE:
                continue
            if not doc.steps[-2].is_loop or doc.steps[-1].step_type_code != 6:
                continue
            return name, data
    raise FileNotFoundError(
        "No PNE02 0x10003/612 5432-byte CCCV-REST-CC_DCHG-REST-LOOP-END template in corpus zip"
    )


def _patch_rest_record(template_record: bytes, *, duration_s: float) -> bytes:
    record = bytearray(template_record)
    struct.pack_into("<f", record, OFF_TIME_OR_REST_S, float(duration_s))
    struct.pack_into("<B", record, OFF_CAP_MODE, 0x01)
    return bytes(record)


def _patch_loop_record(
    template_record: bytes,
    *,
    step_no: int,
    loop_count: int = LOOP_COUNT,
    loop_goto_ensol: int = 1,
) -> bytes:
    record = bytearray(template_record)
    struct.pack_into("<i", record, 0, step_no)
    struct.pack_into("<i", record, 8, 8)
    struct.pack_into("<I", record, 48, 0)
    struct.pack_into("<I", record, OFF_LOOP_COUNT, int(loop_count))
    struct.pack_into("<I", record, OFF_LOOP_GOTO_ENSOL, int(loop_goto_ensol))
    struct.pack_into("<B", record, OFF_CAP_MODE, 0x01)
    return bytes(record)


def build_baseline3_loop_goto_pne02(
    *,
    zip_path: Path = PNE02_ZIP,
    template_bytes: bytes | None = None,
) -> SchBinaryDocument:
    if template_bytes is None:
        _, template_bytes = _find_pne02_6step_loop_template(zip_path)
    template_doc = read_sch_binary_bytes(template_bytes)
    discharge_skeleton = _discharge_step_template(zip_path)

    charge_rec = _patch_step_record(
        template_doc.steps[0].record,
        volt_or_vlim_mV=CHARGE_CV_MV,
        current_mA=CHARGE_CURRENT_MA,
        end_i_mA=CV_CUTOFF_MA,
    )
    charge_rec = _with_step_identity(charge_rec, step_no=1, step_type_code=0x101)

    rest1_rec = _patch_rest_record(template_doc.steps[1].record, duration_s=REST_DURATION_S)
    rest1_rec = _with_step_identity(rest1_rec, step_no=2, step_type_code=REST_STEP_TYPE)

    discharge_rec = _patch_step_record(
        discharge_skeleton,
        volt_or_vlim_mV=DISCHARGE_VLIM_MV,
        current_mA=DISCHARGE_CURRENT_MA,
        end_v_mV=DISCHARGE_END_V_MV,
    )
    discharge_rec = _with_step_identity(discharge_rec, step_no=3, step_type_code=0x202)

    rest2_rec = _patch_rest_record(template_doc.steps[3].record, duration_s=REST_DURATION_S)
    rest2_rec = _with_step_identity(rest2_rec, step_no=4, step_type_code=REST_STEP_TYPE)

    loop_rec = _patch_loop_record(
        template_doc.steps[4].record,
        step_no=5,
        loop_count=LOOP_COUNT,
        loop_goto_ensol=1,
    )

    end_rec = _with_step_identity(template_doc.steps[5].record, step_no=6, step_type_code=6)

    steps = (
        SchBinaryStep(1, 0x101, charge_rec),
        SchBinaryStep(2, REST_STEP_TYPE, rest1_rec),
        SchBinaryStep(3, 0x202, discharge_rec),
        SchBinaryStep(4, REST_STEP_TYPE, rest2_rec),
        SchBinaryStep(5, 8, loop_rec),
        SchBinaryStep(6, 6, end_rec),
    )

    header = bytearray(template_doc.header)
    struct.pack_into("<I", header, 4, 0x00010003)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    stamp = timestamp.encode("ascii", errors="ignore")
    header[8 : 8 + len(stamp)] = stamp
    description = b"PNE02 baseline3 LOOP-goto Gate-B template"
    header[72 : 72 + len(description)] = description[:128]
    for index, value in enumerate(SAFETY_LIMITS):
        struct.pack_into("<f", header, HOFF_SAFETY + index * 4, value)

    return SchBinaryDocument(
        path=DEFAULT_OUT,
        sch_version=0x00010003,
        payload_offset=template_doc.payload_offset,
        step_size=template_doc.step_size,
        header=bytes(header),
        steps=steps,
    )


def export_baseline3_loop_goto(
    output_path: Path = DEFAULT_OUT,
    *,
    zip_path: Path = PNE02_ZIP,
) -> dict:
    template_name, template_bytes = _find_pne02_6step_loop_template(zip_path)
    doc = build_baseline3_loop_goto_pne02(zip_path=zip_path, template_bytes=template_bytes)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_sch_binary(doc, output_path)
    parsed = parse_schedule_file(output_path)

    import struct as st

    loop_step = next(step for step in doc.steps if step.is_loop)
    loop_goto_ensol = st.unpack_from("<I", loop_step.record, OFF_LOOP_GOTO_ENSOL)[0]

    summary = {
        "output": str(
            output_path.relative_to(ROOT) if output_path.is_relative_to(ROOT) else output_path
        ),
        "template_source": f"PNE02.zip::{template_name}",
        "layout": "0x00010003/612",
        "payload_offset": doc.payload_offset,
        "file_size": doc.payload_offset + doc.step_count * doc.step_size,
        "pne_unit": "PNE02",
        "ctspro_build_ppt": "CYCC-1004-S01-R004-N01",
        "purpose": "LOOP goto controlled-pair template (multiple goto targets in CTSPro UI)",
        "default_loop_goto_ensol": loop_goto_ensol,
        "controlled_pair_hint": {
            "directory": "pne02-loop-goto",
            "ui_field": "LOOP goto target",
            "before_value": {"value": 1, "unit": "step_no"},
            "after_value": {"value": 2, "unit": "step_no"},
            "expected_field": "loop_goto_ensol",
        },
        "steps": [
            {
                "step_no": step.step_no,
                "step_type": step.step_type,
                "f_vref": step.f_vref,
                "f_iref": step.f_iref,
                "f_end_v": step.f_end_v,
                "f_end_i": step.f_end_i,
            }
            for step in parsed.steps
        ],
    }
    meta_path = output_path.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--zip", type=Path, default=PNE02_ZIP)
    args = parser.parse_args()
    summary = export_baseline3_loop_goto(args.output, zip_path=args.zip)
    print(f"Wrote {args.output}")
    print(f"Template: {summary['template_source']!r}")
    print(f"Size: {summary['file_size']} bytes, LOOP goto@564 = {summary['default_loop_goto_ensol']}")
    for step in summary["steps"]:
        print(
            f"  step {step['step_no']} {step['step_type']}: "
            f"I={step['f_iref']} EndV={step['f_end_v']} EndI={step['f_end_i']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
