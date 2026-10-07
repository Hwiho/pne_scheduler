from __future__ import annotations

from datetime import datetime

import pytest

from pne_scheduler.engine.duration import estimate_step_duration, estimate_steps_duration
from pne_scheduler.ir import CellProfile, ModuleNode, ScheduleProject, StepIntent
from pne_scheduler.ir.composer import compose_module_steps
from pne_scheduler.report.summary import summarize_project
from pne_scheduler.ui.document import ProjectDocument


CELL = CellProfile(nominal_capacity_mAh=80.0, v_max=4.2, v_min=2.5)


def test_cycle_budget_rejects_partial_qpeed_duration(tmp_path) -> None:
    from pne_scheduler.ui.workspace_model import WorkspaceModel

    project = ScheduleProject(
        name="partial budget", cell_profile=CELL,
        modules=[
            ModuleNode(id="cycle", module_type="cycle_life", params={"loop_count": 100}),
            ModuleNode(id="qpeed", module_type="qpeed", params={}),
        ],
    )
    model = WorkspaceModel(ProjectDocument(project, autosave_dir=tmp_path))
    assert not model.procedure().duration_complete
    result = model.cycles_within(100 * 86400, "cycle", step=50)
    assert not result.ok
    assert result.total_cycles == 0
    assert result.errors


def test_cycle_budget_accepts_nominal_capacity_qpeed_duration(tmp_path) -> None:
    from pne_scheduler.ui.workspace_model import WorkspaceModel

    project = ScheduleProject(
        name="nominal budget", cell_profile=CELL,
        modules=[
            ModuleNode(id="cycle", module_type="cycle_life", params={"loop_count": 100}),
            ModuleNode(id="qpeed", module_type="qpeed", params={"soc_control": "capacity"}),
        ],
    )
    model = WorkspaceModel(ProjectDocument(project, autosave_dir=tmp_path))
    assert model.procedure().duration_complete
    assert model.cycles_within(100 * 86400, "cycle", step=50).ok


def test_timed_rest_is_exact_and_its_own_upper_bound() -> None:
    estimate = estimate_step_duration(
        StepIntent(step_type="rest", end_time_s=125.0),
        step_index=1,
    )

    assert estimate.seconds == 125.0
    assert estimate.upper_bound_seconds == 125.0
    assert not estimate.approximate


def test_capacity_rate_estimate_is_clipped_at_the_configured_end_time() -> None:
    estimate = estimate_step_duration(
        StepIntent(
            step_type="charge",
            mode="CC",
            c_rate=0.5,
            end_capacity_fraction=1.0,
            end_time_s=1_000.0,
        ),
        step_index=1,
    )

    assert estimate.seconds == 1_000.0
    assert estimate.upper_bound_seconds == 1_000.0
    assert estimate.approximate
    assert estimate.basis == "capacity fraction / C-rate"


def test_safety_timeout_is_not_used_as_the_expected_one_c_duration() -> None:
    estimate = estimate_step_duration(
        StepIntent(
            step_type="discharge",
            mode="CC",
            c_rate=1.0,
            end_voltage_v=CELL.v_min,
            end_time_s=21_600.0,
        ),
        step_index=1,
    )

    assert estimate.seconds == 3_600.0
    assert estimate.upper_bound_seconds == 21_600.0
    assert estimate.approximate


@pytest.mark.parametrize(
    "step, expected_basis",
    [
        (
            StepIntent(
                step_type="charge",
                mode="CC",
                c_rate=1.0,
                end_time_s=57_600.0,
                dod_percent=1.0,
            ),
            "DOD field semantics unverified",
        ),
        (
            StepIntent(
                step_type="charge",
                mode="CC",
                c_rate=1.0,
                voltage_v=4.2,
                end_voltage_v=3.318,
                end_time_s=21_600.0,
            ),
            "partial SOC voltage target",
        ),
    ],
)
def test_unverified_dod_and_partial_voltage_steps_have_no_expected_seconds(
    step: StepIntent,
    expected_basis: str,
) -> None:
    estimate = estimate_step_duration(step, step_index=1)

    assert estimate.seconds is None
    assert estimate.upper_bound_seconds == step.end_time_s
    assert estimate.approximate
    assert expected_basis in estimate.basis


def test_nested_loops_repeat_estimates_unknowns_and_upper_bounds() -> None:
    estimate = estimate_steps_duration(
        [
            StepIntent(step_type="rest", end_time_s=10.0),
            StepIntent(
                step_type="charge",
                mode="CC",
                c_rate=1.0,
                end_time_s=100.0,
                dod_percent=10.0,
            ),
            StepIntent(step_type="loop", loop_goto_step=1, loop_count=2),
            StepIntent(step_type="loop", loop_goto_step=1, loop_count=3),
        ]
    )

    assert estimate.estimated_seconds == 60.0
    assert estimate.exact_seconds == 60.0
    assert estimate.unknown_step_count == 6
    assert estimate.upper_bound_seconds == 660.0
    assert not estimate.is_complete


def test_full_qpeed_capacity_mode_has_a_complete_but_approximate_estimate() -> None:
    steps = compose_module_steps(
        [
            ModuleNode(
                "qpeed",
                "qpeed",
                {"variant": "full", "soc_control": "capacity"},
            )
        ],
        CELL,
    )

    estimate = estimate_steps_duration(steps)

    assert estimate.estimated_seconds == pytest.approx(260_966.47705627704)
    assert estimate.upper_bound_seconds == 1_930_212.0
    assert estimate.is_complete
    assert not estimate.is_exact
    assert estimate.approximate_seconds > 0
    assert any("CV taper" in warning for warning in estimate.warnings)


def test_default_voltage_qpeed_summary_is_partial_and_has_no_finish_time() -> None:
    project = ScheduleProject(
        name="QPEED voltage control",
        cell_profile=CELL,
        modules=[ModuleNode("qpeed", "qpeed", {"variant": "full"})],
    )

    summary = summarize_project(project, start=datetime(2026, 10, 8, 9, 0))

    assert "부분 합계" in summary.duration_text
    assert "전체 시간 미정" in summary.duration_text
    assert summary.finish_text == ""
    assert any("종료 시각을 예측하지 않습니다" in warning for warning in summary.warnings)
