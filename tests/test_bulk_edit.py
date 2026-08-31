from __future__ import annotations

import pytest

from pne_scheduler.edit import apply_bulk_edit, parse_param_value, parse_set_args
from pne_scheduler.ir import CellProfile
from pne_scheduler.ir.project import ModuleNode, ScheduleProject


def _sample_project() -> ScheduleProject:
    return ScheduleProject(
        name="test",
        cell_profile=CellProfile(nominal_capacity_mAh=80.0, v_max=4.2, v_min=2.5),
        modules=[
            ModuleNode("fm1", "formation", {"charge_c_rate": 0.1, "cycle_count": 2}),
            ModuleNode("cyc1", "cycle_life", {"charge_c_rate": 1.0, "loop_count": 10}),
            ModuleNode("cyc2", "cycle_life", {"charge_c_rate": 1.0, "loop_count": 20}),
            ModuleNode("rpt1", "rpt", {"reference_c_rate": 1 / 3}),
        ],
    )


def test_parse_c_third() -> None:
    assert parse_param_value("C/3") == pytest.approx(1 / 3)


def test_parse_set_args() -> None:
    patch = parse_set_args(["charge_c_rate=0.5", "loop_count=300"])
    assert patch["charge_c_rate"] == "0.5"
    assert patch["loop_count"] == "300"


def test_bulk_edit_all_modules() -> None:
    project = _sample_project()
    result = apply_bulk_edit(
        project,
        {"rest_s": 600},
        all_modules=True,
    )
    assert result.updated_count >= 2
    assert project.modules[0].params["rest_s"] == 600


def test_bulk_edit_selected_ids() -> None:
    project = _sample_project()
    result = apply_bulk_edit(
        project,
        {"charge_c_rate": "0.5", "discharge_c_rate": "0.5"},
        module_ids=["cyc1", "cyc2"],
    )
    assert result.updated_count == 2
    assert project.modules[1].params["charge_c_rate"] == pytest.approx(0.5)
    assert project.modules[0].params["charge_c_rate"] == pytest.approx(0.1)


def test_bulk_edit_by_module_type() -> None:
    project = _sample_project()
    result = apply_bulk_edit(
        project,
        {"loop_count": "500"},
        module_types=["cycle_life"],
    )
    assert result.updated_count == 2
    assert project.modules[1].params["loop_count"] == 500


def test_bulk_edit_skips_incompatible_keys() -> None:
    project = _sample_project()
    result = apply_bulk_edit(
        project,
        {"loop_count": "100", "reference_c_rate": "C/3"},
        all_modules=True,
    )
    assert result.updated_count == 2
    assert set(result.updated_module_ids) == {"cyc1", "cyc2"}
    assert "fm1" in result.skipped_module_ids
    assert project.modules[1].params["loop_count"] == 100
