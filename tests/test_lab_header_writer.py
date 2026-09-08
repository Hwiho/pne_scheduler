from __future__ import annotations

from pne_scheduler.io.lab_header_writer import build_pne02_reopen_candidate
from pne_scheduler.ir import CellProfile, ModuleNode, ScheduleProject
from pne_scheduler.schema.ensol_v612 import HEADER_SIZE_V3, STEP_SIZE


def test_lab_header_candidate_is_deterministic_and_structurally_sized() -> None:
    project = ScheduleProject(
        name="REOPEN_ONLY_TEST",
        cell_profile=CellProfile(24.0, 4.2, 2.5, max_current_mA=500.0),
        modules=[ModuleNode("q", "qpeed", {"variant": "soc_setting"})],
    )

    first = build_pne02_reopen_candidate(
        project, timestamp="2026-09-09 00:00:00.000"
    )
    second = build_pne02_reopen_candidate(
        project, timestamp="2026-09-09 00:00:00.000"
    )

    assert first.data == second.data
    assert first.step_count == 11
    assert len(first.data) == HEADER_SIZE_V3 + 11 * STEP_SIZE
    assert any("DOD_UNVERIFIED" in warning for warning in first.warnings)


def test_lab_header_candidate_blocks_current_limit_violation() -> None:
    project = ScheduleProject(
        name="TOO_HIGH",
        cell_profile=CellProfile(80.0, 4.2, 2.5, max_current_mA=500.0),
        modules=[ModuleNode("q", "qpeed", {"variant": "full"})],
    )

    try:
        build_pne02_reopen_candidate(project, timestamp="2026-09-09 00:00:00.000")
    except ValueError as exc:
        assert "CURRENT_LIMIT" in str(exc)
    else:
        raise AssertionError("Expected current-limit preflight failure")
