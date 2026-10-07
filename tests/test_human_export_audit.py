"""Human-style audit of every user-facing schedule export shape.

These tests deliberately cross the same boundaries a user does: compose a
project, export files, reopen the saved project and SCH, and inspect the review
tables and integrity manifests.  They do not claim CTSPro or equipment proof.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from pne_scheduler.batch import export_cell_batch, plan_cell_batch
from pne_scheduler.api.errors import ApiError
from pne_scheduler.api.routes import export as api_export
from pne_scheduler.exporting import (
    ExportBlocked,
    REVIEW_CANDIDATE_NAME,
    export_preview,
    export_review_candidate,
)
from pne_scheduler.io.sch_parser import parse_schedule_file
from pne_scheduler.ir.project import ScheduleProject
from pne_scheduler.modules.catalog import get_module_spec, palette_module_types
from pne_scheduler.modules.primitive import PRIMITIVE_KINDS, PrimitiveModule
from pne_scheduler.spec.form import build_module_form
from pne_scheduler.ui.document import ProjectDocument
from pne_scheduler.ui.workspace_model import WorkspaceModel


def _preset_cases() -> tuple[pytest.ParameterSet, ...]:
    cases = []
    for module_type in palette_module_types():
        if module_type == "primitive":
            continue
        spec = get_module_spec(module_type)
        assert spec is not None
        variants = spec.variants or (None,)
        for variant in variants:
            params = {} if variant is None else {"variant": variant}
            label = module_type if variant is None else f"{module_type}-{variant}"
            cases.append(pytest.param(module_type, params, id=label))
    return tuple(cases)


PRESET_CASES = _preset_cases()

EXPECTED_PRESET_MATRIX = {
    "formation",
    "rest",
    "cycle_life",
    "insitu_cycle",
    "capacheck",
    "rpt",
    "dcir",
    "hppc-full",
    "hppc-legacy_soc_pulse",
    "hppc-discharge_soc_pulse",
    "hppc-charge_soc_pulse",
    "qpeed-full",
    "qpeed-soc_setting",
    "qpeed-legacy_pulse",
    "qc-cycle",
    "qc-1n1q",
    "qc-1_charge",
}
EXPECTED_PRIMITIVE_MATRIX = {
    "rest",
    "ocv",
    "cc_charge",
    "cccv_charge",
    "cv_charge",
    "cc_discharge",
}


def test_audit_matrix_covers_the_whole_user_facing_family() -> None:
    assert {case.id for case in PRESET_CASES} == EXPECTED_PRESET_MATRIX
    assert set(PRIMITIVE_KINDS) == EXPECTED_PRIMITIVE_MATRIX


def _model(tmp_path: Path, *, name: str) -> WorkspaceModel:
    model = WorkspaceModel(ProjectDocument.new(autosave_dir=tmp_path / "recovery"))
    model.set_project_name(name)
    model.set_equipment_unit("PNE02")
    # QPEED's default full variant reaches 18C.  A 24 mAh synthetic cell keeps
    # every catalog default below the known PNE02 500 mA channel limit.
    model.set_cell_value("nominal_capacity_mAh", "24")
    model.set_cell_value("max_current_mA", "500")
    return model


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def _assert_single_final_end_and_loops(rows: list[dict[str, str]]) -> None:
    ends = [index for index, row in enumerate(rows, start=1) if row["종류"].lower() == "end"]
    assert ends == [len(rows)]
    for index, row in enumerate(rows, start=1):
        if row["종류"].lower() != "loop":
            continue
        target = int(row["LOOP 대상"])
        assert 1 <= target < index
        assert int(row["LOOP 횟수"]) >= 1


def _assert_reopen_pack(project, out_dir: Path) -> None:
    expected_steps = project.expand_steps()
    expected_end_positions = [
        index for index, step in enumerate(expected_steps, start=1)
        if step.step_type == "end"
    ]
    assert expected_end_positions == [len(expected_steps)]

    result = export_review_candidate(
        project,
        out_dir,
        timestamp="2026-10-08 00:00:00.000",
    )
    assert all(path.is_file() and path.stat().st_size > 0 for path in result.paths)

    sch_path = out_dir / REVIEW_CANDIDATE_NAME
    parsed = parse_schedule_file(sch_path)
    assert parsed.payload_offset == 1760
    assert parsed.step_size == 612
    assert len(parsed.steps) == len(expected_steps)
    assert [step.step_no for step in parsed.steps] == list(range(1, len(parsed.steps) + 1))
    assert [step.step_no for step in parsed.steps if step.step_type == "END"] == [
        len(parsed.steps)
    ]
    for step in parsed.steps:
        if step.step_type == "LOOP":
            assert 1 <= step.loop_target < step.step_no
            assert step.loop_count >= 1

    _assert_single_final_end_and_loops(_csv_rows(out_dir / "expected_steps.csv"))

    reopened = ScheduleProject.load(out_dir / "source.schproj")
    assert reopened.to_dict() == project.to_dict()
    assert len(reopened.expand_steps()) == len(expected_steps)

    manifest_path = out_dir / f"{REVIEW_CANDIDATE_NAME}.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(sch_path.read_bytes()).hexdigest()
    assert manifest["output"]["sha256"] == digest
    assert manifest["output"]["size"] == sch_path.stat().st_size
    assert manifest["validation"]["all_passed"] is True
    assert manifest["validation"]["equipment_smoke_test"] == "not_run"
    assert manifest["equipment_executable"] is False


@pytest.mark.parametrize("module_type,params", PRESET_CASES)
def test_every_supported_preset_exports_and_reopens(
    tmp_path: Path, module_type: str, params: dict
) -> None:
    model = _model(tmp_path, name=f"human-audit-{module_type}")
    model.add_module(module_type, params)

    preview_dir = tmp_path / "preview"
    preview = export_preview(model.project, preview_dir)
    assert {path.name for path in preview.paths} == {
        "steps.csv",
        "summary.txt",
        "project.schproj",
    }
    assert ScheduleProject.load(preview_dir / "project.schproj").to_dict() == model.project.to_dict()
    _assert_single_final_end_and_loops(_csv_rows(preview_dir / "steps.csv"))

    _assert_reopen_pack(model.project, tmp_path / "reopen")


@pytest.mark.parametrize("kind", sorted(PRIMITIVE_KINDS))
def test_every_primitive_kind_exports_with_its_repeat_loop(tmp_path: Path, kind: str) -> None:
    model = _model(tmp_path, name=f"human-audit-primitive-{kind}")
    model.add_module("primitive", {"kind": kind, "repeat_count": 2})

    _assert_reopen_pack(model.project, tmp_path / "reopen")


def test_cv_primitive_exports_its_explicit_current_ceiling(tmp_path: Path) -> None:
    model = _model(tmp_path, name="human-audit-cv-current-ceiling")
    model.add_module(
        "primitive",
        {
            "kind": "cv_charge",
            "c_rate": 0.25,
            "voltage_v": 4.1,
            "duration_s": 120,
        },
    )
    step = PrimitiveModule.from_params(model.project.modules[0].params).expand(
        model.project.cell_profile
    )[0]
    assert step.mode == "CV"
    assert step.c_rate == pytest.approx(0.25)
    form = build_module_form(
        "primitive",
        model.project.modules[0].params,
        cell=model.project.cell_profile,
        current_limit_mA=model.current_limit_mA,
    )
    assert form.field_for("c_rate") is not None

    rows = _csv_rows(export_preview(model.project, tmp_path / "preview").paths[0])
    cv_row = next(row for row in rows if row["모드"] == "CV")
    assert cv_row["C-rate"].lstrip("~") == "0.25C"
    assert float(cv_row["전류(mA)"]) == pytest.approx(6.0)


def test_qpeed_capacity_soc_is_visible_as_percent_and_mah_in_exported_csv(
    tmp_path: Path,
) -> None:
    model = _model(tmp_path, name="human-audit-qpeed-capacity-soc")
    model.add_module(
        "qpeed",
        {
            "variant": "soc_setting",
            "soc_control": "capacity",
            "start_soc_percent": 20.0,
        },
    )
    rows = _csv_rows(export_preview(model.project, tmp_path / "preview").paths[0])

    assert "용량 종료(%)" in rows[0]
    assert "용량 종료(mAh)" in rows[0]
    capacity_rows = [row for row in rows if row["용량 종료(%)"]]
    assert capacity_rows
    assert any(
        float(row["용량 종료(%)"]) == pytest.approx(20.0)
        and float(row["용량 종료(mAh)"]) == pytest.approx(4.8)
        for row in capacity_rows
    )


def test_composed_group_with_nested_loops_exports_and_reopens(tmp_path: Path) -> None:
    model = _model(tmp_path, name="human-audit-nested-loops")
    rest_id = model.add_module(
        "primitive", {"kind": "rest", "duration_s": 15, "repeat_count": 2}
    )
    cycle_id = model.add_module("cycle_life", {"loop_count": 3, "rest_s": 15})
    model.group_modules([rest_id, cycle_id], "nested-loop-group", repeat_count=2)
    model.add_module("primitive", {"kind": "ocv", "duration_s": 15})

    rows = [
        {
            "종류": step.step_type,
            "LOOP 대상": "" if step.loop_goto_step is None else str(step.loop_goto_step),
            "LOOP 횟수": "" if step.loop_count is None else str(step.loop_count),
        }
        for step in model.project.expand_steps()
    ]
    assert sum(row["종류"] == "loop" for row in rows) == 3
    _assert_single_final_end_and_loops(rows)
    _assert_reopen_pack(model.project, tmp_path / "reopen")


def test_manual_reference_two_cell_two_rate_batch_is_atomic_and_reopenable(
    tmp_path: Path,
) -> None:
    model = _model(tmp_path, name="human-audit-manual-reference-batch")
    model.add_module("cycle_life", {"loop_count": 2, "rest_s": 15})
    rows = [
        {"cellId": "QA01", "referenceCapacityMah": 20},
        {"cellId": "QA02", "referenceCapacityMah": 30},
    ]
    matrix = [
        {"chargeRate": 0.5, "dischargeRate": 1.0},
        {"chargeRate": 1.25, "dischargeRate": 1.5},
    ]
    plan = plan_cell_batch(
        model.project,
        phase="cycle",
        basis="manual_reference",
        kind="review_candidate",
        rows=rows,
        matrix=matrix,
    )
    assert plan.ok, plan.errors
    assert len(plan.rows) == 4
    assert {row["oneCmA"] for row in plan.rows} == {20.0, 30.0}

    target = tmp_path / "two-cell-two-rate"
    paths = export_cell_batch(plan, target, token=plan.token)
    assert target.is_dir()
    assert all(path.is_file() for path in paths)

    manifest = json.loads((target / "batch-manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "pne_scheduler.cell_batch/v2"
    assert manifest["basis"] == "manual_reference"
    assert manifest["evidence"] == "manual_reference_unverified"
    assert manifest["equipmentExecutable"] is False
    assert len(manifest["cells"]) == 4
    for entry in manifest["cells"]:
        cell_dir = target / entry["cellId"] / entry["variantId"]
        for artifact in entry["files"]:
            path = target / artifact["path"]
            assert path.is_file()
            assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
        project = ScheduleProject.load(cell_dir / "source.schproj")
        _assert_single_final_end_and_loops(_csv_rows(cell_dir / "expected_steps.csv"))
        parsed = parse_schedule_file(cell_dir / REVIEW_CANDIDATE_NAME)
        assert len(parsed.steps) == len(project.expand_steps())
        assert [step.step_no for step in parsed.steps if step.step_type == "END"] == [
            len(parsed.steps)
        ]
        for step in parsed.steps:
            if step.step_type == "LOOP":
                assert 1 <= step.loop_target < step.step_no


def test_invalid_and_stale_requests_fail_without_output(tmp_path: Path) -> None:
    model = _model(tmp_path, name="human-audit-rejections")
    model.add_module("cycle_life", {"loop_count": 2})

    invalid = plan_cell_batch(
        model.project,
        phase="cycle",
        basis="manual_reference",
        kind="review_candidate",
        rows=[{"cellId": "QA01", "referenceCapacityMah": 20, "legacyCapacity": 19}],
        matrix=[{"chargeRate": 0.5, "dischargeRate": 1.0}],
    )
    assert not invalid.ok
    assert "두 열" in " ".join(invalid.errors)
    invalid_target = tmp_path / "invalid-output"
    with pytest.raises(ExportBlocked, match="다시 미리보세요"):
        export_cell_batch(invalid, invalid_target, token=invalid.token)
    assert not invalid_target.exists()

    valid = plan_cell_batch(
        model.project,
        phase="cycle",
        basis="manual_reference",
        kind="review_candidate",
        rows=[{"cellId": "QA01", "referenceCapacityMah": 20}],
        matrix=[{"chargeRate": 0.5, "dischargeRate": 1.0}],
    )
    assert valid.ok, valid.errors
    stale_target = tmp_path / "stale-output"
    with pytest.raises(ExportBlocked, match="다시 미리보세요"):
        export_cell_batch(valid, stale_target, token=f"{valid.token}-stale")
    assert not stale_target.exists()


def test_api_export_accepts_new_or_empty_absolute_folder_and_rejects_unsafe_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = _model(tmp_path, name="human-audit-api-export-folder")
    model.add_module("formation", {"cycle_count": 1})
    payload = {"project": model.project.to_dict(), "kind": "preview"}

    new_folder = tmp_path / "new-absolute-output"
    created = api_export({**payload, "outDir": str(new_folder)})
    assert created["ok"] is True
    assert new_folder.is_dir()
    assert all(Path(path).is_file() for path in created["paths"])

    empty_folder = tmp_path / "existing-empty-output"
    empty_folder.mkdir()
    reused = api_export({**payload, "outDir": str(empty_folder)})
    assert reused["ok"] is True
    assert all(Path(path).is_file() for path in reused["paths"])

    occupied_folder = tmp_path / "occupied-output"
    occupied_folder.mkdir()
    (occupied_folder / "keep.txt").write_text("preserve", encoding="utf-8")
    with pytest.raises(ApiError, match="비어 있지 않습니다"):
        api_export({**payload, "outDir": str(occupied_folder)})
    assert (occupied_folder / "keep.txt").read_text(encoding="utf-8") == "preserve"

    monkeypatch.chdir(tmp_path)
    relative_folder = Path("relative-output")
    with pytest.raises(ApiError, match="절대 경로"):
        api_export({**payload, "outDir": str(relative_folder)})
    assert not relative_folder.exists()
