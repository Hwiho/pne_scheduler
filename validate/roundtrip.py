"""Round-trip and structural validation helpers."""

from __future__ import annotations

from pathlib import Path

from ..ir.project import ScheduleProject
from ..io.sch_parser import parse_schedule_file
from ..io.writer import write_sch


def validate_written_project(project: ScheduleProject, output_path: Path) -> list[str]:
    """Write project to disk and require the in-repo viewer parser to reload it."""
    warnings: list[str] = []
    write_sch(project, output_path)
    try:
        parsed = parse_schedule_file(output_path)
    except ValueError as exc:
        warnings.append(f"Re-parse failed: {exc}")
        return warnings

    intents = list(project.expand_steps())
    expected_count = len(intents)
    if not intents or intents[-1].step_type != "end":
        expected_count += 1
    if parsed.step_count != expected_count:
        warnings.append(
            f"Step count mismatch: parsed={parsed.step_count}, expected={expected_count}"
        )
    return warnings
