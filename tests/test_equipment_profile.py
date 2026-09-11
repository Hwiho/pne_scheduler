from __future__ import annotations

import json
from pathlib import Path

from pne_scheduler.ir import (
    CellProfile,
    EquipmentProfile,
    ModuleNode,
    SCHPROJ_SCHEMA_V2,
    ScheduleProject,
    effective_current_limit_mA,
    known_units,
    load_project_lenient,
)


def test_registry_backed_profile_carries_rating_build_and_layout() -> None:
    profile = EquipmentProfile.from_unit("PNE2")

    assert profile.unit == "PNE02"
    assert profile.max_current_mA == 500.0
    assert profile.ctspro_build == "CYCC-1004-S01-R004-N01"
    assert profile.layout_key == "0x00010003/612"
    assert profile.is_complete


def test_pne15_registry_profile_is_6a_with_observed_v4_layout() -> None:
    profile = EquipmentProfile.from_unit("PNE15")

    assert profile.unit == "PNE15"
    assert profile.max_current_mA == 6000.0
    assert profile.rating_label == "6A"
    assert profile.ctspro_build == "CYCC-1004-S01-R004-N01"
    assert profile.layout_key == "0x00010004/696"
    assert profile.is_complete
    assert profile.layout_confirmed is False


def test_pne18_registry_profile_is_6a_with_observed_612_layout() -> None:
    profile = EquipmentProfile.from_unit("PNE18")

    assert profile.unit == "PNE18"
    assert profile.max_current_mA == 6000.0
    assert profile.rating_label == "6A"
    assert profile.ctspro_build == "CYCC-1006-S01-R006-N04"
    assert profile.layout_key == "0x00010003/612"
    assert profile.is_complete
    assert profile.layout_confirmed is False


def test_pne19_registry_profile_is_6a_with_observed_696_layout() -> None:
    profile = EquipmentProfile.from_unit("PNE19")

    assert profile.unit == "PNE19"
    assert profile.max_current_mA == 6000.0
    assert profile.rating_label == "6A"
    assert profile.ctspro_build == "CYCN-P1107-S01-8001-N03"
    assert profile.layout_key == "0x00010004/696"
    assert profile.is_complete
    assert profile.layout_confirmed is False


def test_pne20_registry_profile_is_6a_with_observed_696_layout() -> None:
    profile = EquipmentProfile.from_unit("PNE20")

    assert profile.unit == "PNE20"
    assert profile.max_current_mA == 6000.0
    assert profile.rating_label == "6A"
    assert profile.ctspro_build == "CYCSA-P1107-S01-R001-N013"
    assert profile.layout_key == "0x00010004/696"
    assert profile.is_complete
    assert profile.layout_confirmed is False


def test_unknown_unit_stays_incomplete_rather_than_guessing() -> None:
    profile = EquipmentProfile.from_unit("PNE99")

    assert not profile.is_complete
    assert "최대 전류" in profile.missing_fields()
    assert "PNE01" in known_units()


def test_effective_limit_takes_the_smaller_of_cell_and_equipment() -> None:
    equipment = EquipmentProfile.from_unit("PNE02")

    assert effective_current_limit_mA(800.0, equipment) == 500.0
    assert effective_current_limit_mA(200.0, equipment) == 200.0
    assert effective_current_limit_mA(None, None) is None


def test_project_round_trips_equipment_and_review_state(tmp_path: Path) -> None:
    project = ScheduleProject(
        name="round trip",
        cell_profile=CellProfile(24.0, 4.2, 2.5),
        equipment=EquipmentProfile.from_unit("PNE02"),
        modules=[ModuleNode("m1", "rest", {"duration_s": 60.0})],
    )
    project.review.ctspro_reviewed = True
    project.review.ctspro_reviewer = "검토자"
    path = tmp_path / "project.schproj"
    project.save(path)

    reloaded = ScheduleProject.load(path)

    assert json.loads(path.read_text(encoding="utf-8"))["schema"] == SCHPROJ_SCHEMA_V2
    assert reloaded.equipment == project.equipment
    assert reloaded.review.ctspro_reviewed
    assert reloaded.review.ctspro_reviewer == "검토자"


def test_v1_project_migrates_and_says_the_equipment_is_missing(tmp_path: Path) -> None:
    path = tmp_path / "legacy.schproj"
    path.write_text(
        json.dumps(
            {
                "schema": "pne_scheduler.schproj/v1",
                "name": "legacy",
                "cell_profile": {"nominal_capacity_mAh": 80.0, "v_max": 4.2, "v_min": 2.5},
                "modules": [{"id": "r1", "module_type": "rest", "params": {}}],
                "connections": [],
            }
        ),
        encoding="utf-8",
    )

    load = load_project_lenient(path)

    assert load.migrated_from == "pne_scheduler.schproj/v1"
    assert load.project.equipment is None
    assert any("장비 프로파일" in repair for repair in load.repairs)


def test_the_equipment_rating_constrains_validation_even_without_a_cell_limit() -> None:
    from pne_scheduler.validate.preflight import validate_project

    project = ScheduleProject(
        name="over rating",
        cell_profile=CellProfile(80.0, 4.2, 2.5),
        equipment=EquipmentProfile.from_unit("PNE02"),
        modules=[ModuleNode("qpeed_1", "qpeed", {"variant": "full"})],
    )

    result = validate_project(project)
    breaches = [issue for issue in result.errors if issue.code == "CURRENT_LIMIT"]

    assert breaches
    assert "PNE02" in breaches[0].message
