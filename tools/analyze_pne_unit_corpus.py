"""Per-PNE-unit corpus analysis from lab zip archives (PNE01, PNE02, ...)."""

from __future__ import annotations

import json
import struct
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from pne_scheduler.classify import ScheduleCategory, classify_schedule
from pne_scheduler.io.layout import detect_sch_layout
from pne_scheduler.schema.corpus_paths import default_corpus_zip_map
from pne_scheduler.schema.equipment import rating_hint_for_unit
from pne_scheduler.schema.lab_corpus import validate_unit_corpus_zip
from pne_scheduler.schema.ensol_v612 import (
    OFF_CURRENT_MA,
    OFF_CV_CUTOFF_MA,
    OFF_LOOP_COUNT,
    OFF_LOOP_GOTO_ENSOL,
    OFF_LOOP_GOTO_LEGACY,
    OFF_STEP_TYPE,
    OFF_TIME_OR_REST_S,
    OFF_VOLT_OR_VLIM_MV,
    OFF_VOLTAGE_CUTOFF_MV,
)
from pne_scheduler.schema.enums import (
    SCH_STEP_TYPE_CC_CHARGE,
    SCH_STEP_TYPE_CC_DISCHARGE,
    SCH_STEP_TYPE_CCCV,
    SCH_STEP_TYPE_END,
    SCH_STEP_TYPE_LOOP,
)

DEFAULT_ZIPS: dict[str, Path] = default_corpus_zip_map()

TYPE_MAP = {
    int(SCH_STEP_TYPE_CCCV): "CCCV",
    int(SCH_STEP_TYPE_CC_CHARGE): "CC_CHG",
    int(SCH_STEP_TYPE_CC_DISCHARGE): "CC_DCHG",
    int(SCH_STEP_TYPE_LOOP): "LOOP",
    int(SCH_STEP_TYPE_END): "END",
}


def _read_f32(record: bytes, offset: int) -> float:
    return struct.unpack_from("<f", record, offset)[0]


def _read_u32(record: bytes, offset: int) -> int:
    return struct.unpack_from("<I", record, offset)[0]


def _read_i32(record: bytes, offset: int) -> int:
    return struct.unpack_from("<i", record, offset)[0]


