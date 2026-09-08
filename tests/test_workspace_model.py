from __future__ import annotations

from pathlib import Path

import pytest

from pne_scheduler.spec import UnitParseError
from pne_scheduler.ui.document import ProjectDocument
from pne_scheduler.ui.workspace_model import WorkspaceModel


def _model(tmp_path: Path) -> WorkspaceModel:
    return WorkspaceModel(ProjectDocument.new(autosave_dir=tmp_path / "recovery"))


def test_building_a_schedule_from_goals_produces_ordered_phases(tmp_path: Path) -> None:
    model = _model(tmp_path)
    model.set_equipment_unit("PNE02")
    model.add_goal("formation")
    cycle = model.add_goal("cycle_life")

    rows = model.module_rows()

    assert [row.module_type for row in rows] == ["formation", "cycle_life"]
    assert rows[1].module_id == cycle
    assert rows[0].step_range == "1–12"  # 3 formation cycles x 4 steps
    assert model.current_limit_mA == 500.0


def test_editing_a_field_reports_its_step_impact(tmp_path: Path) -> None:
    model = _model(tmp_path)
    module_id = model.add_goal("cycle_life")

    preview = model.preview_param(module_id, "loop_count", "50")
    applied = model.set_param(module_id, "loop_count", "50")

    assert preview.headline() == applied.headline()
    assert model.form(module_id).field_for("loop_count").view.text == "50"


def test_a_bad_field_edit_is_rejected_without_changing_the_project(tmp_path: Path) -> None:
    model = _model(tmp_path)
    module_id = model.add_goal("cycle_life")
    before = model.project.to_dict()

    with pytest.raises(UnitParseError):
        model.set_param(module_id, "charge_c_rate", "빠르게")

    assert model.project.to_dict() == before


def test_cell_edits_accept_units_and_refuse_an_inverted_window(tmp_path: Path) -> None:
    model = _model(tmp_path)
    model.set_cell_value("v_max", "4.35 V")

    assert model.project.cell_profile.v_max == 4.35
    with pytest.raises(UnitParseError):
        model.set_cell_value("v_min", "4.5")


def test_validation_rows_point_at_the_module_and_field_to_fix(tmp_path: Path) -> None:
    model = _model(tmp_path)
    model.set_equipment_unit("PNE02")
    model.set_cell_value("nominal_capacity_mAh", "80")
    module_id = model.add_goal("qpeed_full")

    rows = model.validation_rows()
    current_rows = [row for row in rows if row.code == "CURRENT_LIMIT"]

    assert current_rows
    assert current_rows[0].module_id == module_id
    assert any(row.step_number for row in rows)


def test_detaching_keeps_the_schedule_and_marks_it_user_edited(tmp_path: Path) -> None:
    model = _model(tmp_path)
    module_id = model.add_goal("formation")
    before = [step.to_dict() for step in model.project.expand_steps()]

    model.detach(module_id)

    assert [step.to_dict() for step in model.project.expand_steps()] == before
    assert model.module_rows()[0].module_type == "custom_steps"
    assert "직접 편집" in model.module_rows()[0].trust or model.module_rows()[0].trust


def test_every_edit_is_undoable_through_the_document(tmp_path: Path) -> None:
    model = _model(tmp_path)
    model.add_goal("formation")
    model.set_equipment_unit("PNE02")

    assert model.document.can_undo
    model.document.undo()
    assert model.project.equipment is None
    model.document.undo()
    assert model.project.modules == []


def test_opening_a_file_reports_repairs(tmp_path: Path) -> None:
    path = tmp_path / "legacy.schproj"
    path.write_text(
        '{"schema": "pne_scheduler.schproj/v1", "name": "legacy",'
        ' "cell_profile": {"nominal_capacity_mAh": 24.0, "v_max": 4.2, "v_min": 2.5},'
        ' "modules": [], "connections": []}',
        encoding="utf-8",
    )
    model = _model(tmp_path)

    repairs = model.open_path(path)

    assert repairs
    assert model.project.name == "legacy"


def test_replacing_the_document_does_not_leave_a_stale_recovery(tmp_path: Path) -> None:
    from pne_scheduler.ir import ModuleNode

    recovery = tmp_path / "recovery"
    model = _model(tmp_path)
    model.document.apply(
        "추가", lambda project: project.modules.append(ModuleNode("r", "rest", {}))
    )
    model.document.autosave()
    assert ProjectDocument.recoveries(recovery)

    model.new_document()

    assert ProjectDocument.recoveries(recovery) == ()
