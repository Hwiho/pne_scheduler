"""Real Tk interaction regression tests; CI requires a display, not silent skips."""
from __future__ import annotations

import json
import os
import signal
import time
import tkinter as tk

import pytest

from pne_scheduler.ui.native_controller import NativeController
from pne_scheduler.ui.tk_widgets import FieldInput
from pne_scheduler.ui.tk_runtime import create_root
from pne_scheduler.ui.tk_workspace import WorkspaceApp, run_event_loop


@pytest.fixture
def root():
    try:
        window = create_root()
    except tk.TclError:
        if os.environ.get("PNE_REQUIRE_TK"):
            raise
        pytest.skip("No desktop display; CI native job sets PNE_REQUIRE_TK=1")
    window.withdraw()
    yield window
    try:
        window.destroy()
    except tk.TclError:
        pass


def test_repeated_runtime_startup_and_shutdown(root):
    # Reproduce the old repeated-initialization boundary, not just one launch.
    for _ in range(30):
        window = create_root()
        try:
            window.withdraw()
            assert window.tk.call("info", "commands", "tcl_findLibrary")
            window.update_idletasks()
        finally:
            window.destroy()


def drain(root, app):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        root.update()
        if not app.busy:
            return
        time.sleep(.01)
    pytest.fail("Native worker did not finish")


@pytest.mark.parametrize("kind,value,unit,text,canonical", [
    ("duration_s", 21600, "시간", "6", "21600"),
    ("duration_s", 1800, "분", "30", "1800"),
    ("duration_s", 30, "초", "30", "30"),
    ("soc_percent", .8, "%", "80", "80%"),
    ("voltage_v", 4.2, "V", "4.2", "4.2"),
])
def test_numeric_fields_use_one_unit_and_commit(root, kind, value, unit, text, canonical):
    received = []
    field = FieldInput(root, {"kind": kind, "numericValue": value}, received.append)
    assert field.variable.get() == text
    assert field.unit_variable.get() == unit
    field.apply_button.invoke()
    assert received == [canonical]


def test_unit_change_preserves_quantity_and_does_not_commit(root):
    received = []
    field = FieldInput(root, {"kind": "duration_s", "numericValue": 1800}, received.append)
    field.unit_variable.set("시간")
    field._change_unit()
    assert field.variable.get() == "0.5" and field.get() == "1800"
    assert received == []
    field.variable.set("")
    assert field.get() == ""


def test_console_interrupt_uses_normal_tk_shutdown(root, tmp_path):
    app = WorkspaceApp(root, NativeController(data_dir=tmp_path))
    original = signal.getsignal(signal.SIGINT)
    root.after(100, lambda: signal.raise_signal(signal.SIGINT))
    run_event_loop(app)
    assert app._closed
    assert signal.getsignal(signal.SIGINT) == original


def test_unit_draft_survives_rebuild_but_does_not_hide_undo(root):
    definition = {"kind": "duration_s", "numericValue": 1800, "value": "30분"}
    field = FieldInput(root, definition)
    field.unit_variable.set("시간")
    field._change_unit()
    field.variable.set("0.75")
    copy = FieldInput(root, definition)
    copy.restore_draft(field.draft())
    assert copy.unit_variable.get() == "시간" and copy.get() == "2700"
    changed = FieldInput(root, {"kind": "duration_s", "numericValue": 60, "value": "1분"})
    changed.restore_draft(field.draft())
    assert changed.get() == "60"


@pytest.mark.parametrize("kind,values,expected", [
    ("soc_percent_list", [.8, .5, .2], "80%, 50%, 20%"),
    ("fraction_list", [.8, .5, .2], "80%, 50%, 20%"),
    ("duration_list", [1800, 3600], "1800, 3600"),
    ("c_rate_list", [1 / 3, .5, 2], f"{1 / 3}, 0.5, 2"),
])
def test_list_units_keep_all_values_and_full_precision(root, kind, values, expected):
    widget = FieldInput(root, {"kind": kind, "numericValues": values})
    assert widget.get() == expected


