"""Native/web parity is executable evidence, not a second set of formulas."""
from __future__ import annotations

import builtins
import csv
import hashlib
import json
from pathlib import Path

import pytest

from pne_scheduler.api import routes
from pne_scheduler.api.errors import ApiError
from pne_scheduler.ui.native_controller import NativeController


@pytest.fixture
def controller(tmp_path):
    return NativeController(data_dir=tmp_path / "data")


@pytest.mark.parametrize("module_type", ["formation", "cycle_life", "qc", "qpeed", "rest", "primitive", "hppc"])
def test_native_and_web_transform_and_steps_are_identical(controller, module_type):
    args = {"moduleType": module_type}
    expected = routes.transform("addModule", {"project": controller.project, "args": args})
    actual = controller.edit("addModule", args)
    assert actual["project"] == expected["project"]
    assert actual["views"]["procedure"] == expected["views"]["procedure"]
    assert routes.steps({"project": controller.project}) == routes.steps({"project": expected["project"]})
    before = controller.project
    controller.undo()
    assert not controller.project["modules"]
    controller.redo()
    assert controller.project == before


def test_offline_adapter_does_not_import_flask_or_open_network(tmp_path, monkeypatch):
    original = builtins.__import__
    def guarded(name, *args, **kwargs):
        assert name != "flask" and not name.startswith("flask."), "Native must not require web extras"
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", guarded)
    import socket
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("Offline workspace opened a socket"))
    c = NativeController(data_dir=tmp_path)
    c.edit("addModule", {"moduleType": "formation"})
    c.save(tmp_path / "offline.schproj")
    assert c.project["modules"]


def test_group_child_edit_custom_step_history_save_reopen(controller, tmp_path):
    for kind in ("cc_charge", "rest"):
        controller.edit("addModule", {"moduleType": "primitive", "params": {"kind": kind}})
    ids = [n["id"] for n in controller.project["modules"]]
    controller.edit("groupModules", {"moduleIds": ids, "name": "내 반복", "repeatCount": 3})
    group = controller.project["modules"][0]["id"]
    controller.edit("setGroupChildParam", {"moduleId": group, "index": 1, "key": "duration_s", "text": "30분"})
    controller.edit("detachGroupChild", {"moduleId": group, "index": 0})
    fields = controller.step_fields(group, 0, 0)
    assert fields
    field = next(f for f in fields if f["kind"] == "c_rate")
    controller.edit("setGroupChildStepField", {"moduleId": group, "childIndex": 0, "index": 0, "key": field["key"], "text": "0.5"})
    before = controller.project
    controller.edit("ungroupModule", {"moduleId": group})
    controller.undo()
    assert controller.project == before
    saved = controller.save(tmp_path / "same.schproj")
    assert not controller.document.dirty
    other = NativeController(saved, data_dir=tmp_path / "other")
    assert other.project == controller.project
    normalized = routes.open_project({"data": json.loads(saved.read_text())})
    assert normalized["project"] == other.project


def test_rejected_edit_preserves_history_and_recovery(controller, tmp_path):
    controller.edit("addModule", {"moduleType": "rest"})
    before, revision = controller.project, controller.revision
    with pytest.raises(ApiError):
        controller.edit("setParam", {"moduleId": "absent", "key": "duration_s", "text": "30"})
    assert controller.project == before and controller.revision == revision
    recoveries = controller.recoveries()
    assert recoveries
    other = NativeController(data_dir=tmp_path / "other")
    other.recover(recoveries[0])
    assert other.project == before and other.document.dirty


def test_failed_autosave_keeps_edit_and_blocks_document_replacement(controller, monkeypatch, tmp_path):
    def disk_full(*a, **kw):
        raise OSError("disk full")
    monkeypatch.setattr(controller.document, "autosave", disk_full)
    controller.edit("addModule", {"moduleType": "rest"})
    before = controller.project
    assert controller.notice and controller.document.can_undo
    with pytest.raises(OSError, match="disk full"):
        controller.new()
    assert controller.project == before
    controller.save(tmp_path / "manual.schproj")
    assert not controller.document.dirty and not controller.notice


