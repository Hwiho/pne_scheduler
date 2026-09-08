"""QC fast-charge rate changes carry their voltage and time lists with them."""

from __future__ import annotations

from pathlib import Path

import pytest

from pne_scheduler.protocol.qc_fast_charge import fast_charge_for_rates
from pne_scheduler.ui.document import ProjectDocument
from pne_scheduler.ui.workspace_model import WorkspaceModel

SET2 = {
    "rates_c": [4.0, 3.0, 2.0],
    "voltages_v": [3.918, 4.008, 4.006],
    "times_s": [534.0, 524.0, 290.0],
}


def _charge(rates, times):
    """Nominal ampere-seconds per segment, in units of capacity."""
    return [round(rate * time, 3) for rate, time in zip(rates, times)]


def test_lowering_the_rate_lengthens_the_segment_by_the_same_charge():
    plan = fast_charge_for_rates([3.0, 2.0, 1.5], **SET2)
    assert plan.ok
    # Times are rounded to 0.1 s — sub-second precision on a several-minute step
    # is noise the equipment cannot act on — so charge is preserved to within
    # that rounding, not exactly.
    assert _charge(plan.rates_c, plan.times_s) == pytest.approx(
        _charge(SET2["rates_c"], SET2["times_s"]), rel=1e-4
    )
    assert plan.times_s == (712.0, 786.0, 386.7)


def test_unchanged_rates_leave_everything_alone():
    plan = fast_charge_for_rates(SET2["rates_c"], **SET2)
    assert plan.times_s == tuple(SET2["times_s"])
    assert plan.voltages_v == tuple(SET2["voltages_v"])
    assert any("그대로" in note for note in plan.notes)


def test_voltage_limits_are_carried_over_not_recomputed():
    """We have no model for the CC->CV transition, so we must not invent one."""
    plan = fast_charge_for_rates([1.0, 1.0, 1.0], **SET2)
    assert plan.voltages_v == tuple(SET2["voltages_v"])


def test_fewer_segments_truncates():
    plan = fast_charge_for_rates([4.0], **SET2)
    assert len(plan.rates_c) == len(plan.voltages_v) == len(plan.times_s) == 1
    assert plan.times_s == (534.0,)
    assert any("줄였습니다" in note for note in plan.notes)


def test_extra_segments_copy_the_last_one_and_say_so():
    plan = fast_charge_for_rates([4.0, 3.0, 2.0, 1.0], **SET2)
    assert len(plan.times_s) == 4
    # The added segment carries the last segment's charge and voltage limit.
    assert plan.voltages_v[3] == SET2["voltages_v"][-1]
    assert round(plan.rates_c[3] * plan.times_s[3], 1) == round(2.0 * 290.0, 1)
    assert any("추가했습니다" in note for note in plan.notes)
    assert any("반복한 것입니다" in warning for warning in plan.warnings)


def test_the_cv_taper_gap_is_stated_every_time():
    plan = fast_charge_for_rates([2.0, 2.0, 2.0], **SET2)
    joined = " ".join(plan.warnings)
    assert "CCCV" in joined and "임피던스" in joined
    assert "검증되지 않은" in joined


@pytest.mark.parametrize(
    "rates, extra",
    [
        ([], {}),
        ([1.0, -1.0], {}),
        ([1.0], {"rates_c": [], "voltages_v": [], "times_s": []}),
        ([1.0], {"rates_c": [4.0, 3.0], "voltages_v": [3.9], "times_s": [500.0]}),
    ],
)
def test_bad_input_returns_errors_and_no_values(rates, extra):
    plan = fast_charge_for_rates(rates, **{**SET2, **extra})
    assert plan.errors and not plan.ok and not plan.rates_c


# --- through the workspace model --------------------------------------------


def _qc_model(tmp_path: Path) -> tuple[WorkspaceModel, str]:
    model = WorkspaceModel(ProjectDocument.new(autosave_dir=tmp_path / "recovery"))
    return model, model.add_module("qc")


def test_the_model_plans_without_changing_anything(tmp_path):
    model, module_id = _qc_model(tmp_path)
    before = dict(model.project.modules[0].params)
    plan = model.plan_qc_fast_charge(module_id, [3.0, 2.0, 1.5])
    assert plan.ok
    assert model.project.modules[0].params == before


def test_applying_moves_all_three_lists_in_one_undo_step(tmp_path):
    model, module_id = _qc_model(tmp_path)
    plan = model.plan_qc_fast_charge(module_id, [3.0, 2.0, 1.5])
    model.apply_qc_fast_charge(module_id, plan)

    params = model.project.modules[0].params
    assert params["fast_rates_c"] == [3.0, 2.0, 1.5]
    assert params["fast_times_s"] == [712.0, 786.0, 386.7]
    assert len({len(params[key]) for key in
                ("fast_rates_c", "fast_voltages_v", "fast_times_s")}) == 1

    model.document.undo()
    assert model.project.modules[0].params["fast_rates_c"] == [4.0, 3.0, 2.0]


def test_the_result_still_expands_and_validates(tmp_path):
    model, module_id = _qc_model(tmp_path)
    model.apply_qc_fast_charge(module_id, model.plan_qc_fast_charge(module_id, [5.0, 4.0]))
    steps = model.project.expand_steps()
    labels = [s.label for s in steps if s.label and "segment" in s.label]
    assert "QC 5C segment" in labels and "QC 4C segment" in labels
    assert not model.validation_rows() or all(
        row.severity != "error" for row in model.validation_rows()
    )


def test_a_non_qc_module_is_refused(tmp_path):
    model = WorkspaceModel(ProjectDocument.new(autosave_dir=tmp_path / "recovery"))
    module_id = model.add_module("cycle_life")
    with pytest.raises(ValueError, match="QC 모듈이 아닙니다"):
        model.plan_qc_fast_charge(module_id, [3.0])
