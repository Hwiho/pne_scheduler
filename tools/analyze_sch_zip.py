"""Batch-analyze all .sch files in a zip archive."""

from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from pne_scheduler.classify import classify_schedule_filename
from pne_scheduler.io.sch_parser import parse_schedule_file


def analyze_zip(zip_path: Path, out_path: Path | None = None) -> list[dict]:
    results: list[dict] = []
    errors: list[dict] = []

    with zipfile.ZipFile(zip_path) as zf:
        sch_entries = [e for e in zf.infolist() if e.filename.lower().endswith(".sch")]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            for entry in sorted(sch_entries, key=lambda e: e.filename):
                name = Path(entry.filename).name
                data = zf.read(entry)
                dest = tmp_dir / name
                dest.write_bytes(data)

                cls = classify_schedule_filename(name)
                row: dict = {
                    "filename": name,
                    "bytes": entry.file_size,
                    "category": cls.category.value,
                    "qpeed_variant": (
                        cls.qpeed_variant.value if cls.qpeed_variant is not None else None
                    ),
                }
                try:
                    doc = parse_schedule_file(dest)
                    geo = doc.geometry
                    stack = geo.stack_level.primary
                    currents = [s.f_iref for s in doc.steps if s.f_iref > 100]
                    c_rates = [s.c_rate_label for s in doc.steps if s.c_rate_label]
                    fast = sum(1 for s in doc.steps if s.is_fast_charge)

                    row.update(
                        {
                            "ok": True,
                            "sch_version": hex(doc.sch_version) if doc.sch_version else None,
                            "step_size": doc.step_size,
                            "step_count": len(doc.steps),
                            "fp": geo.footprint.fp_id,
                            "fp_source": geo.footprint.source,
                            "cell_mode": geo.cell_mode.mode.value,
                            "k": geo.cell_mode.reaction_cells_k,
                            "l_level": stack.l_value,
                            "l_source": stack.source.value,
                            "l_label": stack.label,
                            "q_nom_mAh": round(geo.capacity.nominal_capacity_mAh),
                            "i_1c_mA": round(geo.capacity.expected_1c_current_mA),
                            "max_current_mA": max(currents) if currents else 0,
                            "c_rate_labels": sorted(set(c_rates)),
                            "fast_charge_steps": fast,
                            "topology": [f"{s.step_no}:{s.step_type}" for s in doc.steps[:20]],
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    row.update({"ok": False, "error": str(exc)})
                    errors.append(row)

                results.append(row)

    summary = _build_summary(results, errors, zip_path)
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps({"summary": summary, "files": results}, indent=2, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
    return results


def _build_summary(results: list[dict], errors: list[dict], zip_path: Path) -> dict:
    ok = [r for r in results if r.get("ok")]
    by_cat = Counter(r["category"] for r in ok)
    by_fp = Counter(r["fp"] for r in ok)
    by_l = Counter(r["l_label"] for r in ok)
    by_mode = Counter(r["cell_mode"] for r in ok)
    by_steps = Counter(r["step_count"] for r in ok)
    by_version = Counter(r.get("sch_version") for r in ok)
    by_step_size = Counter(r.get("step_size") for r in ok)

    c_rate_all: Counter[str] = Counter()
    for r in ok:
        for label in r.get("c_rate_labels", []):
            c_rate_all[label] += 1

    fast_files = [r["filename"] for r in ok if r.get("fast_charge_steps", 0) > 0]

    # Group by filename patterns
    groups: dict[str, list[str]] = defaultdict(list)
    for r in ok:
        fn = r["filename"]
        if "QC" in fn.upper() or "qc" in fn:
            groups["QC / fast-charge"].append(fn)
        elif "capacheck" in fn.lower() or "capa" in fn.lower():
            groups["capacheck / capa"].append(fn)
        elif "cycle" in fn.lower():
            groups["cycle"].append(fn)
        elif "FM" in fn or "formation" in fn.lower():
            groups["formation (FM)"].append(fn)
        elif "8stack" in fn.lower() or "8스택" in fn:
            groups["8-stack"].append(fn)
        elif "Monocell" in fn:
            groups["Monocell FM"].append(fn)
        elif "swelling" in fn.lower():
            groups["swelling"].append(fn)
        else:
            groups["other"].append(fn)

    return {
        "zip": str(zip_path),
        "total_files": len(results),
        "parsed_ok": len(ok),
        "parse_errors": len(errors),
        "by_category": dict(by_cat),
        "by_footprint": dict(by_fp),
        "by_l_level": dict(by_l),
        "by_cell_mode": dict(by_mode),
        "by_step_count": dict(sorted(by_steps.items())),
        "by_sch_version": dict(by_version),
        "by_step_size": dict(by_step_size),
        "c_rate_labels_seen": dict(c_rate_all.most_common()),
        "fast_charge_files": fast_files,
        "filename_groups": {k: len(v) for k, v in sorted(groups.items())},
        "errors": errors,
    }


def main() -> None:
    zip_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"c:\sch.zip")
    out_path = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else Path(__file__).resolve().parents[1] / "example" / "analysis" / "sch_zip_report.json"
    )
    results = analyze_zip(zip_path, out_path)
    ok = sum(1 for r in results if r.get("ok"))
    print(f"Analyzed {len(results)} files ({ok} ok, {len(results)-ok} errors)")
    print(f"Report: {out_path}")


if __name__ == "__main__":
    main()
