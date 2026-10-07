"""Composable module contents and explicit sequence-child customization."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from pne_scheduler.api.app import create_app
from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.ir.project import ModuleNode, ScheduleProject
from pne_scheduler.library import MethodLibrary
from pne_scheduler.protocol.module_content import derive_module_content
from pne_scheduler.ui.document import ProjectDocument
from pne_scheduler.ui.workspace_model import WorkspaceModel


CELL = CellProfile(80, 4.2, 2.5)


def test_soc_adjustment_card_shows_removed_capacity_not_target_soc() -> None:
    project = ScheduleProject(
        "SOC card", CELL,
        modules=[ModuleNode("hppc", "hppc", {
            "variant": "discharge_soc_pulse", "soc_fractions": [0.8, 0.5, 0.2],
        })],
    )
    content = derive_module_content(project, "hppc")
    assert "용량 종료: 기준용량의 20% (16 mAh)" in content.steps[0]["summary"]
    assert "SOC 20%" not in content.steps[0]["summary"]


def _sequence(*children: ModuleNode, repeat_count: int = 1) -> ModuleNode:
    return ModuleNode(
        "group",
        "sequence",
        {
            "name": "조합 시험",
            "children": [child.to_dict() for child in children],
            "repeat_count": repeat_count,
        },
    )


def _model(tmp_path: Path, *children: ModuleNode, repeat_count: int = 1) -> WorkspaceModel:
    project = ScheduleProject(
        "module content",
        CELL,
        modules=[_sequence(*children, repeat_count=repeat_count)],
    )
    return WorkspaceModel(
        ProjectDocument(project, autosave_dir=tmp_path / "recovery")
    )


def test_derive_is_nonmutating_and_retains_sequence_children() -> None:
    project = ScheduleProject(
        "derive",
        CELL,
        modules=[
            _sequence(
                ModuleNode("formation-child", "formation", {"cycle_count": 1}),
                ModuleNode("cycle-child", "cycle_life", {"loop_count": 2}),
                repeat_count=3,
            )
        ],
    )
    before = deepcopy(project.to_dict())

    content = derive_module_content(project, "group")

    assert project.to_dict() == before
    assert [child.node.id for child in content.children] == [
        "formation-child",
        "cycle-child",
    ]
    assert len(content.children) == 2  # outer repetition is not flattened
    assert content.steps[-1]["stepType"] == "loop"
    assert content.steps[-1]["summary"].endswith("3회 반복")
    assert all(step["stepType"] != "end" for step in content.steps)


@pytest.mark.parametrize(
    ("module_type", "params"),
    [
        ("formation", {"cycle_count": 2}),
        ("cycle_life", {"loop_count": 4}),
        ("qpeed", {"variant": "soc_setting"}),
        ("qpeed", {"variant": "full"}),
    ],
)
def test_detaching_one_preset_child_preserves_composed_steps_exactly(
    tmp_path: Path, module_type: str, params: dict
) -> None:
    model = _model(tmp_path, ModuleNode("target", module_type, params), repeat_count=2)
    before = [step.to_dict() for step in model.project.expand_steps()]

    model.detach_group_child("group", 0)

    assert [step.to_dict() for step in model.project.expand_steps()] == before
    child = model.project.modules[0].params["children"][0]
    assert child["id"] == "target"
    assert child["module_type"] == "custom_steps"
    assert child["params"]["source_module_type"] == module_type
    assert all("extra" in step for step in child["params"]["steps"])


def test_group_and_inner_loops_rebase_after_the_group_moves(tmp_path: Path) -> None:
    model = _model(
        tmp_path,
        ModuleNode("cycle-child", "cycle_life", {"loop_count": 2}),
        repeat_count=3,
    )
    model.project.modules.insert(
        0,
        ModuleNode(
            "before",
            "primitive",
            {"kind": "rest", "duration_s": 10, "repeat_count": 2},
        ),
    )
    before_move = [
        (step.loop_goto_step, step.loop_count)
        for step in model.project.expand_steps()
        if step.step_type == "loop"
    ]
    assert before_move == [(1, 2), (4, 2), (3, 3)]

    model.move("group", -1)

    after_move = [
        (step.loop_goto_step, step.loop_count)
        for step in model.project.expand_steps()
        if step.step_type == "loop"
    ]
    assert after_move == [(2, 2), (1, 3), (8, 2)]
    assert sum(step.step_type == "end" for step in model.project.expand_steps()) == 1


def test_child_edit_is_isolated_and_each_operation_undoes_atomically(
    tmp_path: Path,
) -> None:
    first = ModuleNode("first", "rest", {"duration_s": 60})
    second = ModuleNode("second", "rest", {"duration_s": 60})
    model = _model(tmp_path, first, second)
    original = deepcopy(model.project.to_dict())

    model.detach_group_child("group", 0)
    detached = deepcopy(model.project.to_dict())
    model.set_group_child_step_field("group", 0, 0, "end_time_s", "30분")

    children = model.project.modules[0].params["children"]
    assert children[0]["params"]["steps"][0]["end_time_s"] == 1800
    assert children[1] == second.to_dict()
    assert model.document.undo() is not None
    assert model.project.to_dict() == detached
    assert model.document.undo() is not None
    assert model.project.to_dict() == original


@pytest.mark.parametrize(("operation", "index"), [("detach", -1), ("detach", 2), ("edit", -1), ("edit", 2)])
def test_invalid_child_or_step_bounds_are_rejected_without_mutation(
    tmp_path: Path, operation: str, index: int
) -> None:
    model = _model(tmp_path, ModuleNode("only", "rest", {"duration_s": 60}))
    if operation == "edit":
        model.detach_group_child("group", 0)
    before = deepcopy(model.project.to_dict())

    with pytest.raises(ValueError, match="범위|위치"):
        if operation == "detach":
            model.detach_group_child("group", index)
        else:
            model.set_group_child_step_field(
                "group", 0, index, "end_time_s", "10분"
            )

    assert model.project.to_dict() == before


def test_http_contract_forms_fields_summaries_and_no_end_duplication(
    tmp_path: Path,
) -> None:
    client = create_app(
        tmp_path / "library", tmp_path / "storage.sqlite3"
    ).test_client()
    project = ScheduleProject(
        "api",
        CELL,
        modules=[
            _sequence(
                ModuleNode("cycle", "cycle_life", {"loop_count": 2}),
                ModuleNode("rest", "rest", {"duration_s": 60}),
                repeat_count=2,
            )
        ],
    ).to_dict()

    root_response = client.post(
        "/api/module-content", json={"project": project, "moduleId": "group"}
    )
    root = root_response.get_json()
    assert root_response.status_code == 200
    assert root["childIndex"] is None
    assert root["children"][0]["moduleId"] == "cycle"
    assert root["children"][0]["form"]["sections"]
    assert {step["mode"] for step in root["steps"] if step["stepType"] in {"cycle", "loop"}} == {"CYCLE", "LOOP"}
    assert not [step for step in root["steps"] if step["stepType"] == "end"]

    detached = client.post(
        "/api/edit/detachGroupChild",
        json={"project": project, "args": {"moduleId": "group", "index": 1}},
    ).get_json()
    edited_response = client.post(
        "/api/edit/setGroupChildStepField",
        json={
            "project": detached["project"],
            "args": {
                "moduleId": "group",
                "childIndex": 1,
                "index": 0,
                "key": "end_time_s",
                "text": "30분",
            },
        },
    )
    assert edited_response.status_code == 200
    edited = edited_response.get_json()
    child_response = client.post(
        "/api/module-content",
        json={
            "project": edited["project"],
            "moduleId": "group",
            "childIndex": 1,
        },
    )
    child = child_response.get_json()
    assert child_response.status_code == 200
    assert child["customized"] is True
    assert child["stepCount"] == 1
    duration = next(
        field for field in child["steps"][0]["fields"] if field["key"] == "end_time_s"
    )
    assert duration["detail"] == "30분"
    assert "30분" in child["steps"][0]["summary"]


def test_http_rejects_child_edit_before_detach_and_bad_indexes(tmp_path: Path) -> None:
    client = create_app(
        tmp_path / "library", tmp_path / "storage.sqlite3"
    ).test_client()
    project = ScheduleProject(
        "api",
        CELL,
        modules=[_sequence(ModuleNode("rest", "rest", {"duration_s": 60}))],
    ).to_dict()

    edit = client.post(
        "/api/edit/setGroupChildStepField",
        json={
            "project": project,
            "args": {
                "moduleId": "group",
                "childIndex": 0,
                "index": 0,
                "key": "end_time_s",
                "text": "30분",
            },
        },
    )
    bad_content = client.post(
        "/api/module-content",
        json={"project": project, "moduleId": "group", "childIndex": 5},
    )

    assert edit.status_code == 400
    assert "먼저 분리" in edit.get_json()["error"]
    assert bad_content.status_code == 400
    assert "위치" in bad_content.get_json()["error"]


@pytest.mark.parametrize(
    ("module_type", "params"),
    [
        ("formation", {"cycle_count": 2}),
        ("cycle_life", {"loop_count": 4}),
        ("qpeed", {"variant": "full"}),
    ],
)
def test_single_preset_library_roundtrip_keeps_the_actual_steps(
    tmp_path: Path, module_type: str, params: dict
) -> None:
    library = MethodLibrary(tmp_path / "library")
    source = WorkspaceModel(
        ProjectDocument(
            ScheduleProject("source", CELL), autosave_dir=tmp_path / "source"
        ),
        library=library,
    )
    source.add_module(module_type, params)
    preset_id = source.project.modules[0].id
    expected = [step.to_dict() for step in source.project.expand_steps()]
    source.add_module("rest", {"duration_s": 999})
    original = deepcopy(source.project.to_dict())
    entry = source.save_method("내 프리셋", module_ids=[preset_id])
    assert source.project.to_dict() == original
    assert entry.module_count == 1
    assert entry.path.exists()

    target = WorkspaceModel(
        ProjectDocument(
            ScheduleProject("target", CELL), autosave_dir=tmp_path / "target"
        ),
        library=library,
    )
    target.load_method(target.plan_method_load(entry))
    assert [step.to_dict() for step in target.project.expand_steps()] == expected
    content = derive_module_content(target.project, target.project.modules[0].id)
    assert content.steps
    assert all(step["stepType"] != "end" for step in content.steps)
    assert target.document.undo() is not None
    assert not target.project.modules


def test_customized_repeating_group_library_roundtrip_keeps_child_edit_and_loops(
    tmp_path: Path,
) -> None:
    library = MethodLibrary(tmp_path / "library")
    source = _model(
        tmp_path / "source",
        ModuleNode("cycle", "cycle_life", {"loop_count": 3}),
        ModuleNode("rest", "primitive", {"kind": "rest", "duration_s": 60}),
        repeat_count=2,
    )
    source = WorkspaceModel(source.document, library=library)
    source.detach_group_child("group", 0)
    source.set_group_child_step_field("group", 0, 1, "c_rate", "0.75C")
    expected = [step.to_dict() for step in source.project.expand_steps()]
    entry = source.save_method("반복 시험", module_ids=["group"])
    target = WorkspaceModel(
        ProjectDocument(
            ScheduleProject("target", CELL), autosave_dir=tmp_path / "target"
        ),
        library=library,
    )
    target.load_method(target.plan_method_load(entry))
    assert [step.to_dict() for step in target.project.expand_steps()] == expected
    assert sum(step.step_type == "end" for step in target.project.expand_steps()) == 1
    root = derive_module_content(target.project, target.project.modules[0].id)
    assert len(root.children) == 2
    child = derive_module_content(target.project, target.project.modules[0].id, 0)
    assert child.customized
    assert "0.75C" in child.steps[1]["summary"]
