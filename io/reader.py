"""Read .sch files using available PNE converter backends."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SchCycleMapView:
    source_path: Path
    payload_offset: int
    step_size: int
    step_count: int
    header_version: int | None
    steps: list[dict[str, Any]]


def read_sch(path: Path) -> SchCycleMapView:
    """Parse a .sch file. Prefers ASSB parser, falls back to Ensol vendor parser."""
    data = path.read_bytes()
    parser = _resolve_parser()
    cycle_map = parser(data, source_path=path)
    if cycle_map is None:
        raise ValueError(f"Could not parse SCH layout: {path}")

    header_version = getattr(cycle_map, "header_version", None)
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
        header_version=header_version,
        steps=steps,
    )


def _resolve_parser():
    try:
        from assb_analyzer.io.pne_converter import parse_sch_cycle_map_bytes

        return parse_sch_cycle_map_bytes
    except ImportError:
        pass

    vendor_root = Path(__file__).resolve().parents[2] / "_vendor" / "Ensol_PNE_framework"
    if vendor_root.exists():
        import sys

        vendor_str = str(vendor_root)
        if vendor_str not in sys.path:
            sys.path.insert(0, vendor_str)
        from pne_app.io.pne_converter import _read_sch_steps

        def _parse(data: bytes, source_path: Path):
            temp = source_path
            if not temp.exists():
                temp.write_bytes(data)
            return _read_sch_steps(temp)

        return _parse

    raise ImportError(
        "No SCH parser available. Install assb_analyzer or vendor Ensol_PNE_framework."
    )
