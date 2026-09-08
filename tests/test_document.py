from __future__ import annotations

from pathlib import Path

import pytest

from pne_scheduler.ir import ModuleNode
from pne_scheduler.ui.document import ProjectDocument


def _document(tmp_path: Path) -> ProjectDocument:
    return ProjectDocument.new(autosave_dir=tmp_path / "recovery")


def test_a_new_document_is_clean_until_it_is_edited(tmp_path: Path) -> None:
    document = _document(tmp_path)

    assert not document.dirty
    document.apply("추가", lambda project: project.modules.append(ModuleNode("r", "rest", {})))
    assert document.dirty


def test_undo_and_redo_restore_exact_project_state(tmp_path: Path) -> None:
    document = _document(tmp_path)
    document.apply("추가", lambda project: project.modules.append(ModuleNode("r", "rest", {})))
    snapshot = document.project.to_dict()

    assert document.undo() == "추가"
    assert document.project.modules == []
    assert document.redo() == "추가"
    assert document.project.to_dict() == snapshot
    assert document.undo() == "추가"
    assert document.undo() is None


def test_a_failed_edit_leaves_no_partial_state(tmp_path: Path) -> None:
    document = _document(tmp_path)

    def broken(project) -> None:
        project.modules.append(ModuleNode("r", "rest", {}))
        raise ValueError("중단")

    with pytest.raises(ValueError):
        document.apply("실패", broken)

    assert document.project.modules == []
    assert not document.can_undo


def test_a_no_op_edit_does_not_create_an_undo_entry(tmp_path: Path) -> None:
    document = _document(tmp_path)
    document.apply("아무것도 안 함", lambda project: None)

    assert not document.can_undo


def test_saving_clears_dirty_and_removes_the_recovery_copy(tmp_path: Path) -> None:
    document = _document(tmp_path)
    document.apply("추가", lambda project: project.modules.append(ModuleNode("r", "rest", {})))
    autosave = document.autosave()

    assert autosave is not None and autosave.exists()
    document.save(tmp_path / "saved.schproj")

    assert not document.dirty
    assert not autosave.exists()


def test_a_project_with_errors_still_saves(tmp_path: Path) -> None:
    document = _document(tmp_path)
    document.apply(
        "잘못된 값",
        lambda project: project.modules.append(
            ModuleNode("bad", "cycle_life", {"loop_count": 0})
        ),
    )

    path = document.save(tmp_path / "broken.schproj")

    assert path.exists()


def test_recovery_lists_and_restores_unsaved_work(tmp_path: Path) -> None:
    recovery_dir = tmp_path / "recovery"
    document = _document(tmp_path)
    document.apply("추가", lambda project: project.modules.append(ModuleNode("r", "rest", {})))
    document.autosave()

    snapshots = ProjectDocument.recoveries(recovery_dir)

    assert len(snapshots) == 1
    recovered = ProjectDocument.recover(snapshots[0], autosave_dir=recovery_dir)
    assert [node.id for node in recovered.project.modules] == ["r"]
    assert recovered.dirty

    ProjectDocument.discard_recovery(snapshots[0])
    assert ProjectDocument.recoveries(recovery_dir) == ()


def test_opening_a_repaired_file_marks_it_dirty(tmp_path: Path) -> None:
    path = tmp_path / "legacy.schproj"
    path.write_text(
        '{"schema": "pne_scheduler.schproj/v1", "name": "legacy",'
        ' "cell_profile": {"nominal_capacity_mAh": 24.0, "v_max": 4.2, "v_min": 2.5},'
        ' "modules": [], "connections": []}',
        encoding="utf-8",
    )

    document = ProjectDocument.open(path, autosave_dir=tmp_path / "recovery")

    assert document.load_repairs
    assert document.dirty
