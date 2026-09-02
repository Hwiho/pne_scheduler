"""Compare 612-byte vs 696-byte step record layouts from fixture corpus (Gate B1)."""

from __future__ import annotations

import json
import struct
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pne_scheduler.io.sch_binary import read_sch_binary
from pne_scheduler.schema.fields import get_step_fields

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "example" / "fixtures" / "catalog.json"
FIXTURE_ROOT = ROOT / "example" / "fixtures"


@dataclass(frozen=True, slots=True)
class ExtensionByteStats:
    offset: int
    nonzero_count: int
    sample_count: int
    sample_float_values: tuple[float, ...]


def _extension_byte_stats(records: list[bytes]) -> list[ExtensionByteStats]:
    if not records:
        return []
    extension_len = len(records[0]) - 612
    if extension_len <= 0:
        return []
    stats: list[ExtensionByteStats] = []
    for rel_offset in range(extension_len):
        absolute = 612 + rel_offset
        nonzero = 0
        float_samples: list[float] = []
        for record in records:
            if len(record) <= absolute:
                continue
            value = record[absolute]
            if value != 0:
                nonzero += 1
            if rel_offset % 4 == 0 and rel_offset + 4 <= extension_len:
                word_offset = 612 + rel_offset
                if word_offset + 4 <= len(record):
                    float_samples.append(
                        struct.unpack_from("<f", record, word_offset)[0]
                    )
        stats.append(
            ExtensionByteStats(
                offset=absolute,
                nonzero_count=nonzero,
                sample_count=len(records),
                sample_float_values=tuple(sorted(set(round(v, 6) for v in float_samples[:8]))),
            )
        )
    return stats


def _prefix_field_mismatch_stats(
    records_612: list[bytes],
    records_696: list[bytes],
) -> list[dict[str, Any]]:
    """Heuristic: compare float32 words in shared prefix where both corpora have data."""
    mismatches: list[dict[str, Any]] = []
    fields_612 = {field.offset: field for field in get_step_fields(0x00010003)}
    for offset, field in sorted(fields_612.items()):
        values_612: set[float] = set()
        values_696: set[float] = set()
        for record in records_612:
            if offset + 4 <= len(record):
                values_612.add(round(struct.unpack_from("<f", record, offset)[0], 6))
        for record in records_696:
            if offset + 4 <= len(record):
                values_696.add(round(struct.unpack_from("<f", record, offset)[0], 6))
        if not values_612 or not values_696:
            continue
        overlap = values_612 & values_696
        if not overlap and len(values_612) > 3 and len(values_696) > 3:
            mismatches.append(
                {
                    "offset": offset,
                    "field": field.name,
                    "distinct_values_612": len(values_612),
                    "distinct_values_696": len(values_696),
                    "note": "No overlapping float32 values between corpora at this offset",
                }
            )
    return mismatches


def _collect_step_records(
    fixture_paths: list[Path],
    *,
    step_size: int,
    max_records: int = 200,
) -> list[bytes]:
    records: list[bytes] = []
    for path in fixture_paths:
        data = path.read_bytes()
        doc = read_sch_binary(path)
        if doc.step_size != step_size:
            continue
        for index, _step in enumerate(doc.steps):
            if len(records) >= max_records:
                return records
            base = doc.payload_offset + index * doc.step_size
            records.append(data[base : base + doc.step_size])
    return records


def build_step_layout_diff_report(
    *,
    catalog_path: Path = CATALOG_PATH,
    fixture_root: Path = FIXTURE_ROOT,
    max_records_per_size: int = 200,
) -> dict[str, Any]:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    paths_612: list[Path] = []
    paths_696: list[Path] = []
    for item in catalog["fixtures"]:
        path = fixture_root / Path(item["path"])
        if not path.exists():
            continue
        if item["layout"]["step_size"] == 612:
            paths_612.append(path)
        elif item["layout"]["step_size"] == 696:
            paths_696.append(path)

    records_612 = _collect_step_records(paths_612, step_size=612, max_records=max_records_per_size)
    records_696 = _collect_step_records(paths_696, step_size=696, max_records=max_records_per_size)

    extension_stats = _extension_byte_stats(records_696)
    hot_extension_offsets = [
        {
            "offset": item.offset,
            "nonzero_ratio": round(item.nonzero_count / item.sample_count, 4),
            "sample_float_values": list(item.sample_float_values),
        }
        for item in extension_stats
        if item.nonzero_count > 0
    ]
    hot_extension_offsets.sort(key=lambda row: row["nonzero_ratio"], reverse=True)

    tail_word_histogram = Counter()
    for record in records_696:
        for rel in range(612, len(record), 4):
            if rel + 4 <= len(record):
                tail_word_histogram[rel] += 1 if any(record[rel : rel + 4]) else 0

    return {
        "schema": "pne_scheduler.step_layout_diff/v1",
        "catalog_fixture_count": catalog["fixture_count"],
        "sampled_step_records": {
            "612": len(records_612),
            "696": len(records_696),
        },
        "shared_prefix_bytes": 612,
        "extension_bytes": 84,
        "extension_nonzero_hotspots": hot_extension_offsets[:40],
        "prefix_float_value_divergence": _prefix_field_mismatch_stats(records_612, records_696),
        "interpretation": [
            "696-byte records are NOT a simple 84-byte append to 612-byte records.",
            "Late-field offsets in 0x00010003 corpus differ from ASSB legacy table (+8/+16 shifts).",
            "Semantic field names for bytes 612-695 require controlled pairs or Excel+fixture correlation.",
        ],
        "next_actions": [
            "Map hot extension offsets against sch_file_structure_20250211.xlsx 0x00010004 sheet.",
            "Collect controlled pairs on a 696-byte PNE16 template.",
        ],
    }


def render_step_layout_diff_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 612 vs 696 step layout diff (auto-generated)",
        "",
        f"- Catalog fixtures: **{report['catalog_fixture_count']}**",
        f"- Sampled 612-byte step records: **{report['sampled_step_records']['612']}**",
        f"- Sampled 696-byte step records: **{report['sampled_step_records']['696']}**",
        "",
        "## Interpretation",
        "",
    ]
    for item in report["interpretation"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Extension nonzero hotspots (696-byte tail)", ""])
    if not report["extension_nonzero_hotspots"]:
        lines.append("_No nonzero extension bytes in sample._")
    else:
        lines.append("| Offset | Nonzero ratio | Sample float values |")
        lines.append("|--------|---------------|---------------------|")
        for row in report["extension_nonzero_hotspots"][:25]:
            samples = ", ".join(str(v) for v in row["sample_float_values"][:5])
            lines.append(
                f"| {row['offset']} | {row['nonzero_ratio']:.2%} | {samples} |"
            )
    lines.extend(["", "## Prefix float divergence heuristic", ""])
    divergences = report["prefix_float_value_divergence"]
    if not divergences:
        lines.append("_No prefix divergence flagged in sample._")
    else:
        for row in divergences[:20]:
            lines.append(
                f"- offset **{row['offset']}** (`{row['field']}`): "
                f"{row['note']}"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Compare 612 vs 696 SCH step layouts")
    parser.add_argument("-o", "--output", type=Path, help="JSON report path")
    parser.add_argument("--markdown", type=Path, help="Optional markdown summary path")
    args = parser.parse_args(argv)

    report = build_step_layout_diff_report()
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(rendered, end="")
    if args.markdown:
        args.markdown.write_text(render_step_layout_diff_markdown(report), encoding="utf-8")
        print(f"Wrote {args.markdown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
