"""Import PNE02_controlled_pair.zip into example/gate_b_pairs pair directories."""

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

from pne_scheduler.schema.ensol_v612 import OFF_CAP_MODE  # noqa: E402

PAIR_ROOT = ROOT / "example" / "gate_b_pairs"
HEADER_END = 1632
STEP_SIZE = 612
CTSPRO_BUILD = "CYCC-1004-S01-R004-N01"

BASELINE_MARKERS = (
    "charge_17mA",
    "CV_3mA",
    "discharge_19mA",
    "loop_3",
    "record_charge",
    "record_dis",
    "rest_60s",
    "rest_123s",
    "V_cutoff",
)

PAIR_SPECS = [
    {
        "dir": "pne02-charge-current",
        "after_marker": "charge_17mA",
        "changed_step": 1,
        "ui_field": "Charge current",
        "before_value": {"value": 10, "unit": "mA"},
        "after_value": {"value": 17, "unit": "mA"},
        "expected_field": "fVref",
    },
    {
        "dir": "pne02-discharge-current",
        "after_marker": "discharge_19mA",
        "changed_step": 2,
        "ui_field": "Discharge current",
        "before_value": {"value": 10, "unit": "mA"},
        "after_value": {"value": 19, "unit": "mA"},
        "expected_field": "fVref",
    },
    {
        "dir": "pne02-cv-cutoff",
        "after_marker": "CV_3mA",
        "changed_step": 1,
        "ui_field": "CV cutoff current",
        "before_value": {"value": 2, "unit": "mA"},
        "after_value": {"value": 3, "unit": "mA"},
        "expected_field": "fEndI",
        "normalize_cap_mode_step1": True,
    },
    {
        "dir": "pne02-end-voltage",
        "after_marker": "V_cutoff",
        "changed_step": 2,
        "ui_field": "End voltage (discharge)",
        "before_value": {"value": 2500, "unit": "mV"},
        "after_value": {"value": 3123, "unit": "mV"},
        "expected_field": "fEndV",
    },
    {
        "dir": "pne02-loop-count",
        "after_marker": "loop_3",
        "changed_step": 3,
        "ui_field": "LOOP count",
        "before_value": {"value": 2, "unit": "count"},
        "after_value": {"value": 3, "unit": "count"},
        "expected_field": "loop_count",
    },
    {
        "dir": "pne02-rest-duration",
        "before_marker": "rest_60s",
        "after_marker": "rest_123s",
        "changed_step": 2,
        "ui_field": "Rest duration",
        "before_value": {"value": 60, "unit": "s"},
        "after_value": {"value": 123, "unit": "s"},
        "expected_field": "fIref",
    },
    {
        "dir": "pne02-sampling-interval",
        "after_marker": "record_charge",
        "changed_step": 1,
        "ui_field": "Sampling interval (charge step)",
        "before_value": {"value": 60, "unit": "s"},
        "after_value": {"value": 120, "unit": "s"},
        "expected_field": "record_time_s",
    },
    {
        "dir": "pne02-sampling-interval-discharge",
        "after_marker": "record_dis",
        "changed_step": 2,
        "ui_field": "Sampling interval (discharge step)",
        "before_value": {"value": 60, "unit": "s"},
        "after_value": {"value": 120, "unit": "s"},
        "expected_field": "record_time_s",
        "scope": "discovery",
    },
]


def _decode_zip_name(raw: str) -> str:
    try:
        return raw.encode("cp437").decode("cp949")
    except UnicodeError:
        return raw


def _normalize_after(before: bytes, after_raw: bytes, header_end: int = HEADER_END) -> bytes:
    after = bytearray(after_raw)
    after[:header_end] = before[:header_end]
    return bytes(after)


def _normalize_cap_mode_step1(
    data: bytes,
    *,
    payload_offset: int = HEADER_END,
    cap_value: int = 0,
) -> bytes:
    """Align CCCV step-1 cap_mode@496 to corpus default (PNE02 CV-cutoff coupling fix)."""
    patched = bytearray(data)
    cap_offset = payload_offset + OFF_CAP_MODE
    if cap_offset < len(patched):
        patched[cap_offset] = cap_value
    return bytes(patched)


def _find_sch(sch_files: dict[str, Path], marker: str) -> Path:
    for name, path in sch_files.items():
        if marker in name:
            return path
    raise FileNotFoundError(f"No .sch matching {marker!r}")


def _is_baseline_name(name: str) -> bool:
    if "baseline2" not in name:
        return False
    return not any(token in name for token in BASELINE_MARKERS)


def _intake_payload(spec: dict, *, pair_clean: bool) -> dict:
    notes = (
        "Imported from PNE02_controlled_pair.zip (user confirmed PNE02). "
        "Layout 0x00010002/612 (4080 B). CTSPro save filenames differ; "
        "header bytes were normalized to before.sch for single-field diff."
    )
    if spec.get("normalize_cap_mode_step1"):
        notes += (
            " CV-cutoff save co-writes cap_mode@496 (1→0 on after); before step1 "
            "cap496 was normalized 1→0 to match PNE02 corpus default and isolate fEndI@32."
        )
    if not pair_clean:
        notes += " Pair is NOT clean — review comparison.json before writer promotion."
    return {
        "schema": "pne_scheduler.validation_intake/v1",
        "equipment": {
            "label": "PNE02",
            "rating": "500mA",
            "ctspro_version": CTSPRO_BUILD,
            "channel_profile": "김휘호/baseline2",
            "source": "user_confirmed",
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

    extract_dir = PAIR_ROOT / "_import_staging_pne02"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)

    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            decoded = _decode_zip_name(info.filename)
            dest = extract_dir / Path(decoded).name
            dest.write_bytes(archive.read(info.filename))

    sch_files = {path.name: path for path in extract_dir.glob("*.sch")}
    baseline_path = next(
        (path for name, path in sch_files.items() if _is_baseline_name(name)),
        None,
    )
    if baseline_path is None:
        raise FileNotFoundError(f"No baseline2 before file in {zip_path}")

    baseline_before = baseline_path.read_bytes()
    written: list[str] = []

    for spec in PAIR_SPECS:
        before_src = (
            _find_sch(sch_files, spec["before_marker"])
            if spec.get("before_marker")
            else baseline_path
        )
        after_src = _find_sch(sch_files, spec["after_marker"])
        before = before_src.read_bytes()
        if spec.get("normalize_cap_mode_step1"):
            before = _normalize_cap_mode_step1(before)

        pair_dir = PAIR_ROOT / spec["dir"]
        pair_dir.mkdir(parents=True, exist_ok=True)
        before_path = pair_dir / "before.sch"
        after_path = pair_dir / "after.sch"
        before_path.write_bytes(before)
        after_bytes = _normalize_after(before, after_src.read_bytes())
        if spec.get("normalize_cap_mode_step1"):
            after_bytes = _normalize_cap_mode_step1(after_bytes)
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
        default=Path("c:/PNE02_controlled_pair.zip"),
    )
    parser.add_argument("--no-copy-zip", action="store_true")
    args = parser.parse_args()

    written = import_pairs(args.zip_path, copy_zip=not args.no_copy_zip)
    for row in written:
        print(f"Wrote {row}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
