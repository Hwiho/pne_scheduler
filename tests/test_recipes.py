from __future__ import annotations

import pytest

from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.ir.project import ScheduleProject
from pne_scheduler.modules.base import expand_module, list_module_types
from pne_scheduler.modules.charge import ChargeModule
from pne_scheduler.modules.cycle_life import CycleLifeModule
from pne_scheduler.modules.discharge import DischargeModule
from pne_scheduler.modules.formation import FormationModule
from pne_scheduler.modules.hppc import HppcModule
from pne_scheduler.modules.presets import build_preset
from pne_scheduler.modules.qpeed import QpeedModule
from pne_scheduler.modules.recipe import RecipeUnit
from pne_scheduler.modules.sequence import SequenceModule
from pne_scheduler.ui.flow_model import FlowProjectModel


CELL = CellProfile(nominal_capacity_mAh=80.0, v_max=4.2, v_min=2.5)


def test_palette_includes_recipe_primitives() -> None:
    types = list_module_types()
    assert types[:4] == ("charge", "discharge", "rest", "sequence")
    assert "qpeed" in types
    assert "hppc" in types


def test_qpeed_full_3318_topology() -> None:
    module = QpeedModule.from_params({})
    recipe = module.recipe()
    steps = module.expand(CELL)

    assert recipe.preset == "qpeed.full_3318"
    assert recipe.repeat_count == 12
    assert any(unit.end_voltage_v == pytest.approx(3.318) for unit in recipe.setup)
    pulse = next(unit for unit in recipe.repeat if unit.label == "high-C to full")
    assert pulse.c_rate == pytest.approx(1.5)
    assert pulse.end_voltage_v == pytest.approx(4.2)

    soc_set = [
        step
        for step in steps
        if step.end_voltage_v == pytest.approx(3.318) and step.step_type == "charge"
    ]
    assert soc_set
    assert all(step.c_rate == pytest.approx(1.0) for step in soc_set)

    loops = [step for step in steps if step.step_type == "loop"]
    assert loops
    assert loops[0].loop_count == 12


def test_qpeed_edit_unit_changes_expand() -> None:
    module = QpeedModule.from_params({})
    recipe = module.recipe()
    target = next(unit for unit in recipe.setup if unit.end_voltage_v == pytest.approx(3.318))
    target.c_rate = 0.2
    from pne_scheduler.modules.composable import apply_recipe

    apply_recipe(module, recipe)
    steps = module.expand(CELL)
    edited = [
        step
        for step in steps
        if step.step_type == "charge" and step.end_voltage_v == pytest.approx(3.318)
    ]
    assert edited
    assert edited[0].c_rate == pytest.approx(0.2)


def test_qpeed_soc_setting_variant_maps_to_preset() -> None:
    module = QpeedModule.from_params({"variant": "soc_setting"})
    recipe = module.recipe()
    assert recipe.preset == "qpeed.soc_setting"
    assert recipe.repeat == []
    last_charge = next(
        unit for unit in reversed(recipe.setup) if unit.kind == "charge"
    )
    assert last_charge.end_voltage_v == pytest.approx(4.2)
    assert all(
        unit.end_voltage_v != pytest.approx(3.318)
        for unit in recipe.setup
        if unit.end_voltage_v is not None
    )


def test_qpeed_soc_fraction_is_generator_template() -> None:
    recipe = build_preset("qpeed.soc_fraction")
    assert recipe.preset == "qpeed.soc_fraction"
    assert any(unit.end_capacity_fraction is not None for unit in recipe.setup)
    assert any(unit.end_time_s == pytest.approx(10.0) for unit in recipe.setup)


def test_hppc_full_range_is_voltage_limit_not_soc_ladder() -> None:
    module = HppcModule.from_params({})
    recipe = module.recipe()
    assert recipe.preset == "hppc.full_range"
    assert not any(unit.end_capacity_fraction for unit in recipe.setup + recipe.repeat)
    steps = module.expand(CELL)
    voltages = {step.end_voltage_v for step in steps if step.end_voltage_v is not None}
    assert 2.5 in voltages
    assert 4.2 in voltages


def test_charge_and_discharge_modules() -> None:
    charge_steps = ChargeModule(c_rate=0.5, mode="CCCV").expand(CELL)
    discharge_steps = DischargeModule(c_rate=1.0).expand(CELL)
    assert charge_steps[0].step_type == "charge"
    assert charge_steps[0].c_rate == pytest.approx(0.5)
    assert charge_steps[0].voltage_v == pytest.approx(4.2)
    assert discharge_steps[0].step_type == "discharge"
    assert discharge_steps[0].end_voltage_v == pytest.approx(2.5)


def test_formation_recipe_keeps_01c() -> None:
    module = FormationModule.from_params({})
    charges = [step for step in module.expand(CELL) if step.step_type == "charge"]
    assert charges
    assert charges[0].c_rate == pytest.approx(0.1)
    assert module.cycle_count == 3


def test_cycle_life_recipe_uses_loop() -> None:
    module = CycleLifeModule.from_params({"loop_count": 10})
    steps = module.expand(CELL)
    loops = [step for step in steps if step.step_type == "loop"]
    assert loops[0].loop_count == 10
    assert steps[-1].step_type == "end"


def test_sequence_units_are_editable() -> None:
    module = SequenceModule.from_params({})
    recipe = module.recipe()
    recipe.setup = [
        RecipeUnit(kind="rest", end_time_s=30.0, label="pause"),
        RecipeUnit(kind="charge", mode="CC", c_rate=1.0, end_voltage_v=4.0),
    ]
    from pne_scheduler.modules.composable import apply_recipe

    apply_recipe(module, recipe)
    steps = module.expand(CELL)
    assert [step.step_type for step in steps] == ["rest", "charge"]
    assert steps[1].end_voltage_v == pytest.approx(4.0)


def test_flow_model_apply_preset_and_recipe_edit() -> None:
    model = FlowProjectModel(
        ScheduleProject(name="qpeed", cell_profile=CELL)
    )
    node = model.add_module("qpeed")
    assert node.params["preset"] == "qpeed.full_3318"
    assert any(
        unit.get("end_voltage_v") == pytest.approx(3.318)
        for unit in node.params["setup"]
    )

    model.apply_preset(node.id, "qpeed.soc_setting")
    assert model.get_module(node.id).params["preset"] == "qpeed.soc_setting"

    recipe = model.instantiate(node.id).recipe()
    recipe.setup.append(RecipeUnit(kind="rest", end_time_s=5.0, label="extra"))
    recipe.preset = "custom"
    model.set_recipe(node.id, recipe)
    saved = model.get_module(node.id).params
    assert saved["preset"] == "custom"
    assert saved["setup"][-1]["end_time_s"] == pytest.approx(5.0)

    lines = model.card_lines(node.id)
    assert any("extra" in line or "REST" in line for line in lines)


def test_old_formation_project_still_expands() -> None:
    from pne_scheduler.ir.project import ModuleNode

    project = ScheduleProject(
        name="legacy",
        cell_profile=CELL,
        modules=[
            ModuleNode("fm1", "formation", {"charge_c_rate": 0.1, "cycle_count": 1}),
        ],
    )
    steps = expand_module(project.modules[0], CELL)
    charges = [step for step in steps if step.step_type == "charge"]
    assert charges[0].c_rate == pytest.approx(0.1)
