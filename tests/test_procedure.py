from __future__ import annotations

from pne_scheduler.ir import CellProfile, ModuleNode, ScheduleProject
from pne_scheduler.ir.procedure import (
    build_procedure,
    detach_module,
    move_module,
    procedure_step_rows,
    reorder_modules,
)


def _project() -> ScheduleProject:
    return ScheduleProject(
        name="절차",
        cell_profile=CellProfile(24.0, 4.2, 2.5, max_current_mA=500.0),
        modules=[
            ModuleNode("formation_1", "formation", {"cycle_count": 2}),
            ModuleNode("cycle_life_1", "cycle_life", {"loop_count": 5}),
        ],
    )


def test_phases_carry_contiguous_step_ranges_that_cover_the_schedule() -> None:
    view = build_procedure(_project())

    assert [phase.module_id for phase in view.phases] == ["formation_1", "cycle_life_1"]
    assert view.phases[0].first_step == 1
    assert view.phases[1].first_step == view.phases[0].last_step + 1
    # Every step but the trailing END belongs to a phase.
    assert view.phases[-1].last_step == view.total_steps - 1
    assert view.steps[-1].step_type == "end"


def test_phase_duration_includes_its_own_loop_repeats() -> None:
    few = build_procedure(_project()).phases[1].duration_seconds
    many = _project()
    many.modules[1].params["loop_count"] = 50
    assert build_procedure(many).phases[1].duration_seconds > (few or 0) * 5


def test_moving_a_phase_rewrites_the_run_order_and_the_wiring() -> None:
    project = _project()

    assert move_module(project, "cycle_life_1", -1)
    assert [node.id for node in project.modules] == ["cycle_life_1", "formation_1"]
    assert [(edge.source_id, edge.target_id) for edge in project.connections] == [
        ("cycle_life_1", "formation_1")
    ]
    assert not move_module(project, "cycle_life_1", -1)


def test_reorder_requires_every_module_exactly_once() -> None:
    project = _project()
    reorder_modules(project, ["cycle_life_1", "formation_1"])

    assert [node.id for node in project.modules] == ["cycle_life_1", "formation_1"]


def test_detaching_a_preset_preserves_the_exact_expansion() -> None:
    project = _project()
    before = [step.to_dict() for step in project.expand_steps()]

    detach_module(project, "cycle_life_1")

    assert project.modules[1].module_type == "custom_steps"
    assert project.modules[1].params["source_module_type"] == "cycle_life"
    assert [step.to_dict() for step in project.expand_steps()] == before


def test_step_rows_name_the_phase_each_step_belongs_to() -> None:
    rows = procedure_step_rows(build_procedure(_project()))

    assert rows[0]["phase"] == "Formation"
    assert rows[-1]["step_type"] == "end"


def test_a_module_that_cannot_expand_is_reported_not_raised() -> None:
    project = _project()
    project.modules.append(ModuleNode("bad", "cycle_life", {"loop_count": 0}))

    view = build_procedure(project)

    assert view.errors
    assert any(phase.error for phase in view.phases)
