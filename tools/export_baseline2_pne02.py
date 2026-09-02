"""Export PNE02 (0x00010003/612) baseline2.sch for Gate B controlled-pair work."""

from __future__ import annotations

import argparse
import struct
import sys
import zipfile
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
from pne_scheduler.schema.ensol_v612 import HOFF_SAFETY, OFF_CAP_MODE  # noqa: E402

PNE02_ZIP = ROOT / "example" / "corpus_zips" / "PNE02.zip"
DEFAULT_OUT = ROOT / "example" / "gate_b_pairs" / "baseline2.sch"
V10003_STEP_SEQUENCE = (0x101, 0x202, 8, 6)  # CCCV, CC_DCHG, LOOP, END
DISCHARGE_TEMPLATE_IN_ZIP = "PNE02/0.1C safety4-DISCHARGE.sch"

# PNE02 500 mA tier — matches CONTROLLED_PAIR_QUEUE.md starting values
CHARGE_CV_MV = 4000.0
CHARGE_CURRENT_MA = 10.0
DISCHARGE_CURRENT_MA = 10.0
DISCHARGE_VLIM_MV = 2000.0
DISCHARGE_END_V_MV = 2500.0
CV_CUTOFF_MA = 2.0
RECORD_INTERVAL_S = 60.0
REST_DURATION_S = 60.0
LOOP_COUNT = 2
SAFETY_LIMITS = (4300.0, 1500.0, 500.0, 0.0, 5000.0, 70.0)


def _find_pne02_template(zip_path: Path) -> tuple[str, bytes]:
    """4-step 0x10003 file starting with CCCV; may include REST before LOOP."""
    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if not name.lower().endswith(".sch"):
                continue
            data = archive.read(name)
            if len(data) != 4208:
                continue
            doc = read_sch_binary_bytes(data)
            if doc.sch_version != 0x00010003 or doc.step_count != 4:
                continue
            if doc.steps[0].step_type_code != 0x101:
                continue
            if doc.steps[-1].step_type_code != 6 or not doc.steps[-2].is_loop:
                continue
            return name, data
    raise FileNotFoundError(
        "No PNE02 0x10003/612 4208-byte CCCV template in corpus zip"
    )


def _discharge_step_template(zip_path: Path) -> bytes:
    with zipfile.ZipFile(zip_path) as archive:
        data = archive.read(DISCHARGE_TEMPLATE_IN_ZIP)
    doc = read_sch_binary_bytes(data)
    if not doc.steps or doc.steps[0].step_type_code != 0x202:
        raise ValueError("Discharge template must start with CC_DCHG")
    return doc.steps[0].record


def _patch_step_record(
    template_record: bytes,
    *,
    volt_or_vlim_mV: float,
    current_mA: float,
    end_v_mV: float = 0.0,
    end_i_mA: float = 0.0,
    record_time_s: float = RECORD_INTERVAL_S,
) -> bytes:
    record = bytearray(template_record)
    struct.pack_into("<f", record, 12, float(volt_or_vlim_mV))
    struct.pack_into("<f", record, 16, float(current_mA))
    struct.pack_into("<f", record, 28, float(end_v_mV))
    struct.pack_into("<f", record, 32, float(end_i_mA))
    struct.pack_into("<f", record, 340, float(record_time_s))
    struct.pack_into("<B", record, OFF_CAP_MODE, 0x01)
    return bytes(record)


def build_baseline2_pne02(
    *,
    zip_path: Path = PNE02_ZIP,
    template_bytes: bytes | None = None,
) -> SchBinaryDocument:
    if template_bytes is None:
        _, template_bytes = _find_pne02_template(zip_path)
    template_doc = read_sch_binary_bytes(template_bytes)
    discharge_skeleton = _discharge_step_template(zip_path)

    charge_rec = _patch_step_record(
        template_doc.steps[0].record,
        volt_or_vlim_mV=CHARGE_CV_MV,
        current_mA=CHARGE_CURRENT_MA,
        end_i_mA=CV_CUTOFF_MA,
    )
    discharge_rec = _patch_step_record(
        discharge_skeleton,
        volt_or_vlim_mV=DISCHARGE_VLIM_MV,
        current_mA=DISCHARGE_CURRENT_MA,
        end_v_mV=DISCHARGE_END_V_MV,
    )
    discharge_rec = _with_step_identity(discharge_rec, step_no=2, step_type_code=0x202)

    loop_source = next(step for step in template_doc.steps if step.is_loop)
    loop_rec = bytearray(loop_source.record)
    struct.pack_into("<I", loop_rec, 52, LOOP_COUNT)
    struct.pack_into("<B", loop_rec, OFF_CAP_MODE, 0x01)
    loop_rec = _with_step_identity(bytes(loop_rec), step_no=3, step_type_code=8)

    end_source = template_doc.steps[-1]
    end_rec = _with_step_identity(end_source.record, step_no=4, step_type_code=6)

    steps = (
        SchBinaryStep(1, 0x101, charge_rec),
        SchBinaryStep(2, 0x202, discharge_rec),
        SchBinaryStep(3, 8, loop_rec),
        SchBinaryStep(4, 6, end_rec),
    )

    header = bytearray(template_doc.header)
    struct.pack_into("<I", header, 4, 0x00010003)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    stamp = timestamp.encode("ascii", errors="ignore")
    header[8 : 8 + len(stamp)] = stamp
    description = b"PNE02 baseline2 Gate-B controlled-pair template"
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


def _with_step_identity(record: bytes, *, step_no: int, step_type_code: int) -> bytes:
    patched = bytearray(record)
    struct.pack_into("<i", patched, 0, step_no)
    struct.pack_into("<i", patched, 8, step_type_code)
    return bytes(patched)


def read_sch_binary_bytes(data: bytes) -> SchBinaryDocument:
    scratch = ROOT / "_baseline2_read.sch"
    scratch.write_bytes(data)
    try:
        return read_sch_binary(scratch)
    finally:
        scratch.unlink(missing_ok=True)


def export_baseline2(
    output_path: Path = DEFAULT_OUT,
    *,
    zip_path: Path = PNE02_ZIP,
) -> dict:
    template_name, template_bytes = _find_pne02_template(zip_path)
    doc = build_baseline2_pne02(zip_path=zip_path, template_bytes=template_bytes)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_sch_binary(doc, output_path)
    parsed = parse_schedule_file(output_path)
    summary = {
        "output": str(
            output_path.relative_to(ROOT)
            if output_path.is_relative_to(ROOT)
            else output_path
        ),
        "template_source": f"PNE02.zip::{template_name}",
        "layout": "0x00010003/612",
        "payload_offset": doc.payload_offset,
        "pne_unit": "PNE02",
        "ctspro_build_ppt": "CYCC-1004-S01-R004-N01",
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
    meta_path.write_text(
        __import__("json").dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUT,
    )
    parser.add_argument(
        "--zip",
        type=Path,
        default=PNE02_ZIP,
    )
    args = parser.parse_args()
    summary = export_baseline2(args.output, zip_path=args.zip)
    print(f"Wrote {args.output}")
    print(f"Template: {summary['template_source']!r}")
    for step in summary["steps"]:
        print(
            f"  step {step['step_no']} {step['step_type']}: "
            f"I={step['f_iref']} mA EndV={step['f_end_v']} EndI={step['f_end_i']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
