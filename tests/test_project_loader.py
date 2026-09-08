from __future__ import annotations

import json
from pathlib import Path

import pytest

from pne_scheduler.ir.loader import (
    ProjectLoadError,
    load_project_lenient,
    repair_project_dict,
)


def test_a_broken_project_still_opens_so_it_can_be_fixed() -> None:
    load = repair_project_dict(
        {
            "cell_profile": {"nominal_capacity_mAh": 0, "v_max": 2.0, "v_min": 2.5},
            "modules": [
                {"id": "a", "module_type": "formation"},
                {"id": "a", "module_type": "rest"},
                {"module_type": ""},
            ],
            "connections": [{"source_id": "a", "target_id": "missing"}],
        }
    )

    assert load.project.cell_profile.nominal_capacity_mAh > 0
    assert load.project.cell_profile.v_max > load.project.cell_profile.v_min
    assert [node.id for node in load.project.modules] == ["a", "a_2"]
    # The dangling connection is dropped and the surviving modules are chained
    # in run order.
    assert [(edge.source_id, edge.target_id) for edge in load.project.connections] == [
        ("a", "a_2")
    ]
    assert load.needs_attention


def test_unknown_module_types_are_kept_for_the_validator() -> None:
    load = repair_project_dict(
        {
            "name": "unknown",
            "cell_profile": {"nominal_capacity_mAh": 24.0, "v_max": 4.2, "v_min": 2.5},
            "modules": [{"id": "x", "module_type": "not_a_module"}],
        }
    )

    assert [node.module_type for node in load.project.modules] == ["not_a_module"]


def test_graph_wiring_is_folded_into_run_order() -> None:
    load = repair_project_dict(
        {
            "name": "wired",
            "cell_profile": {"nominal_capacity_mAh": 24.0, "v_max": 4.2, "v_min": 2.5},
            "modules": [
                {"id": "second", "module_type": "rest"},
                {"id": "first", "module_type": "formation"},
            ],
            "connections": [{"source_id": "first", "target_id": "second"}],
        }
    )

    assert [node.id for node in load.project.modules] == ["first", "second"]


def test_malformed_json_is_reported_not_silently_replaced(tmp_path: Path) -> None:
    path = tmp_path / "broken.schproj"
    path.write_text("{ not json", encoding="utf-8")

    with pytest.raises(ProjectLoadError):
        load_project_lenient(path)


def test_missing_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(ProjectLoadError):
        load_project_lenient(tmp_path / "nope.schproj")


def test_saving_a_repaired_project_produces_valid_json(tmp_path: Path) -> None:
    load = repair_project_dict({"cell_profile": {}})
    path = tmp_path / "repaired.schproj"
    load.project.save(path)

    assert json.loads(path.read_text(encoding="utf-8"))["name"] == "이름 없는 프로젝트"
