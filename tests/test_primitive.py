"""Single-step command blocks, and the LOOP shape the composer permits."""

from __future__ import annotations

from pathlib import Path

import pytest

from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.modules.catalog import get_module_spec, palette_module_types
from pne_scheduler.modules.primitive import PRIMITIVE_KINDS, PrimitiveModule
from pne_scheduler.ui.document import ProjectDocument
from pne_scheduler.ui.workspace_model import WorkspaceModel

CELL = CellProfile(nominal_capacity_mAh=80.0, v_min=2.5, v_max=4.2)


@pytest.mark.parametrize("kind", sorted(PRIMITIVE_KINDS))
def test_every_kind_makes_exactly_one_step(kind):
    steps = PrimitiveModule(kind=kind).expand(CELL)
    assert len(steps) == 1
    assert not PrimitiveModule(kind=kind).validate(CELL)


def test_a_cc_step_stops_at_the_edge_its_direction_is_heading_for():
    """One shared cutoff would mean the opposite thing for charge and discharge."""
    charge = PrimitiveModule(kind="cc_charge").expand(CELL)[0]
    discharge = PrimitiveModule(kind="cc_discharge").expand(CELL)[0]
    assert charge.end_voltage_v == 4.2
    assert discharge.end_voltage_v == 2.5


def test_each_kind_only_carries_the_fields_it_uses():
    rest = PrimitiveModule(kind="rest").expand(CELL)[0]
    assert rest.c_rate is None and rest.voltage_v is None
    assert rest.end_time_s == 600.0

    cccv = PrimitiveModule(kind="cccv_charge").expand(CELL)[0]
    assert cccv.mode == "CCCV"
    assert cccv.voltage_v == 4.2 and cccv.cv_cutoff_c_rate == 0.05
    assert cccv.end_voltage_v is None


def test_repeating_keeps_the_loop_and_its_target_in_one_fragment():
    """A LOOP pointing outside its module breaks when the procedure is reordered."""
    steps = PrimitiveModule(kind="rest", repeat_count=5).expand(CELL)
    assert [step.step_type for step in steps] == ["rest", "loop"]
    assert steps[0].ref_id == "body"
    assert steps[1].loop_target_ref == "body"
    assert steps[1].loop_count == 5
    assert steps[1].loop_goto_step is None


def test_one_repeat_adds_no_loop():
    assert len(PrimitiveModule(kind="rest", repeat_count=1).expand(CELL)) == 1


@pytest.mark.parametrize(
    "module, expected",
    [
        (PrimitiveModule(kind="nope"), "kind must be one of"),
        (PrimitiveModule(kind="rest", repeat_count=0), "repeat_count"),
        (PrimitiveModule(kind="cc_charge", c_rate=0.0), "c_rate"),
        (PrimitiveModule(kind="rest", duration_s=0.0), "duration_s"),
        (PrimitiveModule(kind="cccv_charge", voltage_v=9.0), "voltage_v"),
        (PrimitiveModule(kind="cc_discharge", discharge_end_voltage_v=9.0), "discharge_end"),
    ],
)
def test_invalid_settings_are_reported(module, expected):
    errors = module.validate(CELL)
    assert any(expected in error for error in errors)


def test_the_palette_offers_it_and_says_what_it_will_not_do():
    assert "primitive" in palette_module_types()
    spec = get_module_spec("primitive")
    joined = " ".join(spec.limitations)
    assert "END" in joined and "LOOP" in joined


# --- composed into a real schedule ------------------------------------------


def _model(tmp_path: Path) -> WorkspaceModel:
    return WorkspaceModel(ProjectDocument.new(autosave_dir=tmp_path / "recovery"))


def test_a_repeat_survives_being_moved_in_the_procedure(tmp_path):
    """The whole point of the fragment-local LOOP: reordering stays valid."""
    model = _model(tmp_path)
    model.add_module("primitive", {"kind": "rest", "repeat_count": 3})
    model.add_module("primitive", {"kind": "cc_discharge"})

    before = model.project.expand_steps()
    loop_before = next(s for s in before if s.step_type == "loop")

    model.move(model.project.modules[0].id, 1)
    after = model.project.expand_steps()
    loop_after = next(s for s in after if s.step_type == "loop")

    # The target moved with the block instead of pointing at a stale position.
    assert loop_after.loop_goto_step != loop_before.loop_goto_step
    assert loop_after.loop_count == 3
    assert [s for s in after if s.step_type == "end"], "the composer still owns END"


def test_primitives_mix_with_presets(tmp_path):
    model = _model(tmp_path)
    model.add_module("primitive", {"kind": "rest", "duration_s": 1800})
    model.add_module("cycle_life", {"loop_count": 5})
    model.add_module("primitive", {"kind": "ocv"})

    steps = model.project.expand_steps()
    ends = [i for i, s in enumerate(steps) if s.step_type == "end"]
    assert ends == [len(steps) - 1]
    assert not [row for row in model.validation_rows() if row.severity == "error"]