def test_failed_replace_keeps_saved_file_and_unsaved_edit(controller, monkeypatch, tmp_path):
    path = controller.save(tmp_path / "preserved.schproj")
    original = path.read_bytes()
    controller.edit("addModule", {"moduleType": "rest"})
    def rejected(*a, **kw):
        raise OSError("replace rejected")
    monkeypatch.setattr("pne_scheduler.atomic_files.os.replace", rejected)
    with pytest.raises(OSError, match="replace rejected"):
        controller.save()
    assert path.read_bytes() == original
    assert controller.document.dirty
    assert not list(tmp_path.glob(".pne-save-*"))


def test_saved_project_is_success_even_if_recovery_cleanup_fails(controller, monkeypatch, tmp_path):
    controller.edit("addModule", {"moduleType": "rest"})
    def rejected():
        raise PermissionError("recovery locked")
    monkeypatch.setattr(controller.document, "clear_autosave", rejected)
    path = controller.save(tmp_path / "saved.schproj")
    assert path.exists() and not controller.document.dirty
    assert controller.recoveries()


def test_native_batch_generates_distinct_currents_and_stale_preview_blocks(controller, tmp_path):
    controller.edit("setEquipmentUnit", {"unit": "PNE02"})
    controller.edit("addModule", {"moduleType": "formation"})
    args = {"phase": "formation", "basis": "manual_reference", "kind": "preview", "rows": [
        {"cellId": "A01", "referenceCapacityMah": "80"}, {"cellId": "A02", "referenceCapacityMah": "90"}]}
    preview = controller.plan("cellBatch", args)
    assert preview["ok"]
    result = controller.export_batch(args, preview["token"], tmp_path / "batch")
    assert all(Path(p).exists() for p in result["paths"])
    for cell, current in (("A01", 8), ("A02", 9)):
        with (tmp_path / "batch" / cell / "steps.csv").open(encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        assert max(abs(float(r["전류(mA)"])) for r in rows if r["전류(mA)"]) == current
    controller.edit("setProjectName", {"name": "changed"})
    with pytest.raises(ApiError):
        controller.export_batch(args, preview["token"], tmp_path / "stale")
    assert not (tmp_path / "stale").exists()


def test_saved_method_preview_load_and_undo(controller):
    controller.edit("addModule", {"moduleType": "rest"})
    first = controller.save_method("native-method")["method"]
    module = controller.project["modules"][0]["id"]
    controller.edit("setParam", {"moduleId": module, "key": "duration_s", "text": "30분"})
    controller.save_method("native-method")
    preview = controller.library_preview(first["methodId"], 1, replace=True, compare_version=2)
    assert preview["ok"] and preview["versionDiff"]
    before = controller.project
    controller.edit("loadMethod", {"methodId": first["methodId"], "version": 1, "replace": True, "previewToken": preview["token"]})
    assert controller.project["modules"][0]["params"]["duration_s"] == 600
    controller.undo()
    assert controller.project == before


def test_native_review_sch_bytes_match_web_and_reopen(controller, tmp_path):
    controller.edit("setEquipmentUnit", {"unit": "PNE02"})
    controller.edit("addModule", {"moduleType": "rest"})
    native = controller.export("review_candidate", tmp_path / "native")
    web = routes.export({"project": controller.project, "kind": "review_candidate", "outDir": str(tmp_path / "web")})
    native_sch = next(Path(p) for p in native["paths"] if p.endswith(".sch"))
    web_sch = next(Path(p) for p in web["paths"] if p.endswith(".sch"))
    assert native_sch.read_bytes() == web_sch.read_bytes()
    digest = hashlib.sha256(native_sch.read_bytes()).hexdigest()
    info = controller.import_open(native_sch)
    assert info["sha256"] == digest and info["stepCount"] == 2
    proposal = controller.import_stage(1, "fIref", 120)
    assert proposal["ok"]
    patched = controller.import_patch(tmp_path / "patched.sch")
    assert not patched["equipmentExecutable"]
    assert hashlib.sha256(native_sch.read_bytes()).hexdigest() == digest
    assert controller.import_clear()["accepted"] == []