def test_all_panels_edit_save_library_batch_and_storage(root, tmp_path, monkeypatch):
    errors = []
    monkeypatch.setattr("pne_scheduler.ui.tk_workspace.messagebox.showerror", lambda *a, **k: errors.append(a))
    app = WorkspaceApp(root, NativeController(data_dir=tmp_path / "data"))
    drain(root, app)
    assert len(app.notebook.tabs()) == 7
    app.perform("setEquipmentUnit", {"unit": "PNE02"})
    drain(root, app)
    app.perform("addModule", {"moduleType": "formation"})
    drain(root, app)
    assert app.controller.project["modules"]
    protocol, library, export, imported, storage, data = app.panels
    assert protocol._field_widgets
    for panel in app.panels:
        app.notebook.select(panel)
        drain(root, app)
        panel.refresh()
    app.submit(lambda: app.controller.save(tmp_path / "ui.schproj"))
    drain(root, app)
    assert (tmp_path / "ui.schproj").exists()
    app.submit(lambda: app.controller.save_method("native-ui"), lambda _: library._load_library())
    drain(root, app)
    assert library._methods
    assert not errors
    app._shutdown()


def test_actual_batch_buttons_write_files_and_invalidate_preview(root, tmp_path, monkeypatch):
    errors = []
    monkeypatch.setattr("pne_scheduler.ui.tk_workspace.messagebox.showerror", lambda *a, **k: errors.append(a))
    app = WorkspaceApp(root, NativeController(data_dir=tmp_path / "data"))
    drain(root, app)
    app.perform("setEquipmentUnit", {"unit": "PNE02"})
    drain(root, app)
    app.perform("addModule", {"moduleType": "formation"})
    drain(root, app)
    panel = app.panels[2]
    app.notebook.select(panel)
    panel.cells_text.insert("1.0", "CELL01,80\nCELL02,90")
    panel.cell_table.operate("paste")
    panel.out_dir.set(str(tmp_path / "batch"))
    root.update()
    panel.batch_plan_button.invoke()
    drain(root, app)
    assert panel._batch_preview["ok"]
    assert panel.batch_export_button.instate(["!disabled"])
    panel.batch_export_button.invoke()
    drain(root, app)
    manifest = json.loads((tmp_path / "batch" / "batch-manifest.json").read_text())
    assert len(manifest["cells"]) == 2
    assert not manifest["equipmentExecutable"]
    app.perform("setProjectName", {"name": "invalidate"})
    drain(root, app)
    assert panel._batch_preview is None
    assert panel.batch_export_button.instate(["disabled"])
    assert not errors
    app._shutdown()


def test_storage_widgets_add_complete_archive_restore(root, tmp_path, monkeypatch):
    errors = []
    monkeypatch.setattr("pne_scheduler.ui.tk_workspace.messagebox.showerror", lambda *a, **k: errors.append(a))
    monkeypatch.setattr("pne_scheduler.ui.tk_storage.messagebox.askokcancel", lambda *a, **k: True)
    app = WorkspaceApp(root, NativeController(data_dir=tmp_path))
    drain(root, app)
    storage = app.panels[4]
    app.notebook.select(storage)
    drain(root, app)
    storage.sample_var.set("QA-셀01")
    storage.days_var.set("30")
    storage.checkpoints_var.set("7,14")
    storage._add_record()
    drain(root, app)
    assert len(storage._records) == 1
    record = storage._records[0]
    assert len(record["alerts"]) == 3
    storage._archive(record["id"], True)
    drain(root, app)
    assert storage._records[0]["archivedAt"]
    storage._archive(record["id"], False)
    drain(root, app)
    assert not storage._records[0]["archivedAt"]
    assert not errors
    app._shutdown()


def test_data_care_buttons_backup_restore_and_preserve_drafts(root, tmp_path):
    app = WorkspaceApp(root, NativeController(data_dir=tmp_path / "data"))
    drain(root, app)
    app.perform("addModule", {"moduleType": "rest"})
    drain(root, app)
    panel = app.panels[5]
    app.notebook.select(panel)
    drain(root, app)
    panel.output_path.set(str(tmp_path / "verified.zip"))
    panel.external_stopped.set(True)
    panel.preview_button.invoke()
    drain(root, app)
    assert panel._plan and panel.create_button.instate(["!disabled"])
    app.perform("setProjectName", {"name": "changed"})
    drain(root, app)
    assert panel._plan is None and panel.create_button.instate(["disabled"])
    assert panel.output_path.get() == str(tmp_path / "verified.zip")
    panel.preview_button.invoke()
    drain(root, app)
    panel.create_button.invoke()
    drain(root, app)
    assert (tmp_path / "verified.zip").exists()
    panel.inspect_button.invoke()
    drain(root, app)
    assert panel._inspection
    panel.destination.set(str(tmp_path / "restore"))
    panel.restore_button.invoke()
    drain(root, app)
    assert (tmp_path / "restore" / "restore-report.json").exists()
    assert "복원 완료" in panel.result_text.get()
    assert app.controller.data_dir == tmp_path / "data"
    panel.archive_path.set(str(tmp_path / "missing.zip"))
    panel.inspect_button.invoke()
    drain(root, app)
    assert "처리하지 못했습니다" in panel.result_text.get()
    assert panel.archive_path.get() == str(tmp_path / "missing.zip")
    app._shutdown()


