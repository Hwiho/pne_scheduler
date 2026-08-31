from __future__ import annotations

import pytest

from pne_scheduler.engine.duration import (
    estimate_steps_duration,
    format_duration,
)
from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.ir.step_intent import StepIntent
from pne_scheduler.modules.cycle_life import CycleLifeModule
from pne_scheduler.modules.formation import FormationModule

CELL = CellProfile(
    nominal_capacity_mAh=80.0,
    v_max=4.2,
    v_min=2.5,
    max_current_mA=800.0,
)


def test_timed_steps_have_exact_duration() -> None:
    estimate = estimate_steps_duration(
        [StepIntent(step_type="rest", end_time_s=125.0)]
    )

    assert estimate.estimated_seconds == 125.0
    assert estimate.is_exact
    assert estimate.unknown_step_count == 0


def test_formation_duration_is_nominal_c_rate_estimate() -> None:
    steps = FormationModule(
        charge_c_rate=0.1,
        discharge_c_rate=0.1,
        rest_s=60.0,
        cycle_count=1,
    ).expand(CELL)

    estimate = estimate_steps_duration(steps)

    assert estimate.estimated_seconds == pytest.approx(72_120.0)
    assert estimate.is_complete
    assert not estimate.is_exact
    assert any("CV taper" in warning for warning in estimate.warnings)


def test_cycle_life_duration_applies_loop_count() -> None:
    steps = CycleLifeModule(
        charge_c_rate=0.5,
        discharge_c_rate=0.5,
        rest_s=300.0,
        loop_count=10,
    ).expand(CELL)

    estimate = estimate_steps_duration(steps)

    assert estimate.estimated_seconds == pytest.approx(150_000.0)
    assert estimate.exact_seconds == pytest.approx(6_000.0)
    assert estimate.approximate_seconds == pytest.approx(144_000.0)
    assert any("total body executions" in warning for warning in estimate.warnings)


def test_duration_reports_unknown_steps() -> None:
    estimate = estimate_steps_duration([StepIntent(step_type="ocv")])

    assert estimate.estimated_seconds == 0
    assert estimate.unknown_step_count == 1
    assert not estimate.is_complete


def test_duration_format_includes_days_hours_minutes() -> None:
    assert format_duration(90_061) == "1d 1h 1m 1s"
