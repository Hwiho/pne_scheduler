"""Round-trip and structural validation helpers."""

from __future__ import annotations

from pathlib import Path

from ..ir.project import ScheduleProject
from ..io.reader import read_sch
from ..io.writer import write_sch


def validate_written_project(project: ScheduleProject, output_path: Path) -> list[str]:
    """Write project to disk and attempt to re-parse with available SCH reader."""
    warnings: list[str] = []
    write_sch(project, output_path)
    try:
        parsed = read_sch(output_path)
    except (ImportError, ValueError) as exc:
        warnings.append(f"Re-parse skipped or failed: {exc}")
        return warnings

    if parsed.step_count != len(project.expand_steps()) + (
        0 if project.expand_steps() and project.expand_steps()[-1].step_type == "end" else 1
    ):
        warnings.append(
            f"Step count mismatch: parsed={parsed.step_count}, expected from IR differs"
        )
    return warnings
