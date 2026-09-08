from __future__ import annotations

from pathlib import Path

import pytest

from pne_scheduler.exporting import (
    ExportBlocked,
    export_preview,
    export_review_candidate,
)
from pne_scheduler.ir import CellProfile, EquipmentProfile, ModuleNode, ScheduleProject
from pne_scheduler.release import evaluate_release


def _project(**kwargs) -> ScheduleProject:
    project = ScheduleProject(
        name="release",
        cell_profile=CellProfile(24.0, 4.2, 2.5, max_current_mA=500.0),
        sch_version=0x00010003,
        modules=[ModuleNode("formation_1", "formation", {"cycle_count": 1})],
        **kwargs,
    )
    return project


def test_draft_save_is_never_gated() -> None:
    project = _project()
    project.modules.append(ModuleNode("bad", "cycle_life", {"loop_count": 0}))

    state = evaluate_release(project)

    assert state.allows("draft_save")
    assert not state.allows("preview")
    assert state.stage == "draft"


def test_review_candidate_needs_an_equipment_profile() -> None:
    state = evaluate_release(_project())

    assert state.allows("preview")
    assert not state.allows("review_candidate")
    assert any("장비 프로파일" in blocker for blocker in state.option("review_candidate").blockers)


def test_review_candidate_opens_once_the_unit_is_known() -> None:
    project = _project(equipment=EquipmentProfile.from_unit("PNE02"))

    state = evaluate_release(project)

    assert state.allows("review_candidate")
    assert state.stage == "ctspro_pending"


def test_an_unsupported_unit_is_named_in_the_blocker() -> None:
    project = _project(equipment=EquipmentProfile.from_unit("PNE03"))

    blockers = evaluate_release(project).option("review_candidate").blockers

    assert any("PNE03" in blocker for blocker in blockers)


def test_equipment_export_stays_locked_without_recorded_approvals() -> None:
    project = _project(equipment=EquipmentProfile.from_unit("PNE02"))
    project.review.ctspro_reviewed = True

    state = evaluate_release(project)

    assert state.stage == "ctspro_confirmed"
    assert not state.allows("equipment_export")
    assert any("승인" in blocker for blocker in state.option("equipment_export").blockers)


def test_stage_ladder_marks_only_reached_stages() -> None:
    ladder = evaluate_release(_project()).ladder()

    assert [reached for _stage, _label, reached in ladder] == [True, True, False, False, False]


def test_preview_export_writes_steps_summary_and_project(tmp_path: Path) -> None:
    result = export_preview(_project(), tmp_path / "preview")

    names = {path.name for path in result.paths}
    assert names == {"steps.csv", "summary.txt", "project.schproj"}
    assert "스텝" in (tmp_path / "preview" / "steps.csv").read_text(encoding="utf-8-sig")


def test_blocked_export_raises_with_the_reason(tmp_path: Path) -> None:
    with pytest.raises(ExportBlocked) as error:
        export_review_candidate(_project(), tmp_path / "review")

    assert "장비 프로파일" in str(error.value)


def test_review_candidate_writes_a_reopen_only_pack(tmp_path: Path) -> None:
    project = _project(equipment=EquipmentProfile.from_unit("PNE02"))

    result = export_review_candidate(
        project, tmp_path / "review", timestamp="2026-09-09 00:00:00.000"
    )

    names = {path.name for path in result.paths}
    assert "candidate_REOPEN_ONLY_DO_NOT_RUN.sch" in names
    checklist = (tmp_path / "review" / "REVIEW_CHECKLIST.md").read_text(encoding="utf-8")
    assert "실행하지 마세요" in checklist
    manifest = (
        tmp_path / "review" / "candidate_REOPEN_ONLY_DO_NOT_RUN.sch.manifest.json"
    ).read_text(encoding="utf-8")
    assert '"equipment_executable": false' in manifest
