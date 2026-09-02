"""Import goto_controlled_pair.zip into example/gate_b_pairs/pne02-loop-goto/."""

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

PAIR_ROOT = ROOT / "example" / "gate_b_pairs"
PAIR_DIR = PAIR_ROOT / "pne02-loop-goto"
HEADER_END = 1632
CTSPRO_BUILD = "CYCC-1004-S01-R004-N01"


def _decode_zip_name(raw: str) -> str:
    try:
        return raw.encode("cp437").decode("cp949")
    except UnicodeError:
        return raw


def _normalize_after(before: bytes, after_raw: bytes, header_end: int = HEADER_END) -> bytes:
    after = bytearray(after_raw)
    after[:header_end] = before[:header_end]
    return bytes(after)


def _find_sch(sch_files: dict[str, Path], marker: str) -> Path:
    for name, path in sch_files.items():
        if marker in name:
            return path
    raise FileNotFoundError(f"No .sch matching {marker!r}")


def _is_before_name(name: str) -> bool:
    if "baseline3-loop-goto" not in name:
        return False
    return "_7_" not in name and "_13_" not in name and not name.startswith("baseline3-loop-goto.sch")


def import_goto_pair(
    zip_path: Path,
    *,
    after_marker: str = "_7_",
    copy_zip: bool = True,
) -> str:
    zip_path = Path(zip_path)
    if not zip_path.is_file():
        raise FileNotFoundError(zip_path)

    extract_dir = PAIR_ROOT / "_import_staging_goto"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)

    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            decoded = _decode_zip_name(info.filename)
            dest = extract_dir / Path(decoded).name
            dest.write_bytes(archive.read(info.filename))

    sch_files = {path.name: path for path in extract_dir.glob("*.sch")}
    before_src = next(
        (path for name, path in sch_files.items() if _is_before_name(name)),
        None,
    )
    if before_src is None:
        raise FileNotFoundError(f"No baseline3 before file in {zip_path}")
    after_src = _find_sch(sch_files, after_marker)

    before = before_src.read_bytes()
    PAIR_DIR.mkdir(parents=True, exist_ok=True)
    before_path = PAIR_DIR / "before.sch"
    after_path = PAIR_DIR / "after.sch"
    before_path.write_bytes(before)
    after_path.write_bytes(_normalize_after(before, after_src.read_bytes()))

    report = compare_sch_files(before_path, after_path)
    pair_clean = report["summary"]["controlled_pair_clean"]
    changed_step = 17
    if report.get("step_changes"):
        changed_step = int(report["step_changes"][0].get("step_no") or changed_step)

    word = {}
    if report.get("step_changes") and report["step_changes"][0].get("words"):
        word = report["step_changes"][0]["words"][0]

    intake = {
        "schema": "pne_scheduler.validation_intake/v1",
        "equipment": {
            "label": "PNE02",
            "rating": "500mA",
            "ctspro_version": CTSPRO_BUILD,
            "channel_profile": "김휘호/baseline3-loop-goto",
            "source": "user_confirmed",
        },
        "scope": "discovery",
        "before_file": "before.sch",
        "after_file": "after.sch",
        "changed_step": changed_step,
        "ui_field": "LOOP goto target",
        "before_value": {"value": int(word.get("primary_before") or 1), "unit": "step_no"},
        "after_value": {"value": int(word.get("primary_after") or 7), "unit": "step_no"},
        "expected_field": word.get("field") or "loop_target",
        "executed_on_equipment": False,
        "ctspro_reopen_verified": False,
        "screenshots": [],
        "notes": (
            "Imported from goto_controlled_pair.zip. CTSEditorPro expanded baseline3 "
            "to 18 steps (0x10002/612, 12648 B) on save; controlled change is on LOOP "
            "step 17: loop_target@48 (legacy goto). loop_goto_ensol@564 stayed 1 in both "
            "files — PNE02 UI writes goto to offset +48, not +564."
        ),
    }
    if not pair_clean:
        intake["notes"] += " Pair is NOT clean — review comparison.json."

    (PAIR_DIR / "comparison.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (PAIR_DIR / "intake.json").write_text(
        json.dumps(intake, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if copy_zip:
        shutil.copy2(zip_path, PAIR_ROOT / zip_path.name)

    shutil.rmtree(extract_dir)
    return str(PAIR_DIR.relative_to(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "zip_path",
        type=Path,
        nargs="?",
        default=Path("c:/goto_controlled_pair.zip"),
    )
    parser.add_argument(
        "--after-marker",
        default="_7_",
        help="Substring matching the after .sch (default: goto step 7 variant)",
    )
    parser.add_argument("--no-copy-zip", action="store_true")
    args = parser.parse_args()

    written = import_goto_pair(
        args.zip_path,
        after_marker=args.after_marker,
        copy_zip=not args.no_copy_zip,
    )
    print(f"Wrote {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
