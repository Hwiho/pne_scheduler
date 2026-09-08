"""The method library: versions accumulate, and equipment mismatches are said."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pne_scheduler.library import LIBRARY_SCHEMA, MethodLibrary
from pne_scheduler.ui.document import ProjectDocument
from pne_scheduler.ui.workspace_model import WorkspaceModel

MODULES = [
    {"id": "cycle_life_1", "module_type": "cycle_life", "params": {"loop_count": 40}},
    {"id": "rpt_1", "module_type": "rpt", "params": {}},
]


@pytest.fixture()
def library(tmp_path: Path) -> MethodLibrary:
    return MethodLibrary(tmp_path / "library")


def _model(tmp_path: Path, library: MethodLibrary) -> WorkspaceModel:
    document = ProjectDocument.new(autosave_dir=tmp_path / "recovery")
    return WorkspaceModel(document, library=library)


# --- storage ----------------------------------------------------------------


def test_saving_twice_keeps_both_versions(library):
    """A method someone is mid-experiment with must not be edited out from under them."""
    first = library.save(name="수명 표준", modules=MODULES[:1])
    second = library.save(name="수명 표준", modules=MODULES)

    assert (first.version, second.version) == (1, 2)
    assert first.method_id == second.method_id
    assert first.path.exists() and second.path.exists()

    versions = library.versions(first.method_id)
    assert [entry.version for entry in versions] == [1, 2]
    assert versions[0].module_count == 1, "v1 was rewritten by the second save"
    assert versions[1].module_count == 2


def test_the_newest_version_is_what_a_listing_shows(library):
    library.save(name="수명 표준", modules=MODULES[:1])
    library.save(name="수명 표준", modules=MODULES)
    library.save(name="다른 방법", modules=MODULES[:1])

    methods = library.methods()
    assert len(methods) == 2, "one row per method, not per version"
    standard = next(entry for entry in methods if entry.name == "수명 표준")
    assert standard.version == 2


def test_a_saved_file_is_readable_json_with_its_schema(library):
    entry = library.save(name="수명 표준", modules=MODULES, equipment_unit="PNE02")
    data = json.loads(entry.path.read_text(encoding="utf-8"))
    assert data["schema"] == LIBRARY_SCHEMA
    assert data["equipment"]["unit"] == "PNE02"
    assert len(data["modules"]) == 2


def test_a_foreign_or_broken_file_is_skipped_not_crashed_on(library, tmp_path):
    entry = library.save(name="수명 표준", modules=MODULES)
    (entry.path.parent / "v0002.json").write_text("{not json", encoding="utf-8")
    (entry.path.parent / "v0003.json").write_text('{"schema": "other/v1"}', encoding="utf-8")
    assert [item.version for item in library.versions(entry.method_id)] == [1]


@pytest.mark.parametrize("name, modules", [("", MODULES), ("   ", MODULES), ("이름", [])])
def test_saving_nothing_useful_is_refused(library, name, modules):
    with pytest.raises(ValueError):
        library.save(name=name, modules=modules)


def test_korean_names_get_distinct_ids(library):
    """Stripping to ASCII collapsed every Korean name onto one id, filing
    unrelated methods as versions of each other."""
    first = library.save(name="수명 표준", modules=MODULES)
    second = library.save(name="급속충전 평가", modules=MODULES)

    assert first.method_id != second.method_id
    assert "/" not in first.method_id and "\\" not in first.method_id
    assert library.latest(first.method_id).name == "수명 표준"
    assert library.latest(second.method_id).name == "급속충전 평가"
    assert first.version == second.version == 1, "these are separate methods"


def test_a_name_that_slugs_to_nothing_still_saves(library):
    entry = library.save(name="!!!", modules=MODULES)
    assert entry.method_id == "method"
    assert library.latest(entry.method_id) is not None


# --- loading ----------------------------------------------------------------


def test_loading_onto_a_different_unit_is_allowed_but_reported(library):
    entry = library.save(name="수명 표준", modules=MODULES, equipment_unit="PNE02")
    plan = library.plan_load(entry, equipment_unit="PNE01")
    assert plan.ok, "a mismatch warns; it does not block"
    assert any("PNE02" in warning and "PNE01" in warning for warning in plan.warnings)


def test_a_missing_equipment_profile_is_reported(library):
    entry = library.save(name="수명 표준", modules=MODULES, equipment_unit="PNE02")
    plan = library.plan_load(entry, equipment_unit="")
    assert any("장비 프로파일이 없어" in warning for warning in plan.warnings)


def test_saved_never_means_verified(library):
    entry = library.save(name="수명 표준", modules=MODULES, equipment_unit="PNE02")
    plan = library.plan_load(entry, equipment_unit="PNE02")
    assert any("검증되었다는 뜻은 아닙니다" in warning for warning in plan.warnings)


# --- through the model ------------------------------------------------------


def test_a_round_trip_reproduces_the_procedure(tmp_path, library):
    source = _model(tmp_path / "a", library)
    source.add_module("cycle_life", {"loop_count": 40})
    source.add_module("rpt")
    source.save_method("수명 + RPT")

    target = _model(tmp_path / "b", library)
    plan = target.plan_method_load(library.methods()[0])
    target.load_method(plan)

    assert [node.module_type for node in target.project.modules] == ["cycle_life", "rpt"]
    assert target.project.modules[0].params["loop_count"] == 40
    assert not [row for row in target.validation_rows() if row.severity == "error"]


def test_loaded_ids_never_collide_with_what_is_already_there(tmp_path, library):
    source = _model(tmp_path / "a", library)
    source.add_module("cycle_life")
    source.save_method("한 구간")

    target = _model(tmp_path / "b", library)
    target.add_module("cycle_life")
    target.load_method(target.plan_method_load(library.methods()[0]))

    ids = [node.id for node in target.project.modules]
    assert len(ids) == len(set(ids)) == 2


def test_loading_is_one_undo_step(tmp_path, library):
    source = _model(tmp_path / "a", library)
    source.add_module("cycle_life")
    source.add_module("rpt")
    source.save_method("두 구간")

    target = _model(tmp_path / "b", library)
    target.load_method(target.plan_method_load(library.methods()[0]))
    assert len(target.project.modules) == 2
    target.document.undo()
    assert target.project.modules == []


def test_replace_clears_what_was_there(tmp_path, library):
    source = _model(tmp_path / "a", library)
    source.add_module("rpt")
    source.save_method("한 구간")

    target = _model(tmp_path / "b", library)
    target.add_module("cycle_life")
    target.load_method(target.plan_method_load(library.methods()[0]), replace=True)
    assert [node.module_type for node in target.project.modules] == ["rpt"]


def test_an_unknown_module_type_is_refused_before_anything_changes(tmp_path, library):
    library.save(
        name="미래 방법",
        modules=[{"id": "x", "module_type": "not_a_module", "params": {}}],
    )
    target = _model(tmp_path / "b", library)
    target.add_module("cycle_life")
    with pytest.raises(ValueError, match="알 수 없는 실험 종류"):
        target.load_method(target.plan_method_load(library.methods()[0]))
    assert len(target.project.modules) == 1
