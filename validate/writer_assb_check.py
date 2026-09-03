"""Gate C4 — cross-check writer output with the vendored ASSB parser."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pne_scheduler.validate.assb_parser_diff import compare_fixture_parsers
from pne_scheduler.vendor.assb_sch import parse_sch_cycle_map_bytes


@dataclass(frozen=True, slots=True)
class WriterAssbCrossCheck:
    path: Path
    passed: bool
    layout_match: bool
    step_count_match: bool
    field_mismatch_count: int
    assb_step_count: int | None
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "pne_scheduler.writer_assb_crosscheck/v1",
            "path": str(self.path),
            "passed": self.passed,
            "layout_match": self.layout_match,
            "step_count_match": self.step_count_match,
            "field_mismatch_count": self.field_mismatch_count,
            "assb_step_count": self.assb_step_count,
            "notes": list(self.notes),
        }


def cross_check_writer_output_with_assb(path: str | Path) -> WriterAssbCrossCheck:
    """Require layout/step parity and zero ASSB↔native field mismatches."""
    resolved = Path(path)
    notes: list[str] = []
    assb_map = parse_sch_cycle_map_bytes(resolved.read_bytes(), source_path=resolved)
    if assb_map is None:
        return WriterAssbCrossCheck(
            path=resolved,
            passed=False,
            layout_match=False,
            step_count_match=False,
            field_mismatch_count=0,
            assb_step_count=None,
            notes=("ASSB parser could not detect layout",),
        )

    diff = compare_fixture_parsers(resolved)
    if not diff.layout_match:
        notes.append("ASSB and native layout framing differ")
    if not diff.step_count_match:
        notes.append(
            f"Step count differs: ASSB={diff.assb_step_count}, native={diff.native_step_count}"
        )
    if diff.field_value_mismatches:
        notes.append(
            f"{len(diff.field_value_mismatches)} ASSB↔native field value mismatch(es)"
        )

    # Spot-check ASSB-derived currents against nonzero charge/discharge steps.
    for step in assb_map.current_steps:
        if step.reference_current_mA is not None and step.reference_current_mA < 0:
            notes.append(f"Step {step.step_no}: negative ASSB reference_current_mA")

    passed = (
        diff.layout_match
        and diff.step_count_match
        and len(diff.field_value_mismatches) == 0
        and not notes
    )
    return WriterAssbCrossCheck(
        path=resolved,
        passed=passed,
        layout_match=diff.layout_match,
        step_count_match=diff.step_count_match,
        field_mismatch_count=len(diff.field_value_mismatches),
        assb_step_count=diff.assb_step_count,
        notes=tuple(notes),
    )
