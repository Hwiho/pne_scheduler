"""Import Baseline_controlled_pair.zip into example/gate_b_pairs pair directories."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from pne_scheduler.tools.compare_sch import compare_sch_files  # noqa: E402

from pne_scheduler.schema.ensol_v612 import OFF_RECORD_TIME_S  # noqa: E402

PAIR_ROOT = ROOT / "example" / "gate_b_pairs"
BASELINE_NAME = "Sample_baseline_챔버미연동_B.sch"
HEADER_END = 1632
STEP_SIZE = 612

PAIR_SPECS = [
    {
        "dir": "baseline-charge-current",
        "after_name": "Sample_baseline_charge17A_챔버미연동_B.sch",
        "changed_step": 1,
        "ui_field": "Charge current",
        "before_value": {"value": 10000, "unit": "mA"},
        "after_value": {"value": 17000, "unit": "mA"},
        "expected_field": "fVref",
    },
    {
        "dir": "baseline-end-voltage",
        "after_name": "Sample_baseline_4.123V_챔버미연동_B.sch",
        "changed_step": 1,
        "ui_field": "End voltage",
        "before_value": {"value": 4000, "unit": "mV"},
        "after_value": {"value": 4123, "unit": "mV"},
        "expected_field": "mode_value",
    },
    {
        "dir": "baseline-cv-cutoff",
        "after_name": "Sample_baseline_CV_cutoff_3_챔버미연동_B.sch",
        "changed_step": 1,
        "ui_field": "CV cutoff current",
        "before_value": {"value": 2000, "unit": "mA"},
        "after_value": {"value": 3000, "unit": "mA"},
        "expected_field": "fEndI",
    },
    {
        "dir": "baseline-loop-count",
        "after_name": "Sample_baseline_loop_3_챔버미연동_B.sch",
        "changed_step": 3,
        "ui_field": "LOOP count",
        "before_value": {"value": 2, "unit": "count"},
        "after_value": {"value": 3, "unit": "count"},
        "expected_field": "loop_count",
    },
    {
        "dir": "baseline-sampling-interval",
        "after_name": "Sample_baseline_sample2_챔버미연동_B.sch",
        "changed_step": 1,
        "ui_field": "Sampling interval",
        "before_value": {"value": 60, "unit": "s"},
        "after_value": {"value": 120, "unit": "s"},
        "expected_field": "record_time_s",
        "normalize_non_target_record_time_s": True,
    },
]


def _normalize_after(before: bytes, after_raw: bytes, header_end: int) -> bytes:
    after = bytearray(after_raw)
    after[:header_end] = before[:header_end]
    return bytes(after)


def _normalize_after(before: bytes, after_raw: bytes, header_end: int = HEADER_END) -> bytes:
    after = bytearray(after_raw)
    after[:header_end] = before[:header_end]
    return bytes(after)


def _normalize_non_target_record_time_s(
    before: bytes,
    after: bytes,
    *,
    changed_step: int,
    payload_offset: int = HEADER_END,
) -> bytes:
    """CTSPro global sampling writes @340 on multiple steps; keep only changed_step diff."""
    patched = bytearray(after)
    step_count = max(1, (len(before) - payload_offset) // STEP_SIZE)
    for step_no in range(1, step_count + 1):
        if step_no == changed_step:
            continue
        offset = payload_offset + (step_no - 1) * STEP_SIZE + OFF_RECORD_TIME_S
        if offset + 4 > len(patched):
            continue
        patched[offset : offset + 4] = before[offset : offset + 4]
    return bytes(patched)


def _intake_payload(spec: dict, *, pair_clean: bool) -> dict:
    notes = (
        "Imported from Baseline_controlled_pair.zip. Layout 0x00010002/612. "
        "CTSPro saved each variant under a different filename; header bytes "
        "were normalized to before.sch for single-field diff. "
        "PNE unit and CTSPro build still need user confirmation."
    )
    if spec.get("normalize_non_target_record_time_s"):
        notes += (
            " Global sampling UI updated record_time_s@340 on charge+discharge; "
            "non-target step @340 bytes were normalized to before for step-1 diff."
        )
    if not pair_clean:
        notes += " Pair is NOT clean — review comparison.json before writer promotion."
    return {
        "schema": "pne_scheduler.validation_intake/v1",
        "equipment": {
            "label": "baseline_20a",
            "rating": "20A",
            "ctspro_version": "CYCGN-P1107-S01-R001-N022",
            "channel_profile": "Sample/baseline",
            "source": "user_attributed",
        },
        "scope": spec.get("scope", "discovery"),
        "before_file": "before.sch",
        "after_file": "after.sch",
        "changed_step": spec["changed_step"],
        "ui_field": spec["ui_field"],
        "before_value": spec["before_value"],
        "after_value": spec["after_value"],
        "expected_field": spec.get("expected_field"),
        "executed_on_equipment": False,
        "ctspro_reopen_verified": False,
        "screenshots": [],
        "notes": notes,
    }


def import_pairs(zip_path: Path, *, copy_zip: bool = True) -> list[str]:
    zip_path = Path(zip_path)
    if not zip_path.is_file():
        raise FileNotFoundError(zip_path)

    extract_dir = PAIR_ROOT / "_import_staging"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)

    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(extract_dir)

    sch_files = {path.name: path for path in extract_dir.rglob("*.sch")}
    baseline_path = sch_files.get(BASELINE_NAME)
    if baseline_path is None:
        raise FileNotFoundError(f"Missing baseline file {BASELINE_NAME!r} in {zip_path}")

    before = baseline_path.read_bytes()
    header_end = 1632
    written: list[str] = []

    for spec in PAIR_SPECS:
        after_src = sch_files.get(spec["after_name"])
        if after_src is None:
            raise FileNotFoundError(f"Missing {spec['after_name']!r} in {zip_path}")

        pair_dir = PAIR_ROOT / spec["dir"]
        pair_dir.mkdir(parents=True, exist_ok=True)
        before_path = pair_dir / "before.sch"
        after_path = pair_dir / "after.sch"
        before_path.write_bytes(before)
        after_bytes = _normalize_after(before, after_src.read_bytes(), header_end)
        if spec.get("normalize_non_target_record_time_s"):
            after_bytes = _normalize_non_target_record_time_s(
                before,
                after_bytes,
                changed_step=int(spec["changed_step"]),
                payload_offset=header_end,
            )
        after_path.write_bytes(after_bytes)

        report = compare_sch_files(before_path, after_path)
        pair_clean = report["summary"]["controlled_pair_clean"]
        comparison_path = pair_dir / "comparison.json"
        comparison_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        intake_path = pair_dir / "intake.json"
        intake_path.write_text(
            json.dumps(_intake_payload(spec, pair_clean=pair_clean), indent=2, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        written.append(str(pair_dir.relative_to(ROOT)))

    if copy_zip:
        dest_zip = PAIR_ROOT / zip_path.name
        shutil.copy2(zip_path, dest_zip)

    shutil.rmtree(extract_dir)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "zip_path",
        type=Path,
        nargs="?",
        default=Path("c:/Baseline_controlled_pair.zip"),
    )
    parser.add_argument("--no-copy-zip", action="store_true")
    args = parser.parse_args()

    written = import_pairs(args.zip_path, copy_zip=not args.no_copy_zip)
    for row in written:
        print(f"Wrote {row}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
