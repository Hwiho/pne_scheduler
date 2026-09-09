"""Regression cover for the four Tk tools — skipped where there is no display.

The workspace has had smoke cover since it shipped; the viewer, project editor,
flow editor and resume wizard had none. They are not dead code — the workspace
launches the flow canvas under 고급 도구 and the others remain the way an existing
`.sch` is read — so a rename in the IR could break all four with the whole suite
still green.

These build each tool headless against a real fixture and assert it actually
populated, which is the failure a constructor smoke test alone would miss: a tool
that builds its widgets and then shows an empty table looks identical to a
working one from the outside.
"""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PROJECT = ROOT / "example" / "example.schproj"
SCH_FIXTURE = (
    ROOT / "example" / "fixtures" / "capacheck_zip"
    / "07100766_260511_SJ1300_dry_40um_RPT_500cycle.sch"
)


@pytest.fixture()
def root():
    try:
        window = tk.Tk()
    except tk.TclError as exc:  # headless CI
        pytest.skip(f"Tk is unavailable: {exc}")
    window.withdraw()
    yield window
    window.destroy()


# --- schedule viewer --------------------------------------------------------


def test_the_viewer_fills_its_table_from_a_real_sch(root):
    from pne_scheduler.ui.schedule_viewer import ScheduleViewerApp

    app = ScheduleViewerApp(root)
    app.load_file(SCH_FIXTURE)

    rows = app.tree.get_children()
    assert rows, "the viewer built its table but never populated it"
    assert len(rows) == len(app._document.steps)
    status = app.status_var.get()
    assert SCH_FIXTURE.name in status and str(len(rows)) in status


def test_the_viewer_opens_with_a_path_given_up_front(root):
    from pne_scheduler.ui.schedule_viewer import ScheduleViewerApp

    app = ScheduleViewerApp(root, SCH_FIXTURE)
    assert app.tree.get_children()


# --- project editor ---------------------------------------------------------


def test_the_project_editor_lists_the_modules_it_loaded(root):
    from pne_scheduler.ui.project_editor import ProjectEditorApp

    app = ProjectEditorApp(root)
    app.load_project(EXAMPLE_PROJECT)

    expected = len(json.loads(EXAMPLE_PROJECT.read_text(encoding="utf-8"))["modules"])
    assert len(app._module_vars) == expected
    assert app._project is not None


def test_the_project_editor_survives_a_project_with_bad_values(root, tmp_path):
    """It must open what needs fixing; refusing to load is the worse failure."""
    from pne_scheduler.ui.project_editor import ProjectEditorApp

    source = json.loads(EXAMPLE_PROJECT.read_text(encoding="utf-8"))
    source["modules"][0]["params"]["charge_c_rate"] = -1.0
    broken = tmp_path / "broken.schproj"
    broken.write_text(json.dumps(source), encoding="utf-8")

    app = ProjectEditorApp(root)
    app.load_project(broken)
    assert app._module_vars


# --- flow editor ------------------------------------------------------------


def test_the_flow_editor_previews_the_steps_of_a_loaded_project(root):
    """Preview is a button, not part of loading — so drive the button."""
    from pne_scheduler.ui.flow_editor import FlowEditorApp

    app = FlowEditorApp(root)
    app.load_project(EXAMPLE_PROJECT)
    assert app.model.project.modules
    assert not app.preview_tree.get_children(), "loading should not preview by itself"

    app._preview()
    rows = app.preview_tree.get_children()
    assert rows, "the step preview stayed empty after being asked for one"
    assert len(rows) == len(app.model.preview_steps()[0])


def test_the_flow_editor_starts_on_a_usable_empty_project(root):
    from pne_scheduler.ui.flow_editor import FlowEditorApp

    app = FlowEditorApp(root)
    assert app.model is not None
    assert app.model.project.cell_profile is not None


# --- resume wizard ----------------------------------------------------------


def test_the_resume_wizard_builds_without_a_file_selected(root):
    """It opens empty by design — the user picks the .sch and the data after."""
    from pne_scheduler.ui.resume_wizard import ResumeWizardApp

    app = ResumeWizardApp(root)
    assert app.sch_path is None and app.data_path is None


def test_the_resume_wizard_previews_a_selected_schedule(root):
    from pne_scheduler.io.sch_parser import parse_schedule_file
    from pne_scheduler.ui.resume_wizard import ResumeWizardApp

    app = ResumeWizardApp(root)
    assert not app.orig_tree.get_children()

    app.sch_path = SCH_FIXTURE
    app._load_original_preview()

    rows = app.orig_tree.get_children()
    assert rows, "the original-schedule preview stayed empty"
    assert len(rows) == len(parse_schedule_file(SCH_FIXTURE).steps)


# --- the shared contract ----------------------------------------------------


@pytest.mark.parametrize(
    "module_name, attribute",
    [
        ("schedule_viewer", "launch_schedule_viewer"),
        ("project_editor", "launch_project_editor"),
        ("resume_wizard", "launch_resume_wizard"),
        ("flow_editor", "launch_flow_editor"),
    ],
)
def test_every_tool_still_exposes_its_launcher(module_name, attribute):
    """The run_pne_scheduler_*.py scripts import these by name."""
    import importlib

    module = importlib.import_module(f"pne_scheduler.ui.{module_name}")
    assert callable(getattr(module, attribute))
