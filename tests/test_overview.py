from __future__ import annotations

from pathlib import Path

from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.ir.project import ScheduleProject
from pne_scheduler.protocol.overview import compose_overview, format_overview
from pne_scheduler.ui.flow_model import FlowProjectModel

ROOT = Path(__file__).resolve().parents[1]


def test_qpeed_project_overview_names_3318_and_15c() -> None:
    project = ScheduleProject.load(ROOT / "example" / "qpeed.schproj")
    overview = compose_overview(project)
    text = format_overview(overview)

    assert overview.flow == ("qpeed_1",)
    assert "3.318 V" in text
    assert "1.5C" in text
    assert "Repeat ×12" in text
    assert "What this schedule does" in text
    assert "not equipment-ready" in text


def test_flow_model_overview_follows_recipe_edits() -> None:
    model = FlowProjectModel(
        ScheduleProject(
            name="edited",
            cell_profile=CellProfile(nominal_capacity_mAh=80.0, v_max=4.2, v_min=2.5),
        )
    )
    node = model.add_module("qpeed")
    recipe = model.instantiate(node.id).recipe()
    recipe.setup[0].end_time_s = 30.0
    recipe.preset = "custom"
    model.set_recipe(node.id, recipe)

    text = format_overview(compose_overview(model.project))
    assert "REST 30 s" in text
    assert "Custom recipe" in text
