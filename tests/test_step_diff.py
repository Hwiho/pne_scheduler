from __future__ import annotations

from pne_scheduler.edit.diff import diff_projects, preview_module_change
from pne_scheduler.ir import CellProfile, ModuleNode, ScheduleProject


def _project(loop_count: int = 10) -> ScheduleProject:
    return ScheduleProject(
        name="diff",
        cell_profile=CellProfile(24.0, 4.2, 2.5),
        modules=[ModuleNode("cycle_life_1", "cycle_life", {"loop_count": loop_count})],
    )


def test_an_unchanged_project_reports_no_step_changes() -> None:
    diff = diff_projects(_project(), _project())

    assert diff.is_empty
    assert diff.headline() == "스텝에는 변화가 없습니다."


def test_a_value_change_is_reported_per_step_with_units() -> None:
    diff = preview_module_change(
        _project(), "cycle_life_1", {"charge_c_rate": 1.0, "loop_count": 10}
    )

    assert diff.modified >= 1
    assert diff.added == 0 and diff.removed == 0
    assert any("1C" in line for line in diff.preview_lines())


def test_a_structural_change_reports_added_steps() -> None:
    before = ScheduleProject(
        name="diff",
        cell_profile=CellProfile(24.0, 4.2, 2.5),
        modules=[ModuleNode("formation_1", "formation", {"cycle_count": 1})],
    )
    after = before.copy()
    after.modules[0].params["cycle_count"] = 3

    diff = diff_projects(before, after)

    assert diff.added == 8
    assert "8개 추가" in diff.headline()


def test_preview_does_not_touch_the_original_project() -> None:
    project = _project()
    preview_module_change(project, "cycle_life_1", {"loop_count": 999})

    assert project.modules[0].params["loop_count"] == 10


def test_an_unbuildable_edit_says_so_instead_of_reporting_mass_deletion() -> None:
    diff = preview_module_change(_project(), "cycle_life_1", {"loop_count": 0})

    assert diff.is_empty
    assert "만들 수 없습니다" in diff.headline()
