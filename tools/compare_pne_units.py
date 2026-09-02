"""Cross-unit PNE cycler comparison from lab zip corpora."""

from __future__ import annotations

import json
import struct
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from pne_scheduler.classify import classify_schedule_filename
from pne_scheduler.schema.corpus_paths import default_corpus_zip_map
from pne_scheduler.schema.equipment import rating_hint_for_unit
from pne_scheduler.schema.equipment_registry import get_unit_equipment_profile
from pne_scheduler.schema.lab_corpus import validate_unit_corpus_zip
from pne_scheduler.io.layout import detect_sch_layout
from pne_scheduler.schema.ensol_v612 import (
    HOFF_SAFETY,
    OFF_CURRENT_MA,
    OFF_CV_CUTOFF_MA,
    OFF_LOOP_GOTO_ENSOL,
    OFF_LOOP_GOTO_LEGACY,
    OFF_STEP_TYPE,
    OFF_VOLT_OR_VLIM_MV,
)
from pne_scheduler.schema.enums import SCH_STEP_TYPE_LOOP

DEFAULT_ZIPS: dict[str, Path] = default_corpus_zip_map()

CHARGE_TYPES = {0x0101, 0x0201, 0x0202}


def _rf32(record: bytes, offset: int) -> float:
    return struct.unpack_from("<f", record, offset)[0]


def _ri32(record: bytes, offset: int) -> int:
    return struct.unpack_from("<i", record, offset)[0]


def _ru32(record: bytes, offset: int) -> int:
    return struct.unpack_from("<I", record, offset)[0]


