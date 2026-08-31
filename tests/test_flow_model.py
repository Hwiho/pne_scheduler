from __future__ import annotations

from pathlib import Path

import pytest

from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.ir.project import ModuleConnection, ScheduleProject
from pne_scheduler.ui.flow_model import FlowProjectModel


def _model() -> FlowProjectModel:
    return FlowProjectModel(
        ScheduleProject(
            name="flow test",
            cell_profile=CellProfile(
                nominal_capacity_mAh=80.0,
                v_max=4.2,
                v_min=2.5,
                max_current_mA=800.0,
            ),
        )
    )


def test_flow_model_add_connect_preview_and_round_trip(tmp_path: Path) -> None:
    model = _model()
    formation = model.add_module(
        "formation",
        params={"cycle_count": 1, "rest_s": 60.0},
    )
    rest = model.add_module("rest", params={"duration_s": 120.0})
    model.connect(formation.id, rest.id)

    validation = model.validate()
    steps, warnings = model.preview_steps()
    duration = model.estimate_duration()
    project_path = tmp_path / "flow.schproj"
    model.project.save(project_path)
    loaded = ScheduleProject.load(project_path)

    assert validation.is_valid
    assert validation.warnings == ()
    assert len(steps) == 5
    assert warnings == ()
    assert duration.total.estimated_seconds == pytest.approx(72_240.0)
    assert [item.module_id for item in duration.modules] == [
        formation.id,
        rest.id,
    ]
    assert loaded.to_dict() == model.project.to_dict()


def test_flow_model_rejects_cycles_and_branching() -> None:
    model = _model()
    first = model.add_module("rest")
    second = model.add_module("rest")
    third = model.add_module("rest")
    model.connect(first.id, second.id)

    with pytest.raises(ValueError, match="more than one output"):
        model.connect(first.id, third.id)
    with pytest.raises(ValueError, match="cycle"):
        model.connect(second.id, first.id)


def test_flow_model_auto_connect_and_remove() -> None:
    model = _model()
    ids = [model.add_module("rest").id for _ in range(3)]

    model.auto_connect()
    model.remove_module(ids[1])

    assert model.validate().is_valid
    assert model.project.connections == []
    assert [node.id for node in model.project.modules] == [ids[0], ids[2]]


def test_flow_model_rejects_unknown_parameter() -> None:
    model = _model()
    node = model.add_module("rest")

    with pytest.raises(ValueError, match="Unknown parameter"):
        model.update_params(node.id, {"duraton_s": 10})


def test_project_expansion_rejects_dangling_connections() -> None:
    model = _model()
    node = model.add_module("rest")
    model.project.connections.append(ModuleConnection(node.id, "missing"))

    with pytest.raises(ValueError, match="unknown module"):
        model.project.expand_steps()
