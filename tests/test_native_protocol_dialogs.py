"""Actual Tk dialogs, real native executor and shared plan/edit routes."""
from __future__ import annotations

from copy import deepcopy
from io import BytesIO
import json
import os
from pathlib import Path
import threading
import time
import tkinter as tk
from tkinter import ttk

import pytest

from pne_scheduler.protocol.qpeed_results import MAX_BYTES
from pne_scheduler.ui.native_controller import NativeController
from pne_scheduler.ui.tk_workspace import WorkspaceApp


KINDS = ("campaign", "qc", "budget", "qpeed")


def drain(app):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        app.root.update()
        if not app.busy:
            return
        time.sleep(.005)
    pytest.fail("Native dialog worker did not finish")


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def button(window, text):
    return next(w for w in descendants(window) if isinstance(w, ttk.Button) and w.cget("text") == text)


def field(window, label):
    heading = next(w for w in descendants(window) if isinstance(w, ttk.Label) and w.cget("text") == label)
    row = heading.grid_info()["row"]
    return next(w for w in heading.master.grid_slaves(row=row) if isinstance(w, ttk.Entry))


def set_value(widget, value):
    widget.setvar(widget.cget("textvariable"), value)


def invoke_command(widget):
    """Also exercise the apply-time guard without relying on disabled UI state."""
    widget.tk.call(widget.cget("command"))


