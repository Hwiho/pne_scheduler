"""Editing the individual steps of a detached module."""

from __future__ import annotations

from pathlib import Path

import pytest

from pne_scheduler.edit.steps import (
    StepEditError,
    insert_step,
    move_step,
    remove_step,
    set_step_field,
    step_fields,
)
from pne_scheduler.ui.document import ProjectDocument
from pne_scheduler.ui.workspace_model import WorkspaceModel

REST = {"step_type": "rest", "end_time_s": 600.0}
CHARGE = {"step_type": "charge", "mode": "CC", "c_rate": 0.5, "end_voltage_v": 4.2}
END = {"step_type": "end"}


# --- the pure operations ----------------------------------------------------


def test_insert_uses_the_same_definition_as_the_palette():
    """A step added inside a module and one added as its own must match."""
    from pne_scheduler.modules.primitive import PrimitiveModule

    steps = insert_step([REST], 1, "cc_discharge")
    assert steps[1] == PrimitiveModule(kind="cc_discharge").build_step().to_dict()


def test_insert_accepts_the_position_after_the_last_step():
    assert len(insert_step([REST], 1, "rest")) == 2


@pytest.mark.parametrize("index", [-1, 3])
def test_insert_outside_the_list_is_refused(index):
    with pytest.raises(StepEditError, match="범위를 벗어납니다"):
        insert_step([REST, CHARGE], index, "rest")


def test_an_unknown_kind_is_refused():
    with pytest.raises(StepEditError, match="알 수 없는 스텝 종류"):
        insert_step([REST], 0, "teleport")


def test_the_list_may_never_become_empty():
    """An empty module would vanish from the schedule while keeping its row."""
    with pytest.raises(StepEditError, match="모두 지울 수는 없습니다"):
        remove_step([REST], 0)


def test_a_step_may_be_inserted_before_end():
    assert [step["step_type"] for step in insert_step([REST, END], 1, "rest")] == [
        "rest", "rest", "end"
    ]


def test_end_must_stay_last():
    with pytest.raises(StepEditError, match="END 는 마지막"):
        insert_step([REST, END], 2, "rest")
    with pytest.raises(StepEditError, match="END 는 마지막"):
        move_step([REST, END], 1, -1)


def test_moving_past_either_edge_is_a_no_op_not_an_error():
    steps = [REST, CHARGE]
    assert move_step(steps, 0, -1) == steps
    assert move_step(steps, 1, 1) == steps


def test_a_field_is_parsed_in_the_unit_it_is_shown_in():
    steps = set_step_field([REST], 0, "end_time_s", "30분")
    assert steps[0]["end_time_s"] == 1800.0
    steps = set_step_field([CHARGE], 0, "c_rate", "C/3")
    assert steps[0]["c_rate"] == pytest.approx(1 / 3)


def test_clearing_a_field_removes_it_rather_than_zeroing_it():
    """A zero cutoff is a real, dangerous setting; absent is what "none" means."""
    steps = set_step_field([CHARGE], 0, "end_voltage_v", "")
    assert "end_voltage_v" not in steps[0]


def test_an_unparseable_value_leaves_the_list_alone():
    with pytest.raises(StepEditError):
        set_step_field([REST], 0, "end_time_s", "언젠가")


def test_a_field_that_is_not_meant_to_be_typed_is_refused():
    with pytest.raises(StepEditError, match="직접 고칠 수 없습니다"):
        set_step_field([REST], 0, "step_type", "charge")


def test_each_field_shows_its_other_unit():
    views = {view.key: view for view in step_fields(CHARGE, nominal_capacity_mAh=80.0)}
    assert views["c_rate"].detail == "40 mA"
    rest = {view.key: view for view in step_fields(REST, nominal_capacity_mAh=80.0)}
    assert rest["end_time_s"].detail == "10분"


def test_absent_fields_are_not_shown_as_empty_rows():
    keys = {view.key for view in step_fields(REST, nominal_capacity_mAh=80.0)}
    assert "c_rate" not in keys and "voltage_v" not in keys


# --- through the model ------------------------------------------------------


def _detached(tmp_path: Path) -> tuple[WorkspaceModel, str]:
    model = WorkspaceModel(ProjectDocument.new(autosave_dir=tmp_path / "recovery"))
    module_id = model.add_module("formation", {"cycle_count": 1})
    model.detach(module_id)
    return model, model.project.modules[0].id


def test_a_preset_refuses_step_editing_until_it_is_detached(tmp_path):
    model = WorkspaceModel(ProjectDocument.new(autosave_dir=tmp_path / "recovery"))
    module_id = model.add_module("formation")
    assert not model.can_edit_steps(module_id)
    with pytest.raises(StepEditError, match="먼저 분리하세요"):
        model.custom_step_rows(module_id)


def test_editing_a_detached_module_changes_the_schedule(tmp_path):
    model, module_id = _detached(tmp_path)
    before = len(model.project.expand_steps())

    model.insert_step(module_id, 1, "rest")
    model.set_step_field(module_id, 1, "end_time_s", "30분")

    rows = model.custom_step_rows(module_id)
    assert rows[1]["stepType"] == "rest"
    assert len(model.project.expand_steps()) == before + 1
    assert not [row for row in model.validation_rows() if row.severity == "error"]


def test_a_preview_does_not_commit(tmp_path):
    model, module_id = _detached(tmp_path)
    before = model.custom_step_rows(module_id)
    diff = model.preview_step_field(module_id, 0, "c_rate", "1C")
    assert diff is not None
    assert model.custom_step_rows(module_id) == before


def test_every_step_edit_is_its_own_undo_entry(tmp_path):
    model, module_id = _detached(tmp_path)
    original = len(model.custom_step_rows(module_id))

    model.insert_step(module_id, 0, "rest")
    model.remove_step(module_id, 0)
    assert len(model.custom_step_rows(module_id)) == original

    model.document.undo()
    assert len(model.custom_step_rows(module_id)) == original + 1
    model.document.undo()
    assert len(model.custom_step_rows(module_id)) == original