def _scan_unit(unit: str, zip_path: Path) -> dict:
    zip_error = validate_unit_corpus_zip(unit, zip_path)
    if zip_error:
        return {"unit": unit, "error": zip_error}
    if not zip_path.is_file():
        return {"unit": unit, "error": "missing"}

    equip = get_unit_equipment_profile(unit)
    categories: Counter = Counter()
    versions: Counter = Counter()
    step_sizes: Counter = Counter()
    payload_offsets: Counter = Counter()
    step_counts: Counter = Counter()
    layout_sigs: Counter = Counter()
    loop_goto = Counter()
    cap_modes: Counter = Counter()
    cv_ratios: list[float] = []
    charge_currents: list[float] = []
    safety_tuples: Counter = Counter()
    parse_errors = 0

    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".sch"):
                continue
            match = classify_schedule_filename(name)
            categories[match.category.value] += 1
            try:
                data = zf.read(name)
                layout = detect_sch_layout(data)
                if layout is None:
                    parse_errors += 1
                    continue

                version = struct.unpack_from("<I", data, 4)[0]
                ver_s = f"0x{version:08x}"
                versions[ver_s] += 1
                step_sizes[layout.step_size] += 1
                payload_offsets[layout.payload_offset] += 1

                payload, step_size = layout.payload_offset, layout.step_size
                steps = 0
                idx = 0
                while payload + idx * step_size + 12 <= len(data):
                    record = data[payload + idx * step_size : payload + (idx + 1) * step_size]
                    step_no = _ri32(record, 0)
                    type_code = _ri32(record, OFF_STEP_TYPE) & 0xFFFF
                    if step_no <= 0:
                        break
                    steps += 1
                    if type_code == int(SCH_STEP_TYPE_LOOP):
                        g48 = _ru32(record, OFF_LOOP_GOTO_LEGACY)
                        g564 = (
                            _ru32(record, OFF_LOOP_GOTO_ENSOL)
                            if len(record) > OFF_LOOP_GOTO_ENSOL + 4
                            else 0
                        )
                        if g48 and g564:
                            loop_goto["both"] += 1
                        elif g48:
                            loop_goto["only_48"] += 1
                        elif g564:
                            loop_goto["only_564"] += 1
                        else:
                            loop_goto["neither"] += 1
                    if type_code in CHARGE_TYPES:
                        i_ma = _rf32(record, OFF_CURRENT_MA)
                        cv = _rf32(record, OFF_CV_CUTOFF_MA)
                        v = _rf32(record, OFF_VOLT_OR_VLIM_MV)
                        if 0.1 < i_ma < 200_000:
                            charge_currents.append(i_ma)
                        if cv > 0 and i_ma > 0:
                            cv_ratios.append(cv / i_ma)
                        _ = v
                    if len(record) > 496:
                        cap_modes[record[496]] += 1
                    if type_code == 6:
                        break
                    idx += 1

                step_counts[steps] += 1
                layout_sigs[f"{ver_s}/{step_size}B/{steps}st"] += 1

                if len(data) >= HOFF_SAFETY + 16:
                    max_v = _rf32(data, HOFF_SAFETY)
                    min_v = _rf32(data, HOFF_SAFETY + 4)
                    max_i = _rf32(data, HOFF_SAFETY + 8)
                    min_i = _rf32(data, HOFF_SAFETY + 12)
                    if max_i > 0 and max_i < 1_000_000:
                        safety_tuples[
                            (round(max_v), round(min_v), round(max_i), round(min_i))
                        ] += 1
            except Exception:
                parse_errors += 1

    currents_sorted = sorted(charge_currents)
    cv_mode = Counter(round(r, 3) for r in cv_ratios).most_common(6)

    def pct(n: int, total: int) -> float:
        return round(100 * n / total, 1) if total else 0.0

    total = sum(categories.values())
    classified_cats = {k: v for k, v in categories.items() if k != "unknown"}

    return {
        "unit": unit,
        "zip": zip_path.name,
        "ctspro_build": equip.ctspro_build if equip else None,
        "sch_layouts_observed": [
            {
                "file_version": row.file_version,
                "payload_offset": row.payload_offset,
                "step_size": row.step_size,
                "dominant": row.dominant,
            }
            for row in (equip.layouts_observed if equip else ())
        ],
        "sch_count": total,
        "parse_errors": parse_errors,
        "unknown_pct": pct(categories.get("unknown", 0), total),
        "categories_top": dict(categories.most_common(15)),
        "category_share": {
            k: pct(v, total) for k, v in categories.most_common(10) if k != "unknown"
        },
        "versions": dict(versions.most_common()),
        "step_sizes": dict(step_sizes.most_common()),
        "payload_offsets": dict(payload_offsets.most_common()),
        "top_layouts": layout_sigs.most_common(8),
        "top_step_counts": step_counts.most_common(8),
        "loop_goto": dict(loop_goto),
        "loop_both_pct": pct(
            loop_goto.get("both", 0),
            sum(loop_goto.values()) or 1,
        ),
        "current_mA": {
            "median": round(median(currents_sorted), 3) if currents_sorted else None,
            "p90": round(currents_sorted[int(len(currents_sorted) * 0.9)], 3)
            if currents_sorted
            else None,
            "max": round(max(currents_sorted), 3) if currents_sorted else None,
            "top_modes": Counter(round(c, 3) for c in charge_currents).most_common(8),
        },
        "cv_cutoff_ratio_modes": cv_mode,
        "cap_mode_496": dict(cap_modes.most_common(4)),
        "safety_header_top": [
            {"maxV_mV": t[0], "minV_mV": t[1], "maxI_mA": t[2], "minI_mA": t[3], "count": c}
            for t, c in safety_tuples.most_common(5)
        ],
        "distinct_protocols": len(classified_cats),
    }


def _pairwise_category_diff(units: dict[str, dict]) -> list[dict]:
    """Categories where unit mix diverges most from corpus average."""
    all_cats: Counter = Counter()
    for u in units.values():
        if "error" in u:
            continue
        all_cats.update(u.get("categories_top", {}))

    corpus_total = sum(all_cats.values())
    corpus_share = {k: all_cats[k] / corpus_total for k in all_cats}

    rows = []
    for unit, data in units.items():
        if "error" in data:
            continue
        n = data["sch_count"]
        for cat, count in data.get("categories_top", {}).items():
            if cat == "unknown":
                continue
            unit_share = count / n if n else 0
            corpus = corpus_share.get(cat, 0)
            delta_pp = round(100 * (unit_share - corpus), 1)
            if abs(delta_pp) >= 2.0:
                rows.append(
                    {
                        "unit": unit,
                        "category": cat,
                        "unit_share_pct": round(100 * unit_share, 1),
                        "corpus_share_pct": round(100 * corpus, 1),
                        "delta_pp": delta_pp,
                    }
                )
    return sorted(rows, key=lambda r: -abs(r["delta_pp"]))[:30]