def test_desktop_narrow_width_keeps_tabs_and_numeric_controls_usable(root, tmp_path):
    app = WorkspaceApp(root, NativeController(data_dir=tmp_path))
    drain(root, app)
    root.deiconify()
    root.geometry("960x640")
    app.perform("addModule", {"moduleType": "qpeed"})
    drain(root, app)
    panel = app.panels[0]
    app.notebook.select(panel)
    root.update()
    assert all(panel.winfo_width() > 0 for panel in app.panels)
    assert panel._inspector_scroll.winfo_width() >= 250
    for widget in panel._field_widgets.values():
        assert widget.entry.winfo_width() >= 50
        if hasattr(widget, "apply_button"):
            assert widget.apply_button.winfo_x() + widget.apply_button.winfo_width() <= widget.winfo_width()
    app._shutdown()


def test_preset_parameter_edits_update_duration_and_history(root, tmp_path, monkeypatch):
    monkeypatch.setattr("pne_scheduler.ui.tk_workspace.messagebox.showerror", lambda *a, **k: pytest.fail(str(a)))
    app = WorkspaceApp(root, NativeController(data_dir=tmp_path))
    drain(root, app)
    app.perform("addModule", {"moduleType": "rest"})
    drain(root, app)
    panel = app.panels[0]
    field = next(widget for key, widget in panel._field_widgets.items() if key[-1] == "duration_s")
    field.variable.set("30")
    field.apply_button.invoke()
    drain(root, app)
    assert app.project["modules"][0]["params"]["duration_s"] == 1800
    assert app.controller.views["procedure"]["durationSeconds"] == 1800
    app.undo()
    drain(root, app)
    assert app.project["modules"][0]["params"]["duration_s"] == 600
    app.redo()
    drain(root, app)
    assert app.project["modules"][0]["params"]["duration_s"] == 1800
    app._shutdown()


def test_cell_table_edit_error_focus_and_copy(root):
    from pne_scheduler.ui.tk_cell_table import CellTable
    changes = []
    table = CellTable(root, lambda: changes.append(True))
    table.pack(fill="both", expand=True)
    table.set_rows([{"cellId": "A01", "referenceCapacityMah": ""}])
    table.focus_issue(0, "referenceCapacityMah")
    assert table._index == 0
    table.capacity_var.set("80")
    assert table.get_rows()[0]["referenceCapacityMah"] == "80"
    assert table.check["ok"]
    table.operate("duplicate")
    assert [r["cellId"] for r in table.rows] == ["A01", "A02"]
    assert table.rows[1]["referenceCapacityMah"] == "80"
    table.focus_issue(1, "cellId")
    table.id_var.set("a01")
    assert len(table.check["issues"]) == 2
    table.set_enabled(False)
    assert table.capacity_entry.instate(["disabled"])
    assert changes


def test_key_conditions_error_is_inline_and_can_be_corrected(root, tmp_path, monkeypatch):
    errors = []
    monkeypatch.setattr("pne_scheduler.ui.tk_workspace.messagebox.showerror", lambda *a, **k: errors.append(a))
    app = WorkspaceApp(root, NativeController(data_dir=tmp_path))
    drain(root, app)
    app.perform("addModule", {"moduleType": "formation"})
    drain(root, app)
    panel = app.panels[0]
    module_id = app.project["modules"][0]["id"]
    field = panel._field_widgets[(module_id, "param", "charge_c_rate")]
    field.variable.set("invalid")
    field.apply_button.invoke()
    drain(root, app)
    assert field.issue_text.get()
    assert not errors
    field.variable.set("0.2")
    field.apply_button.invoke()
    drain(root, app)
    assert app.project["modules"][0]["params"]["charge_c_rate"] == .2
    assert ("setup", "nominal_capacity_mAh") in panel._field_widgets
    app.undo()
    drain(root, app)
    assert app.project["modules"][0]["params"].get("charge_c_rate", .1) == .1
    app._shutdown()