@pytest.fixture
def desktop(tmp_path, monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError:
        if os.environ.get("PNE_REQUIRE_TK"):
            raise
        pytest.skip("Tk display unavailable; required native jobs set PNE_REQUIRE_TK=1")
    root.withdraw()
    errors = []
    root.report_callback_exception = lambda *args: errors.append(args)
    monkeypatch.setattr("pne_scheduler.ui.tk_workspace.messagebox.showerror", lambda *a, **k: errors.append(a))
    controller = NativeController(data_dir=tmp_path / "data")
    ids = {}
    plans, edits = [], []
    real_plan, real_edit = controller.plan, controller.edit

    def plan(action, args=None):
        result = real_plan(action, args)
        plans.append((action, deepcopy(args), deepcopy(result), threading.get_ident()))
        return result

    def edit(action, args=None):
        result = real_edit(action, args)
        edits.append((action, deepcopy(args)))
        return result

    monkeypatch.setattr(controller, "plan", plan)
    monkeypatch.setattr(controller, "edit", edit)
    csv_path = tmp_path / "first.csv"
    csv_path.write_text("Cell ID,Step,Voltage (V),SOC (%)\nA,1,3.71,42\nB,2,3.82,60\n", encoding="utf-8")
    second_path = tmp_path / "second.tsv"
    second_path.write_text("Channel\tStep\tVoltage (mV)\tSOC (%)\nC\t4\t3900\t70\n", encoding="utf-8")
    app = WorkspaceApp(root, controller)
    root.deiconify()
    drain(app)
    yield app, ids, plans, edits, csv_path, second_path
    drain(app)
    app._shutdown()
    assert not errors, errors


def open_dialog(desktop, kind, monkeypatch):
    app, ids, _plans, _edits, csv_path, second_path = desktop
    panel = app.panels[0]
    if kind != "campaign":
        module_type = "cycle_life" if kind == "budget" else kind
        app.controller.edit("addModule", {"moduleType": module_type})
        ids[module_type] = app.controller.selected
        app.refresh()
        _edits.clear()
    if kind == "campaign":
        panel._campaign_dialog()
        preview_text, apply_text = "미리보기", "추가"
    elif kind == "qc":
        panel._qc_dialog(ids["qc"])
        preview_text, apply_text = "미리보기", "적용"
    elif kind == "budget":
        panel._budget_dialog()
        preview_text, apply_text = "계산", "사이클 수 적용"
    else:
        panel._qpeed_dialog(ids["qpeed"])
        preview_text, apply_text = "전압 데이터 미리보기", "선택 전압 적용"
    window = next(w for w in app.root.winfo_children() if isinstance(w, tk.Toplevel))
    if kind == "campaign":
        input_widget, changed = field(window, "총 사이클 (회)"), "150"
    elif kind == "qc":
        input_widget = next(w for w in descendants(window) if type(w) is ttk.Entry)
        set_value(input_widget, "3, 2, 1")
        changed = "2, 1"
    elif kind == "budget":
        input_widget, changed = field(window, "기간 (일)"), "28"
    else:
        monkeypatch.setattr("pne_scheduler.ui.tk_protocol.filedialog.askopenfilename", lambda **kw: str(csv_path))
        button(window, "파일 선택").invoke()
        input_widget = next(w for w in descendants(window) if type(w) is ttk.Entry)
        changed = str(second_path)
    app.root.update()
    return window, button(window, preview_text), button(window, apply_text), input_widget, changed


def preview_and_select(app, kind, window, preview, apply):
    preview.invoke()
    drain(app)
    if kind == "qpeed":
        listing = next(w for w in descendants(window) if isinstance(w, tk.Listbox))
        assert listing.size() > 0
        assert apply.instate(["disabled"]), "QPEED must require a deliberate row choice"
        listing.selection_set(0)
        listing.event_generate("<<ListboxSelect>>", when="tail")
        app.root.update()
    assert not apply.instate(["disabled"])


@pytest.mark.parametrize("kind", KINDS)
def test_preview_apply_uses_reviewed_values_and_one_undo(desktop, kind, monkeypatch):
    app, ids, plans, edits, *_ = desktop
    window, preview, apply, _input, _changed = open_dialog(desktop, kind, monkeypatch)
    before, revision = deepcopy(app.project), app.revision
    preview_and_select(app, kind, window, preview, apply)
    assert app.project == before and app.revision == revision
    action, args, result, thread_id = plans[-1]
    assert thread_id != threading.get_ident()
    apply.invoke()
    assert not window.winfo_exists()
    drain(app)
    assert app.revision == revision + 1
    edit_action, applied = edits[-1]
    if kind == "campaign":
        assert action == "campaign" and edit_action == "addCampaign" and applied == args
        assert applied["dcirRates"] == [1.5] and applied["baselineRpt"] is True
        added = app.project["modules"][len(before["modules"]):]
        assert [node["module_type"] for node in added] == [block["moduleType"] for block in result["blocks"]]
    elif kind == "qc":
        assert edit_action == "applyQcFastCharge" and applied == args
        params = next(node["params"] for node in app.project["modules"] if node["id"] == ids["qc"])
        assert (params["fast_rates_c"], params["fast_voltages_v"], params["fast_times_s"]) == (result["rates"], result["voltages"], result["times"])
    elif kind == "budget":
        assert applied == {"moduleId": ids["cycle_life"], "count": result["totalCycles"]}
    else:
        params = next(node["params"] for node in app.project["modules"] if node["id"] == ids["qpeed"])
        assert params["soc_voltage_v"] == pytest.approx(3.71)
        assert params["start_soc_percent"] == pytest.approx(42)
        assert json.loads(params["soc_voltage_source"])["fileName"] == "first.csv"
        assert applied["mapping"] == result["mapping"] and applied["token"] == result["token"]
    app.undo()
    drain(app)
    assert app.project == before


@pytest.mark.parametrize("kind", KINDS)
def test_input_change_invalidates_preview_until_replanned(desktop, kind, monkeypatch):
    app, _ids, plans, edits, *_ = desktop
    window, preview, apply, input_widget, changed = open_dialog(desktop, kind, monkeypatch)
    preview_and_select(app, kind, window, preview, apply)
    set_value(input_widget, changed)
    assert apply.instate(["disabled"])
    before = deepcopy(app.project)
    invoke_command(apply)
    drain(app)
    assert not edits and app.project == before and window.winfo_exists()
    preview_and_select(app, kind, window, preview, apply)
    apply.invoke()
    drain(app)
    assert edits and app.project != before and not window.winfo_exists()
    if kind == "qpeed":
        assert plans[-1][1]["fileName"] == "second.tsv"
        assert edits[-1][1]["candidateId"] == "row-2"
        assert "3900" in edits[-1][1]["text"]


@pytest.mark.parametrize("kind", KINDS)
def test_project_edit_invalidates_review_and_repreview_reenables(desktop, kind, monkeypatch):
    app, _ids, _plans, edits, *_ = desktop
    window, preview, apply, *_ = open_dialog(desktop, kind, monkeypatch)
    preview_and_select(app, kind, window, preview, apply)
    assert app.perform("setProjectName", {"name": "changed while dialog open"})
    drain(app)
    assert apply.instate(["disabled"])
    before, count = deepcopy(app.project), len(edits)
    invoke_command(apply)
    assert app.project == before and len(edits) == count and window.winfo_exists()
    preview_and_select(app, kind, window, preview, apply)
    apply.invoke()
    drain(app)
    assert len(edits) == count + 1


@pytest.mark.parametrize("kind", KINDS)
def test_busy_apply_keeps_dialog_and_review_for_retry(desktop, kind, monkeypatch):
    app, _ids, _plans, edits, *_ = desktop
    window, preview, apply, *_ = open_dialog(desktop, kind, monkeypatch)
    preview_and_select(app, kind, window, preview, apply)
    released = threading.Event()
    try:
        assert app.submit(lambda: released.wait(5), on_success=lambda _result: None)
        apply.invoke()
        assert window.winfo_exists() and not edits
    finally:
        released.set()
        drain(app)
    apply.invoke()
    drain(app)
    assert not window.winfo_exists() and len(edits) == 1


@pytest.mark.parametrize("kind", KINDS)
def test_changed_back_inputs_do_not_accept_late_worker_result(desktop, kind, monkeypatch):
    app, _ids, _plans, edits, *_ = desktop
    window, preview, apply, input_widget, changed = open_dialog(desktop, kind, monkeypatch)
    original = input_widget.get()
    real_plan = app.controller.plan
    released = threading.Event()

    def delayed(action, args):
        assert released.wait(5)
        return real_plan(action, args)

    monkeypatch.setattr(app.controller, "plan", delayed)
    try:
        preview.invoke()
        assert app.busy
        set_value(input_widget, changed)
        set_value(input_widget, original)
    finally:
        released.set()
        drain(app)
    assert apply.instate(["disabled"])
    invoke_command(apply)
    assert not edits and window.winfo_exists()
    preview_and_select(app, kind, window, preview, apply)


@pytest.mark.parametrize("baseline", (False, True))
def test_campaign_baseline_and_human_policy_have_matching_preview_apply(desktop, baseline, monkeypatch):
    app, _ids, plans, edits, *_ = desktop
    window, preview, apply, *_ = open_dialog(desktop, "campaign", monkeypatch)
    policy = field(window, "RPT 진입 상태")
    assert "charge_to_full" not in policy.cget("values")
    policy.set("입력한 시작 SOC를 직접 확인함")
    baseline_control = next(w for w in descendants(window) if isinstance(w, ttk.Checkbutton))
    assert baseline_control.instate(["selected"])
    preview_and_select(app, "campaign", window, preview, apply)
    baseline_control.invoke()
    assert apply.instate(["disabled"])
    if baseline:
        baseline_control.invoke()
    preview_and_select(app, "campaign", window, preview, apply)
    _, args, result, _ = plans[-1]
    assert args["baselineRpt"] is baseline
    assert args["preparationPolicy"] == "user_confirmed_start_soc"
    assert result["rptCount"] == (5 if baseline else 4)
    assert result["blocks"][0]["moduleType"] == ("rpt" if baseline else "cycle_life")
    apply.invoke()
    drain(app)
    assert edits[-1][1] == args


@pytest.mark.parametrize("change", ("mapping", "capacity"))
def test_qpeed_mapping_or_capacity_change_requires_new_preview(desktop, change, monkeypatch):
    app, _ids, _plans, edits, *_ = desktop
    window, preview, apply, *_ = open_dialog(desktop, "qpeed", monkeypatch)
    preview_and_select(app, "qpeed", window, preview, apply)
    if change == "mapping":
        field(window, "셀/채널 열 (선택)").set("")
    else:
        next(w for w in descendants(window) if isinstance(w, ttk.Checkbutton)).invoke()
    assert apply.instate(["disabled"])
    invoke_command(apply)
    assert not edits
    preview_and_select(app, "qpeed", window, preview, apply)
    apply.invoke()
    drain(app)
    assert len(edits) == 1


def test_budget_retains_unknown_duration_block(desktop, monkeypatch):
    app, _ids, plans, edits, *_ = desktop
    window, preview, apply, *_ = open_dialog(desktop, "budget", monkeypatch)
    for module_type in ("qc", "qpeed"):
        app.controller.edit("addModule", {"moduleType": module_type})
    app.refresh()
    edits.clear()
    before = deepcopy(app.project)
    preview.invoke()
    drain(app)
    result = plans[-1][2]
    assert not result["ok"] and result["totalCycles"] == 0
    assert "예상 시간을 계산할 수 없어" in " ".join(result["errors"])
    assert apply.instate(["disabled"])
    invoke_command(apply)
    assert app.project == before and not edits
    assert window.winfo_exists()


def test_qpeed_file_read_is_bounded_before_planning(desktop, monkeypatch):
    app, _ids, plans, edits, csv_path, _second_path = desktop
    window, preview, apply, *_ = open_dialog(desktop, "qpeed", monkeypatch)
    reads, errors = [], []

    class CyclerFile(BytesIO):
        def read(self, size=-1):
            reads.append(size)
            assert size == MAX_BYTES + 1, "Cycler files must never be read without a bound"
            return super().read(size)

    source = CyclerFile(b"x" * (MAX_BYTES + 100))
    real_open = Path.open

    def open_source(path, *args, **kwargs):
        if path == csv_path:
            assert args == ("rb",)
            return source
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_source)
    monkeypatch.setattr("pne_scheduler.ui.tk_protocol.messagebox.showerror", lambda *a, **k: errors.append(a))
    preview.invoke()
    drain(app)
    assert reads == [MAX_BYTES + 1] and source.closed
    assert errors and "2 MB" in str(errors)
    assert not plans and not edits
    assert apply.instate(["disabled"]) and window.winfo_exists()


def test_protocol_labels_follow_allocated_width(desktop):
    app = desktop[0]
    panel = app.panels[0]
    window = tk.Toplevel(app.root)
    window.geometry("240x200")
    label = panel._label(window, "실제 배정 너비에 맞추어 줄바꿈해야 하는 모듈 조건 설명입니다. " * 6, wrap=420)
    label.pack(fill="x")
    window.deiconify()
    app.root.update()
    assert int(label.cget("wraplength")) == min(label.winfo_width() - 8, 420)
    assert label.winfo_reqheight() > 20
    window.geometry("600x200")
    app.root.update()
    assert int(label.cget("wraplength")) == 420
    window.destroy()
    app.controller.edit("addModule", {"moduleType": "qc"})
    app.refresh()
    app.root.geometry("960x840")
    app.notebook.select(panel)
    app.root.update()
    inspector = panel._inspector_scroll.body
    trust = next(w for w in inspector.winfo_children() if isinstance(w, ttk.Label) and str(w.cget("text")).startswith("검증 상태:"))
    assert 0 < int(trust.cget("wraplength")) <= trust.winfo_width() - 8
    assert trust.winfo_x() + trust.winfo_width() <= inspector.winfo_width()