def _unique_traits(units: dict[str, dict]) -> dict[str, list[str]]:
    traits: dict[str, list[str]] = defaultdict(list)
    valid = {k: v for k, v in units.items() if "error" not in v}

    # step size 696 only on some units
    for unit, data in valid.items():
        sizes = data.get("step_sizes", {})
        if sizes.get(696) or sizes.get("696"):
            n = sizes.get(696) or sizes.get("696")
            traits[unit].append(f"696B step records: {n} files")
        elif any((d.get("step_sizes", {}).get(696) or d.get("step_sizes", {}).get("696")) for d in valid.values()):
            traits[unit].append("696B step records: none")

    # version 0x10004
    for unit, data in valid.items():
        if data.get("versions", {}).get("0x00010004"):
            n = data["versions"]["0x00010004"]
            traits[unit].append(f"0x10004 (696 formation): {n} files")

    # safety
    for unit, data in valid.items():
        safety = data.get("safety_header_top", [])
        if safety:
            s = safety[0]
            traits[unit].append(
                f"safety header populated: maxI={s['maxI_mA']} mA ({s['count']} files)"
            )
        else:
            traits[unit].append("safety header @0x3D8: mostly empty")

    # current scale
    medians = {
        u: d["current_mA"]["median"] for u, d in valid.items() if d["current_mA"]["median"]
    }
    if medians:
        overall_med = median(medians.values())
        for unit, med in medians.items():
            if med > overall_med * 3:
                traits[unit].append(f"high typical current (median {med} mA vs corpus {overall_med:.1f})")
            elif med < overall_med / 3:
                traits[unit].append(f"low typical current (median {med} mA vs corpus {overall_med:.1f})")

    return dict(traits)


def build_comparison(zip_map: dict[str, Path] | None = None) -> dict:
    zip_map = zip_map or DEFAULT_ZIPS
    units = {unit: _scan_unit(unit, path) for unit, path in sorted(zip_map.items())}
    valid = [u for u in units.values() if "error" not in u]

    shared = {
        "dominant_version": "0x00010003",
        "dominant_step_size": 612,
        "dominant_payload_v3": 1760,
        "dominant_payload_v2": 1632,
        "loop_primary_offset": "+564",
        "current_unit_in_sch": "mA",
        "cv_cutoff_ratio_mode": 0.5,
    }

    return {
        "schema": "pne_scheduler.pne_unit_comparison/v1",
        "units": units,
        "shared_across_units": shared,
        "category_divergence": _pairwise_category_diff(units),
        "unit_unique_traits": _unique_traits(units),
        "summary_table": [
            {
                "unit": u["unit"],
                "files": u["sch_count"],
                "unknown_pct": u["unknown_pct"],
                "protocols": u["distinct_protocols"],
                "median_mA": u["current_mA"]["median"],
                "max_mA": u["current_mA"]["max"],
                "step_696": u["step_sizes"].get(696, u["step_sizes"].get("696", 0)),
                "loop_both_pct": u["loop_both_pct"],
                "top_layout": u["top_layouts"][0][0] if u["top_layouts"] else None,
            }
            for u in valid
        ],
    }


