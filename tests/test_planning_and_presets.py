"""Working backwards from a time budget, and the C-rate chips."""

from __future__ import annotations

from pathlib import Path

import pytest

from pne_scheduler.protocol.planning import cycles_within
from pne_scheduler.protocol.presets import C_RATE_PRESETS, presets_within
from pne_scheduler.ui.document import ProjectDocument
from pne_scheduler.ui.workspace_model import WorkspaceModel

HOUR = 3600.0
DAY = 86400.0


def _linear(seconds_per_cycle: float):
    """A cycle count costs exactly this much — easy to reason about in a test."""
    return lambda count: count * seconds_per_cycle


# --- the search -------------------------------------------------------------


def test_it_returns_the_largest_count_that_fits():
    budget = cycles_within(10 * HOUR, _linear(HOUR))
    assert budget.total_cycles == 10
    assert budget.seconds == 10 * HOUR
    assert budget.headroom_seconds == 0


def test_it_never_overshoots_the_budget():
    budget = cycles_within(10 * HOUR + 1, _linear(HOUR))
    assert budget.total_cycles == 10
    assert budget.seconds <= budget.budget_seconds


def test_the_answer_stays_on_the_requested_grid():
    """A campaign measuring every 50 cycles wants 300, not 336."""
    budget = cycles_within(14 * DAY, _linear(HOUR), step=50)
    assert budget.total_cycles == 300
    assert budget.total_cycles % 50 == 0
    assert any("50 사이클 단위" in note for note in budget.notes)


def test_a_budget_too_small_for_one_cycle_says_so():
    budget = cycles_within(HOUR / 2, _linear(HOUR))
    assert budget.total_cycles == 0
    assert not budget.ok
    assert any("넘습니다" in note for note in budget.notes)


def test_an_unestimatable_schedule_is_reported_not_guessed():
    budget = cycles_within(DAY, lambda _count: None)
    assert budget.errors and not budget.ok


def test_the_search_is_bounded():
    budget = cycles_within(DAY, _linear(0.0001), max_cycles=100)
    assert budget.total_cycles <= 100
    assert any("상한" in note for note in budget.notes)


def test_the_estimate_is_called_a_bounded_number_of_times():
    """Bisection, not a linear walk — the estimator rebuilds the schedule."""
    calls: list[int] = []

    def counted(count: int) -> float:
        calls.append(count)
        return count * HOUR

    cycles_within(5000 * HOUR, counted)
    assert len(calls) < 40, f"{len(calls)} estimator calls is a linear scan"


@pytest.mark.parametrize(
    "budget, step", [(0, 1), (-1, 1), (DAY, 0)]
)
def test_bad_input_returns_errors(budget, step):
    result = cycles_within(budget, _linear(HOUR), step=step)
    assert result.errors and not result.ok


def test_the_estimate_caveat_travels_with_the_answer():
    budget = cycles_within(10 * HOUR, _linear(HOUR))
    assert any("근사" in warning for warning in budget.warnings)


# --- presets ----------------------------------------------------------------


def test_presets_carry_the_value_the_label_claims():
    by_label = {preset.label: preset.value for preset in C_RATE_PRESETS}
    assert by_label["C/3"] == pytest.approx(1 / 3)
    assert by_label["0.5C"] == 0.5
    assert by_label["2C"] == 2.0


def test_every_preset_says_where_it_is_used():
    assert all(preset.usage for preset in C_RATE_PRESETS)


def test_current_follows_the_cell_capacity():
    preset = next(p for p in C_RATE_PRESETS if p.label == "1C")
    assert preset.current_mA(80.0) == 80.0
    assert preset.current_mA(24.0) == 24.0


def test_presets_the_equipment_cannot_deliver_are_withheld():
    """A chip that preflight would reject is worse than no chip."""
    offered = presets_within(1.2)
    assert [p.label for p in offered] == ["0.1C", "C/3", "0.5C", "1C"]


def test_an_unknown_limit_offers_everything():
    assert presets_within(None) == C_RATE_PRESETS
    assert presets_within(0) == C_RATE_PRESETS


# --- through the model ------------------------------------------------------


def _model(tmp_path: Path) -> WorkspaceModel:
    return WorkspaceModel(ProjectDocument.new(autosave_dir=tmp_path / "recovery"))


def test_the_model_asks_the_real_estimator(tmp_path):
    model = _model(tmp_path)
    module_id = model.add_module("cycle_life", {"loop_count": 10})
    budget = model.cycles_within(14 * DAY)

    assert budget.ok
    # The found count must actually fit once committed.
    model.set_cycle_count(module_id, budget.total_cycles)
    assert model.procedure().duration_seconds <= 14 * DAY
    # And one more cycle must not.
    model.set_cycle_count(module_id, budget.total_cycles + 1)
    assert model.procedure().duration_seconds > 14 * DAY


def test_the_search_does_not_disturb_the_project(tmp_path):
    model = _model(tmp_path)
    module_id = model.add_module("cycle_life", {"loop_count": 7})
    entries = len(model.document.undo_entries()) if hasattr(
        model.document, "undo_entries"
    ) else None
    model.cycles_within(30 * DAY)
    assert model.project.modules[0].params["loop_count"] == 7
    assert module_id  # the module is still there, untouched
    if entries is not None:
        assert len(model.document.undo_entries()) == entries


def test_a_project_with_no_cycle_block_is_told_why(tmp_path):
    model = _model(tmp_path)
    model.add_module("rest")
    budget = model.cycles_within(DAY)
    assert budget.errors and "사이클 구간이 없어" in budget.errors[0]


def test_model_presets_respect_the_equipment_rating(tmp_path):
    model = _model(tmp_path)
    labels = [preset.label for preset in model.c_rate_presets()]
    assert labels  # a fresh project has no rating yet, so everything is offered
    assert "1C" in labels
