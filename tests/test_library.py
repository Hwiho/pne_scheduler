"""The method library: versions accumulate, and equipment mismatches are said."""

from __future__ import annotations

import json
import logging
import unicodedata
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
    assert entry.method_id.startswith("method-")
    assert len(entry.method_id) == len("method-") + 12
    assert library.latest(entry.method_id) is not None
    assert library.save(name="!!!", modules=MODULES).method_id == entry.method_id
    assert [version.version for version in library.versions(entry.method_id)] == [1, 2]


@pytest.mark.parametrize("name, expected_id", [("수명 표준", "수명-표준"), ("Rest 01", "rest-01")])
def test_existing_nonfallback_ids_are_preserved(library, name, expected_id):
    first = library.save(name=name, modules=MODULES)
    assert first.method_id == expected_id
    original_bytes = first.path.read_bytes()

    # Different Unicode composition and outer whitespace still name the same method.
    second = library.save(name=f"  {unicodedata.normalize('NFD', name)}  ", modules=MODULES)

    assert second.method_id == expected_id and second.version == 2
    assert first.path.read_bytes() == original_bytes


def test_unambiguous_legacy_fallback_id_is_preserved(library):
    legacy = library.save(name="🔥", modules=MODULES, method_id="method")
    original_bytes = legacy.path.read_bytes()

    same = library.save(name="🔥", modules=MODULES)
    different = library.save(name="⚡", modules=MODULES)

    assert same.method_id == "method" and same.version == 2
    assert different.method_id.startswith("method-") and different.version == 1
    assert legacy.path.read_bytes() == original_bytes
    assert {entry.method_id for entry in library.methods()} == {"method", different.method_id}


def test_mixed_legacy_fallback_history_is_not_extended_or_rewritten(library):
    first = library.save(name="🔥", modules=MODULES, method_id="method")
    second = library.save(name="⚡", modules=MODULES, method_id="method")
    originals = {entry.path: entry.path.read_bytes() for entry in (first, second)}

    fire = library.save(name="🔥", modules=MODULES)
    bolt = library.save(name="⚡", modules=MODULES)

    assert fire.method_id != bolt.method_id
    assert fire.method_id != "method" and bolt.method_id != "method"
    assert fire.version == bolt.version == 1
    assert [entry.version for entry in library.versions("method")] == [1, 2]
    assert all(path.read_bytes() == raw for path, raw in originals.items())


def test_existing_hashed_fallback_id_keeps_priority_if_legacy_files_are_added(library):
    hashed = library.save(name="🔥", modules=MODULES)
    legacy = library.save(name="🔥", modules=MODULES, method_id="method")

    saved = library.save(name="🔥", modules=MODULES)

    assert saved.method_id == hashed.method_id and saved.version == 2
    assert library.versions(legacy.method_id) == (legacy,)


@pytest.mark.parametrize(
    "first_name, second_name",
    [("Rest + 01", "Rest - 01"), ("a" * 60 + "1", "a" * 60 + "2")],
)
def test_normal_slug_collisions_keep_the_first_id_and_separate_new_names(
    library, first_name, second_name
):
    first = library.save(name=first_name, modules=MODULES)
    second = library.save(name=second_name, modules=MODULES)

    assert first.method_id != second.method_id
    assert first.version == second.version == 1
    assert library.save(name=first_name, modules=MODULES).method_id == first.method_id
    assert library.save(name=second_name, modules=MODULES).method_id == second.method_id


@pytest.mark.parametrize(
    "changes",
    [
        {"version": "not-a-number"},
        {"version": True},
        {"version": 1.5},
        {"version": 0},
        {"version": None},
        {"equipment": []},
        {"equipment": {"unit": []}},
        {"modules": "broken"},
        {"modules": [None]},
        {"modules": [{"id": "bad", "module_type": "rest", "params": []}]},
        {"name": []},
        {"description": []},
        {"saved_at": {}},
        {"method_id": "wrong-directory"},
        {"version": 2},
    ],
)
def test_malformed_entries_are_skipped_with_path_and_reason(library, caplog, changes):
    valid = library.save(name="정상 방법", modules=MODULES)
    damaged = library.root / "damaged" / "v0001.json"
    damaged.parent.mkdir(parents=True)
    data = {**valid.to_dict(), "method_id": "damaged", **changes}
    damaged.write_text(json.dumps(data), encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="pne_scheduler.library"):
        methods = library.methods()

    assert [entry.method_id for entry in methods] == [valid.method_id]
    messages = [record.getMessage() for record in caplog.records]
    assert any(str(damaged) in message and "건너뜁니다" in message for message in messages)
    assert any("(" in message for message in messages), "the diagnostic must explain why"


def test_invalid_utf8_is_skipped_with_diagnostics(library, caplog):
    valid = library.save(name="정상 방법", modules=MODULES)
    damaged = valid.path.parent / "v0002.json"
    damaged.write_bytes(b"\xff\xfe\x00")

    with caplog.at_level(logging.WARNING, logger="pne_scheduler.library"):
        assert library.versions(valid.method_id) == (valid,)

    assert str(damaged) in caplog.text


def test_saving_after_a_damaged_version_preserves_its_file(library):
    first = library.save(name="정상 방법", modules=MODULES)
    damaged = first.path.parent / "v0002.json"
    damaged.write_text("{keep this recoverable data", encoding="utf-8")
    original_bytes = damaged.read_bytes()

    saved = library.save(name="정상 방법", modules=MODULES)

    assert saved.version == 3
    assert damaged.read_bytes() == original_bytes
    assert [entry.version for entry in library.versions(first.method_id)] == [1, 3]


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
    errors = [row for row in target.validation_rows() if row.severity == "error"]
    assert {row.code for row in errors} == {"ENTRY_SOC_CHAIN_CONFLICT"}


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
