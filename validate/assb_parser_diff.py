"""Compare vendored ASSB parser output with the native pne_scheduler reader."""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pne_scheduler.io.sch_parser import parse_schedule_file
from pne_scheduler.schema.fields import get_step_fields
from pne_scheduler.vendor.assb_sch import (
    DOCUMENTED_DIVERGENCES,
    SHARED_OFFSET_PAIRS,
    assb_offset_table,
    parse_sch_cycle_map_bytes,
    pne_scheduler_offset_table,
)

NATIVE_FIELD_TO_OFFSET = {
    "f_vref": 16,
    "f_iref": 20,
    "f_end_v": 28,
    "f_end_i": 32,
    "f_end_c": 36,
}


@dataclass(frozen=True, slots=True)
class FixtureParserDiff:
    path: str
    layout_match: bool
    step_count_match: bool
    assb_step_count: int | None
    native_step_count: int
    field_value_mismatches: tuple[dict[str, Any], ...]


def offset_parity_summary() -> dict[str, Any]:
    return {
        "schema": "pne_scheduler.assb_offset_parity/v1",
        "shared_pairs": [
            {
                "assb_name": pair.assb_name,
                "assb_offset": pair.assb_offset,
                "pne_name": pair.pne_name,
                "pne_offset": pair.pne_offset,
            }
            for pair in SHARED_OFFSET_PAIRS
        ],
        "documented_divergences": [
            {
                "assb_name": item.assb_name,
                "assb_offset": item.assb_offset,
                "pne_name": item.pne_name,
                "pne_offset": item.pne_offset,
                "reason": item.reason,
            }
            for item in DOCUMENTED_DIVERGENCES
        ],
        "assb_offset_table": assb_offset_table(),
        "pne_scheduler_offset_table": pne_scheduler_offset_table(),
    }


def compare_fixture_parsers(path: str | Path) -> FixtureParserDiff:
    resolved = Path(path)
    data = resolved.read_bytes()
    assb_map = parse_sch_cycle_map_bytes(data, source_path=resolved)
    native_doc = parse_schedule_file(resolved)

    mismatches: list[dict[str, Any]] = []
    if assb_map is not None:
        for assb_step, native_step in zip(assb_map.current_steps, native_doc.steps):
            for assb_field, (dtype, assb_offset) in _assb_fields_for_layout(
                assb_map.header_version,
                assb_map.step_size,
            ).items():
                pne_field = _assb_to_native_name(assb_field)
                if pne_field is None:
                    continue
                native_offset = NATIVE_FIELD_TO_OFFSET.get(pne_field)
                if native_offset is None:
                    continue
                assb_value = assb_step.condition_candidates.get(assb_field)
                native_value = getattr(native_step, pne_field)
                if not _values_close(assb_value, native_value, dtype=dtype):
                    mismatches.append(
                        {
                            "step_no": assb_step.step_no,
                            "field": assb_field,
                            "native_field": pne_field,
                            "assb_offset": assb_offset,
                            "native_offset": native_offset,
                            "assb_value": assb_value,
                            "native_value": native_value,
                        }
                    )

    return FixtureParserDiff(
        path=str(resolved),
        layout_match=(
            assb_map is not None
            and assb_map.payload_offset == native_doc.payload_offset
            and assb_map.step_size == native_doc.step_size
        ),
        step_count_match=(
            assb_map is not None and assb_map.step_count == len(native_doc.steps)
        ),
        assb_step_count=assb_map.step_count if assb_map is not None else None,
        native_step_count=len(native_doc.steps),
        field_value_mismatches=tuple(mismatches),
    )


