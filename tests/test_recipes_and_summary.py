from __future__ import annotations

from datetime import datetime

from pne_scheduler.ir import CellProfile, EquipmentProfile, ModuleNode, ScheduleProject
from pne_scheduler.protocol.recipes import (
    get_goal,
    list_goals,
    search_goals,
    validate_goal_catalog,
)
from pne_scheduler.report.summary import module_headline, summarize_project


def _project() -> ScheduleProject:
    return ScheduleProject(
        name="요약",
        cell_profile=CellProfile(24.0, 4.2, 2.5, max_current_mA=500.0),
        equipment=EquipmentProfile.from_unit("PNE02"),
        modules=[
            ModuleNode("formation_1", "formation", {"cycle_count": 2}),
            ModuleNode("qpeed_1", "qpeed", {"variant": "full"}),
        ],
    )


def test_every_goal_maps_onto_a_real_module_and_variant() -> None:
    assert validate_goal_catalog() == ()
    assert len(list_goals()) >= 10


def test_goals_are_searchable_in_korean_and_by_module_name() -> None:
    assert any(goal.module_type == "cycle_life" for goal in search_goals("수명"))
    assert any(goal.module_type == "qpeed" for goal in search_goals("qpeed"))
    assert search_goals("존재하지않는검색어") == ()
    assert search_goals("") == list_goals()


def test_a_goal_carries_its_starting_variant() -> None:
    goal = get_goal("qpeed_soc")

    assert goal is not None
    assert goal.params["variant"] == "soc_setting"


def test_module_headline_speaks_in_lab_terms() -> None:
    cell = CellProfile(24.0, 4.2, 2.5)

    assert module_headline(ModuleNode("f", "formation", {"cycle_count": 3}), cell) == (
        "0.1C 충방전 3회"
    )
    qpeed = module_headline(ModuleNode("q", "qpeed", {"variant": "full"}), cell)
    assert "432 mA" in qpeed and "12단계" in qpeed


def test_summary_reports_cell_equipment_phases_and_finish_time() -> None:
    summary = summarize_project(_project(), start=datetime(2026, 9, 9, 9, 0))
    text = summary.as_text()

    assert "24 mAh" in text
    assert "PNE02" in text
    assert "1. Formation" in text
    assert "2. QPEED" in text
    assert "종료 예정" in summary.finish_text
    assert summary.total_steps > 100


def test_summary_warns_when_the_peak_current_passes_the_limit() -> None:
    project = _project()
    project.cell_profile.nominal_capacity_mAh = 80.0

    summary = summarize_project(project)

    assert any("한계" in warning for warning in summary.warnings)


def test_summary_of_an_empty_project_points_at_the_next_step() -> None:
    project = ScheduleProject(name="빈", cell_profile=CellProfile(24.0, 4.2, 2.5))

    assert "실험 목적" in summarize_project(project).phase_lines[0]
