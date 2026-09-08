"""Smoke tests for the Tk workspace — skipped where there is no display."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

import pytest


@pytest.fixture()
def root():
    try:
        window = tk.Tk()
    except tk.TclError as exc:  # headless CI
        pytest.skip(f"Tk is unavailable: {exc}")
    window.withdraw()
    yield window
    window.destroy()


def _app(root, tmp_path: Path):
    from pne_scheduler.ui.document import ProjectDocument
    from pne_scheduler.ui.workspace import WorkspaceApp

    app = WorkspaceApp(root)
    app.model.document = ProjectDocument.new(autosave_dir=tmp_path / "recovery")
    app.refresh_all()
    return app


def test_the_workspace_builds_all_five_tabs(root, tmp_path: Path) -> None:
    app = _app(root, tmp_path)

    labels = [app.notebook.tab(index, "text") for index in range(app.notebook.index("end"))]
    assert labels == ["1. 설정", "2. 프로토콜", "3. 절차", "4. 검증", "5. 내보내기"]


def test_adding_a_goal_populates_procedure_steps_and_export(root, tmp_path: Path) -> None:
    app = _app(root, tmp_path)
    app.model.set_equipment_unit("PNE02")
    app.model.add_goal("formation")
    cycle = app.model.add_goal("cycle_life")
    app.selected_module = cycle
    app.refresh_all()

    assert len(app.phase_tree.get_children()) == 2
    assert len(app.step_tree.get_children()) > 10
    assert "CTSPro 확인 대기" in app.stage_var.get()
    # The form follows the selected phase, unit-aware and fully populated.
    assert set(app._field_widgets) >= {"charge_c_rate", "loop_count"}
    assert app.setup_vars["equipment_unit"].get() == "PNE02"


def test_a_project_with_errors_still_renders_every_tab(root, tmp_path: Path) -> None:
    from pne_scheduler.ir import ModuleNode

    app = _app(root, tmp_path)
    app.model.document.apply(
        "잘못된 값",
        lambda project: project.modules.append(
            ModuleNode("bad", "cycle_life", {"loop_count": 0})
        ),
    )
    app.refresh_all()

    assert app.issue_tree.get_children()
    assert app.model.release().allows("draft_save")
