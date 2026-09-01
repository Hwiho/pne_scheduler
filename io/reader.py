"""Read .sch files using the in-tree vendored ASSB SCH parser."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..vendor.assb_sch import parse_sch_cycle_map_bytes


@dataclass(frozen=True)
class SchCycleMapView:
    source_path: Path
    payload_offset: int
    step_size: int
    step_count: int
    header_version: int | None
    steps: list[dict[str, Any]]


def read_sch(path: Path) -> SchCycleMapView:
    """Parse a .sch file with the vendored ASSB-compatible parser."""
    data = path.read_bytes()
    cycle_map = parse_sch_cycle_map_bytes(data, source_path=path)
    if cycle_map is None:
        raise ValueError(f"Could not parse SCH layout: {path}")

    steps = []
    for candidate in cycle_map.sch_condition_candidates:
        steps.append(
            {
                "step_no": candidate.get("StepNo"),
                "step_type_code": candidate.get("StepTypeCode"),
                "fields": candidate.get("raw_fields", {}),
            }
        )

    return SchCycleMapView(
        source_path=path,
        payload_offset=cycle_map.payload_offset,
        step_size=cycle_map.step_size,
        step_count=cycle_map.step_count,
        header_version=cycle_map.header_version,
        steps=steps,
    )
