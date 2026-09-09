"""G0 — the stateless path, and the two routes that were dead ends."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pne_scheduler.import_session import ImportSession
from pne_scheduler.io.template_writer import SchPatchPlan, apply_sch_patch
from pne_scheduler.ui.document import ProjectDocument
from pne_scheduler.ui.workspace_model import WorkspaceModel

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "example" / "example.schproj"
SCH = (
    ROOT / "example" / "fixtures" / "capacheck_zip"
    / "07100766_260511_SJ1300_dry_40um_RPT_500cycle.sch"
)


# --- a document that keeps no history --------------------------------------


def _detached() -> WorkspaceModel:
    return WorkspaceModel(
        ProjectDocument.detached(json.loads(EXAMPLE.read_text(encoding="utf-8")))
    )


def test_a_detached_document_edits_without_accumulating_undo():
    """A stateless request holds history on the client; snapshots here are waste."""
    model = _detached()
    before = len(model.project.modules)
    model.add_module("rest")

    assert len(model.project.modules) == before + 1
    assert not model.document.can_undo
    assert not model.document.can_redo


def test_it_still_reports_the_label_of_the_edit():
    """That label is what a stateless caller names its own history entry with."""
    model = _detached()
    model.add_module("rest")
    assert model.document.last_label == "Rest 추가"


def test_a_detached_document_writes_no_recovery_file(tmp_path):
    model = _detached()
    model.add_module("rest")
    assert model.document.autosave(force=True) is None


def test_a_normal_document_still_keeps_history(tmp_path):
    model = WorkspaceModel(ProjectDocument.new(autosave_dir=tmp_path / "recovery"))
    model.add_module("rest")
    assert model.document.can_undo
    assert model.document.last_label


def test_a_failed_edit_leaves_a_detached_document_unchanged():
    model = _detached()
    before = model.project.to_dict()
    with pytest.raises(ValueError):
        model.add_module("not_a_module")
    assert model.project.to_dict() == before


# --- the patch plan can now leave the process ------------------------------


def test_a_patch_plan_round_trips_through_json(tmp_path):
    session = ImportSession.open(SCH)
    session.stage(3, "fVref", 25.0)
    plan = session.propose_patch().plan

    path = plan.save(tmp_path / "plan.json")
    assert SchPatchPlan.load(path) == plan
    assert SchPatchPlan.from_dict(plan.to_dict()) == plan


def test_the_serialized_version_is_the_form_from_dict_reads():
    session = ImportSession.open(SCH)
    session.stage(3, "fVref", 25.0)
    data = session.propose_patch().plan.to_dict()
    assert data["expected_version"] == "0x00010004"
    assert data["template_sha256"] == session.sha256


def test_a_session_edit_reaches_the_file_through_the_saved_plan(tmp_path):
    """The whole point of G0: propose, save, apply — without losing the bytes."""
    session = ImportSession.open(SCH)
    session.stage(3, "fVref", 25.0)
    plan_path = session.propose_patch().plan.save(tmp_path / "plan.json")

    output = tmp_path / "patched.sch"
    apply_sch_patch(SCH, SchPatchPlan.load(plan_path), output, allow_analysis_output=True)

    before, after = SCH.read_bytes(), output.read_bytes()
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert 0 < len(changed) <= 4
    assert before[:1760] == after[:1760]


# --- saving a method is reachable ------------------------------------------


def test_the_cli_can_save_and_then_list_a_method(tmp_path, monkeypatch):
    from pne_scheduler.__main__ import main

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    assert main(["library", "--save", str(EXAMPLE), "--name", "왕복 시험"]) == 0
    assert main(["library"]) == 0

    from pne_scheduler.library import MethodLibrary

    saved = MethodLibrary(tmp_path / ".pne_scheduler" / "library").methods()
    assert [entry.name for entry in saved] == ["왕복 시험"]
    assert saved[0].module_count == 2


def test_saving_without_a_name_is_refused(tmp_path, monkeypatch):
    from pne_scheduler.__main__ import main

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert main(["library", "--save", str(EXAMPLE)]) == 2