def build_assb_parser_diff_report(
    fixture_paths: list[Path],
) -> dict[str, Any]:
    fixture_results = []
    for path in fixture_paths:
        diff = compare_fixture_parsers(path)
        fixture_results.append(
            {
                "path": str(path.relative_to(path.parents[2]))
                if len(path.parents) > 2
                else str(path),
                "layout_match": diff.layout_match,
                "step_count_match": diff.step_count_match,
                "assb_step_count": diff.assb_step_count,
                "native_step_count": diff.native_step_count,
                "field_value_mismatch_count": len(diff.field_value_mismatches),
                "field_value_mismatches": list(diff.field_value_mismatches[:10]),
            }
        )

    return {
        "schema": "pne_scheduler.assb_parser_diff/v1",
        "offset_parity": offset_parity_summary(),
        "fixtures": fixture_results,
        "summary": {
            "fixture_count": len(fixture_results),
            "layout_match_count": sum(1 for row in fixture_results if row["layout_match"]),
            "step_count_match_count": sum(
                1 for row in fixture_results if row["step_count_match"]
            ),
            "fixtures_with_field_mismatches": sum(
                1 for row in fixture_results if row["field_value_mismatch_count"] > 0
            ),
        },
    }


def render_assb_parser_diff_markdown(report: dict[str, Any]) -> str:
    parity = report["offset_parity"]
    lines = [
        "# ASSB vs internal parser divergence",
        "",
        "Auto-generated report for Gate B. ASSB vendored constants live in "
        "`vendor/assb_sch/`. Internal reader uses `schema/fields.py`.",
        "",
        "## Shared offset pairs (must match)",
        "",
        "| ASSB name | ASSB offset | PNE name | PNE offset |",
        "|-----------|-------------|----------|------------|",
    ]
    for row in parity["shared_pairs"]:
        lines.append(
            f"| {row['assb_name']} | {row['assb_offset']} | "
            f"{row['pne_name']} | {row['pne_offset']} |"
        )
    lines.extend(["", "## Documented divergences", ""])
    for row in parity["documented_divergences"]:
        lines.append(
            f"- **{row['assb_name']}** @ {row['assb_offset']} vs "
            f"**{row['pne_name']}** @ {row['pne_offset']}: {row['reason']}"
        )
    summary = report["summary"]
    lines.extend(
        [
            "",
            "## Fixture comparison summary",
            "",
            f"- Fixtures checked: **{summary['fixture_count']}**",
            f"- Layout matches: **{summary['layout_match_count']}**",
            f"- Step-count matches: **{summary['step_count_match_count']}**",
            f"- Fixtures with ASSB/native field mismatches: "
            f"**{summary['fixtures_with_field_mismatches']}**",
            "",
            "## Per-fixture notes",
            "",
        ]
    )
    for row in report["fixtures"]:
        rel = row["path"]
        lines.append(
            f"- `{rel}`: layout={row['layout_match']}, steps={row['step_count_match']}, "
            f"field_mismatches={row['field_value_mismatch_count']}"
        )
    return "\n".join(lines) + "\n"


def _assb_fields_for_layout(version: int | None, step_size: int) -> dict[str, tuple[str, int]]:
    from pne_scheduler.vendor.assb_sch.constants import (
        SCH_CONDITION_CANDIDATE_FIELDS_BY_LAYOUT,
    )

    if version is None:
        return {}
    return dict(SCH_CONDITION_CANDIDATE_FIELDS_BY_LAYOUT.get((version, step_size), {}))


def _assb_to_native_name(assb_field: str) -> str | None:
    mapping = {
        "fEndC": "f_end_c",
        "nGotoStepID": None,
        "fSocRate": None,
        "fMaxCapacity": None,
        "bUseActualCapa": None,
        "bUseDataStepNo": None,
        "nLoopInfoEndSocGoto": None,
    }
    return mapping.get(assb_field)


def _values_close(assb_value: Any, native_value: Any, *, dtype: str) -> bool:
    if assb_value is None and native_value in (0, 0.0):
        return True
    if native_value is None and assb_value in (0, 0.0):
        return True
    if dtype == "uint8":
        return assb_value == native_value
    if isinstance(assb_value, (int, float)) and isinstance(native_value, (int, float)):
        return abs(float(assb_value) - float(native_value)) <= 1e-3
    return assb_value == native_value