def _render_markdown(report: dict) -> str:
    lines = [
        "## Cross-unit comparison",
        "",
        "Diff from lab zip corpora (`PNE01` … `PNE09`, `PNE22`).",
        "",
        "| Unit | Files | Unknown | Protocols | Median I (mA) | Max I (mA) | 696B | LOOP both% | Top layout |",
        "|------|------:|--------:|----------:|--------------:|-----------:|-----:|-----------:|------------|",
    ]
    for row in report["summary_table"]:
        lines.append(
            f"| {row['unit']} | {row['files']} | {row['unknown_pct']}% | {row['protocols']} | "
            f"{row['median_mA']} | {row['max_mA']} | {row['step_696']} | {row['loop_both_pct']}% | "
            f"`{row['top_layout']}` |"
        )

    lines.extend(
        [
            "",
            "### What is the same (all units)",
            "",
        ]
    )
    for k, v in report["shared_across_units"].items():
        lines.append(f"- **{k}**: `{v}`")

    lines.extend(["", "### Per-unit unique traits", ""])
    for unit, traits in report["unit_unique_traits"].items():
        lines.append(f"#### {unit}")
        lines.append("")
        for t in traits:
            lines.append(f"- {t}")
        data = report["units"][unit]
        if "error" not in data:
            lines.append("")
            lines.append("**Top categories**")
            for cat, n in list(data["categories_top"].items())[:8]:
                share = data["category_share"].get(cat)
                suffix = f" ({share}%)" if share is not None else ""
                lines.append(f"- `{cat}`: {n}{suffix}")
            lines.append("")
            lines.append("**Top step counts**")
            for st, n in data["top_step_counts"][:5]:
                lines.append(f"- {st} steps: {n} files")
            lines.append("")
            lines.append("**Current modes (mA)**")
            for val, n in data["current_mA"]["top_modes"][:5]:
                lines.append(f"- {val} mA: {n} steps")
            lines.append("")

    lines.extend(["", "### Category mix divergence (vs corpus average)", ""])
    lines.append("| Unit | Category | Unit% | Corpus% | Δ pp |")
    lines.append("|------|----------|------:|--------:|-----:|")
    for row in report["category_divergence"][:20]:
        sign = "+" if row["delta_pp"] > 0 else ""
        lines.append(
            f"| {row['unit']} | `{row['category']}` | {row['unit_share_pct']}% | "
            f"{row['corpus_share_pct']}% | {sign}{row['delta_pp']} |"
        )

    lines.extend(
        [
            "",
            "### Interpretation notes",
            "",
            "- **Unknown filenames** are mostly project/material names; low unknown% (PNE01) means clearer naming, not better binary.",
            "- **Max I (mA)** in a zip reflects stored schedule values (cell size × C-rate), not always equipment rating.",
            "- **696B / 0x10004** is a file-format generation, not tied to one cycler — but only PNE02/PNE03 have any in this corpus.",
            "- **LOOP both%** = nested loop steps with both +48 and +564 populated; higher on complex HPPC/RPT schedules.",
            "",
        ]
    )
    return "\n".join(lines)


def render_lab_corpus_report(corpus_report: dict, comparison_report: dict) -> str:
    from pne_scheduler.tools.analyze_pne_unit_corpus import render_corpus_markdown

    header = [
        "# Lab corpus report (PNE unit zips)",
        "",
        "Machine-readable: [`PNE_UNIT_CORPUS.json`](PNE_UNIT_CORPUS.json), "
        "[`PNE_UNIT_COMPARISON.json`](PNE_UNIT_COMPARISON.json)",
        "",
        "Regenerate:",
        "",
        "```powershell",
        "python tools/analyze_pne_unit_corpus.py",
        "python tools/compare_pne_units.py",
        "```",
        "",
        "---",
        "",
    ]
    return "\n".join(header) + render_corpus_markdown(corpus_report) + "\n\n---\n\n" + _render_markdown(
        comparison_report
    )


def main() -> None:
    from pne_scheduler.tools.analyze_pne_unit_corpus import build_report as build_corpus_report

    corpus_report = build_corpus_report()
    comparison_report = build_comparison()
    out_corpus_json = ROOT / "planning" / "PNE_UNIT_CORPUS.json"
    out_json = ROOT / "planning" / "PNE_UNIT_COMPARISON.json"
    out_md = ROOT / "planning" / "LAB_CORPUS_REPORT.md"
    out_corpus_json.write_text(json.dumps(corpus_report, ensure_ascii=False, indent=2), encoding="utf-8")
    out_json.write_text(json.dumps(comparison_report, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_lab_corpus_report(corpus_report, comparison_report), encoding="utf-8")
    print(f"Wrote {out_corpus_json}")
    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")
    for row in comparison_report["summary_table"]:
        print(row["unit"], row["files"], "files", "median", row["median_mA"], "mA")


if __name__ == "__main__":
    main()
