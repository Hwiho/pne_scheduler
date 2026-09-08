"""A 200+ step schedule must stay responsive in the workspace views."""

from __future__ import annotations

import time
from pathlib import Path

from pne_scheduler.ir.procedure import build_procedure
from pne_scheduler.ui.document import ProjectDocument
from pne_scheduler.ui.workspace_model import WorkspaceModel


def _large_model(tmp_path: Path) -> WorkspaceModel:
    model = WorkspaceModel(ProjectDocument.new(autosave_dir=tmp_path / "recovery"))
    model.set_equipment_unit("PNE02")
    model.add_goal("qpeed_full")
    model.add_goal("hppc_full")
    model.add_goal("formation")
    model.add_goal("cycle_life")
    return model


def test_a_large_schedule_expands_and_validates_quickly(tmp_path: Path) -> None:
    model = _large_model(tmp_path)

    start = time.perf_counter()
    view = build_procedure(model.project)
    rows = model.validation_rows()
    summary = model.summary()
    release = model.release()
    elapsed = time.perf_counter() - start

    assert view.total_steps > 200
    assert summary.total_steps == view.total_steps
    assert rows and release.options
    assert elapsed < 5.0


def test_editing_one_field_in_a_large_schedule_stays_local(tmp_path: Path) -> None:
    model = _large_model(tmp_path)
    qpeed = model.modules_of_type("qpeed")[0]

    start = time.perf_counter()
    diff = model.set_param(qpeed, "condition_c_rate", "C/2")
    elapsed = time.perf_counter() - start

    assert diff.modified > 0
    assert diff.added == 0 and diff.removed == 0
    assert elapsed < 5.0


def test_bulk_apply_updates_every_phase_of_the_same_type(tmp_path: Path) -> None:
    model = WorkspaceModel(ProjectDocument.new(autosave_dir=tmp_path / "recovery"))
    first = model.add_goal("cycle_life")
    second = model.add_goal("cycle_life")

    count, diff = model.apply_to_all_of_type("cycle_life", "loop_count", "25")

    assert count == 2
    assert not diff.is_empty
    for module_id in (first, second):
        assert model.form(module_id).field_for("loop_count").view.text == "25"