def analyze_binary(data: bytes) -> dict | None:
    layout = detect_sch_layout(data)
    if layout is None:
        return None
    payload, step_size = layout.payload_offset, layout.step_size
    version = struct.unpack_from("<I", data, 4)[0] if len(data) >= 8 else None
    steps: list[tuple[int, int, bytes]] = []
    index = 0
    while payload + index * step_size + 12 <= len(data):
        record = data[payload + index * step_size : payload + (index + 1) * step_size]
        step_no = _read_i32(record, 0)
        type_code = _read_i32(record, OFF_STEP_TYPE) & 0xFFFF
        if step_no <= 0:
            break
        steps.append((step_no, type_code, record))
        if type_code == int(SCH_STEP_TYPE_END):
            break
        index += 1

    loop_stats = {"only_48": 0, "only_564": 0, "both": 0, "neither": 0}
    currents: list[float] = []
    max_current = 0.0
    for step_no, type_code, record in steps:
        if type_code == int(SCH_STEP_TYPE_LOOP):
            g48 = _read_u32(record, OFF_LOOP_GOTO_LEGACY)
            g564 = _read_u32(record, OFF_LOOP_GOTO_ENSOL) if len(record) > OFF_LOOP_GOTO_ENSOL + 4 else 0
            if g48 and g564:
                loop_stats["both"] += 1
            elif g48:
                loop_stats["only_48"] += 1
            elif g564:
                loop_stats["only_564"] += 1
            else:
                loop_stats["neither"] += 1
        if type_code in (0x0101, 0x0201, 0x0202):
            i_ma = _read_f32(record, OFF_CURRENT_MA)
            if i_ma > 0:
                currents.append(i_ma)
                max_current = max(max_current, i_ma)

    return {
        "version": f"0x{version:08x}" if version is not None else None,
        "payload_offset": payload,
        "step_size": step_size,
        "file_bytes": len(data),
        "step_count": len(steps),
        "loop_steps": sum(1 for _, tc, _ in steps if tc == int(SCH_STEP_TYPE_LOOP)),
        "loop_goto": loop_stats,
        "current_mA_max": round(max_current, 4) if max_current else None,
        "current_mA_p50": round(sorted(currents)[len(currents) // 2], 4) if currents else None,
    }


def scan_unit(unit: str, zip_path: Path, sample_per_category: int = 2) -> dict:
    zip_error = validate_unit_corpus_zip(unit, zip_path)
    if zip_error:
        return {"unit": unit, "zip": str(zip_path), "error": zip_error}

    if not zip_path.is_file():
        return {"unit": unit, "zip": str(zip_path), "error": "missing"}

    categories: Counter = Counter()
    layouts: Counter = Counter()
    versions: Counter = Counter()
    step_sizes: Counter = Counter()
    loop_goto_total = {"only_48": 0, "only_564": 0, "both": 0, "neither": 0}
    max_current_seen = 0.0
    currents_over: Counter = Counter()
    samples: dict[str, list] = defaultdict(list)
    parse_errors = 0
    files_with_loop = 0

    with zipfile.ZipFile(zip_path) as zf:
        sch_names = sorted(n for n in zf.namelist() if n.lower().endswith(".sch"))
        for name in sch_names:
            try:
                data = zf.read(name)
                match = classify_schedule(name, data)
                cat = match.category.value
                categories[cat] += 1
                info = analyze_binary(data)
                if info is None:
                    parse_errors += 1
                    continue
                if info["version"]:
                    versions[info["version"]] += 1
                step_sizes[info["step_size"]] += 1
                layouts[f"{info['version']}/{info['step_size']}B/{info['step_count']}st"] += 1
                if info["loop_steps"]:
                    files_with_loop += 1
                    for key, val in info["loop_goto"].items():
                        loop_goto_total[key] += val
                if info["current_mA_max"] is not None:
                    max_current_seen = max(max_current_seen, info["current_mA_max"])
                    if info["current_mA_max"] > 500:
                        currents_over[">500mA"] += 1
                    if info["current_mA_max"] > 6000:
                        currents_over[">6A"] += 1
                if len(samples[cat]) < sample_per_category:
                    samples[cat].append(
                        {
                            "file": PurePosixPath(name).name,
                            "classify_rule": match.matched_rule,
                            "binary": info,
                        }
                    )
            except Exception:
                parse_errors += 1

    total = len(sch_names)
    unknown = categories.get("unknown", 0)
    return {
        "unit": unit,
        "zip": zip_path.name,
        "zip_bytes": zip_path.stat().st_size,
        "sch_count": total,
        "unknown_count": unknown,
        "unknown_pct": round(100 * unknown / total, 1) if total else 0,
        "classified_pct": round(100 * (total - unknown) / total, 1) if total else 0,
        "parse_errors": parse_errors,
        "files_with_loop": files_with_loop,
        "loop_goto_aggregate": loop_goto_total,
        "max_current_mA_seen": round(max_current_seen, 4) if max_current_seen else None,
        "categories": dict(categories.most_common()),
        "versions": dict(versions.most_common()),
        "step_sizes": dict(step_sizes.most_common()),
        "top_layouts": layouts.most_common(12),
        "current_threshold_hits": dict(currents_over),
        "samples_by_category": dict(samples),
    }


def _rating_label(hint: dict) -> str:
    if hint.get("official_rating"):
        return str(hint["official_rating"])
    return str(hint.get("inferred_from_corpus") or "unlisted")


def infer_rating_hint(unit_report: dict) -> dict:
    max_current = unit_report.get("max_current_mA_seen")
    return rating_hint_for_unit(unit_report.get("unit", ""), max_current)


def build_report(zip_map: dict[str, Path] | None = None) -> dict:
    zip_map = zip_map or DEFAULT_ZIPS
    units = {}
    for unit, path in sorted(zip_map.items()):
        report = scan_unit(unit, path)
        if "error" not in report:
            report["rating_hint"] = infer_rating_hint(report)
        units[unit] = report

    return {
        "schema": "pne_scheduler.pne_unit_corpus/v1",
        "source": "Lab zip archives named PNE##.zip only (see planning/LAB_DATA_POLICY.md)",
        "policy_ref": "planning/LAB_DATA_POLICY.md",
        "units": units,
        "cross_unit_summary": _cross_unit_summary(units),
    }


def _cross_unit_summary(units: dict[str, dict]) -> dict:
    total_sch = sum(u.get("sch_count", 0) for u in units.values() if "error" not in u)
    total_unknown = sum(u.get("unknown_count", 0) for u in units.values() if "error" not in u)
    all_categories: Counter = Counter()
    all_versions: Counter = Counter()
    for u in units.values():
        if "error" in u:
            continue
        all_categories.update(u.get("categories", {}))
        all_versions.update(u.get("versions", {}))
    return {
        "unit_count": len([u for u in units.values() if "error" not in u]),
        "total_sch": total_sch,
        "total_unknown": total_unknown,
        "unknown_pct": round(100 * total_unknown / total_sch, 1) if total_sch else 0,
        "categories_all_units": dict(all_categories.most_common(20)),
        "versions_all_units": dict(all_versions.most_common()),
    }


def render_corpus_markdown(report: dict) -> str:
    """Render corpus scan report as markdown (section for LAB_CORPUS_REPORT.md)."""
    lines = [
        "## Corpus scan (per zip)",
        "",
        "Source zips: `example/corpus_zips/PNE##.zip` (or `c:\\PNE##.zip` on lab PC).",
        "",
        f"- Units: {report['cross_unit_summary']['unit_count']}",
        f"- Total `.sch`: {report['cross_unit_summary']['total_sch']}",
        f"- Unknown (no protocol keyword): {report['cross_unit_summary']['total_unknown']} "
        f"({report['cross_unit_summary']['unknown_pct']}%)",
        "",
        "| Unit | Files | Classified | Unknown | LOOP files | Step sizes | Rating hint |",
        "|------|------:|-----------:|--------:|-----------:|------------|-------------|",
    ]
    for unit, data in report["units"].items():
        if "error" in data:
            lines.append(f"| {unit} | — | — | — | — | — | missing zip |")
            continue
        step_sizes = ", ".join(f"{k}×{v}" for k, v in data.get("step_sizes", {}).items())
        hint = _rating_label(data.get("rating_hint", {}))
        lines.append(
            f"| {unit} | {data['sch_count']} | {data['classified_pct']}% | "
            f"{data['unknown_pct']}% | {data['files_with_loop']} | {step_sizes} | {hint} |"
        )

    lines.extend(["", "### Per-unit detail", ""])
    for unit, data in report["units"].items():
        if "error" in data:
            continue
        lines.append(f"#### {unit} ({data['sch_count']} files)")
        lines.append("")
        loop_agg = data.get("loop_goto_aggregate", {})
        lines.append(
            f"- LOOP goto aggregate: +564 only={loop_agg.get('only_564', 0)}, "
            f"+48 only={loop_agg.get('only_48', 0)}, both={loop_agg.get('both', 0)}, "
            f"neither={loop_agg.get('neither', 0)}"
        )
        hint = data.get("rating_hint", {})
        official = hint.get("official_rating") or "unlisted"
        exceed = hint.get("corpus_exceeds_official")
        exceed_note = " (corpus max exceeds official)" if exceed else ""
        lines.append(
            f"- Official rating: **{official}** | max in corpus: {data.get('max_current_mA_seen')} mA{exceed_note}"
        )
        lines.append("")
        for cat, count in sorted(data["categories"].items(), key=lambda x: -x[1])[:12]:
            lines.append(f"- `{cat}`: {count}")
        lines.append("")
        lines.append(f"- Versions: `{data.get('versions', {})}`")
        lines.append(f"- Step sizes: `{data.get('step_sizes', {})}`")
        lines.append(f"- Top layouts: `{data.get('top_layouts', [])[:5]}`")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    report = build_report()
    out_json = ROOT / "planning" / "PNE_UNIT_CORPUS.json"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_json}")
    for unit, data in report["units"].items():
        if "error" in data:
            print(unit, "MISSING")
        else:
            print(
                unit,
                data["sch_count"],
                "sch",
                "unknown",
                data["unknown_pct"],
                "%",
                "rating",
                _rating_label(data["rating_hint"]),
            )


if __name__ == "__main__":
    main()
