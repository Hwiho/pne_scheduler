from pathlib import Path

import pytest

from pne_scheduler.engine.duration import estimate_steps_duration
from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.ir.project import ModuleNode, ScheduleProject
from pne_scheduler.ui.document import ProjectDocument
from pne_scheduler.ui.workspace_model import WorkspaceModel
from pne_scheduler.validate.preflight import validate_project


CELL = CellProfile(80, 4.2, 2.5)


def rest(identifier, seconds, count=1):
    return ModuleNode(identifier, "primitive", {"kind": "rest", "duration_s": seconds, "repeat_count": count})


def test_group_nested_loops_rebase_when_moved_and_time_includes_inner_repeat():
    group = ModuleNode("group", "sequence", {"name": "대기 묶음", "children": [rest("a", 10, 2).to_dict(), rest("b", 5).to_dict()], "repeat_count": 3})
    project = ScheduleProject("probe", CELL, modules=[rest("before", 7), group])
    steps = project.expand_steps()
    assert [(s.loop_goto_step, s.loop_count) for s in steps if s.step_type == "loop"] == [(2, 2), (2, 3)]
    assert sum(s.step_type == "end" for s in steps) == 1
    assert estimate_steps_duration(steps).estimated_seconds == 82
    project.modules.reverse()
    steps = project.expand_steps()
    assert [(s.loop_goto_step, s.loop_count) for s in steps if s.step_type == "loop"] == [(1, 2), (1, 3)]
    assert estimate_steps_duration(steps).estimated_seconds == 82


def test_group_edit_undo_ungroup_and_duplicate_do_not_alias(tmp_path: Path):
    model = WorkspaceModel(ProjectDocument.new(autosave_dir=tmp_path / "recovery"))
    a = model.add_module("primitive", {"kind": "rest", "duration_s": 10})
    b = model.add_module("rest", {"duration_s": 5})
    group = model.group_modules([b, a], "내 블록", 3)
    assert len(model.project.modules) == 1
    model.set_group_child_param(group, 0, "duration_s", "20초")
    clone = model.duplicate_module(group)
    model.project.modules[1].params["children"][0]["params"]["duration_s"] = 99
    assert model.project.modules[0].params["children"][0]["params"]["duration_s"] == 20
    model.remove_module(clone)
    before = estimate_steps_duration(model.project.expand_steps()).estimated_seconds
    model.ungroup_module(group)
    assert len(model.project.modules) == 6
    assert len({node.id for node in model.project.modules}) == 6
    assert estimate_steps_duration(model.project.expand_steps()).estimated_seconds == before
    model.document.undo()
    assert model.project.modules[0].module_type == "sequence"


def test_nonconsecutive_and_nested_groups_rejected_without_mutation(tmp_path):
    model = WorkspaceModel(ProjectDocument.new(autosave_dir=tmp_path / "recovery"))
    ids = [model.add_module("rest") for _ in range(3)]
    with pytest.raises(ValueError, match="연속"):
        model.group_modules([ids[0], ids[2]], "bad")
    assert len(model.project.modules) == 3
    group = model.group_modules(ids[:2], "first")
    with pytest.raises(ValueError, match="중첩"):
        model.group_modules([group, ids[2]], "second")
    with pytest.raises(ValueError, match="정수"):
        model.group_modules([group, ids[2]], "bad", 1.5)


def test_group_retains_child_trust_and_production_block():
    children = [ModuleNode("rpt", "rpt", {}).to_dict(), rest("rest", 5).to_dict()]
    project = ScheduleProject("probe", CELL, modules=[ModuleNode("g", "sequence", {"children": children})])
    issues = validate_project(project).issues
    assert any(issue.code == "MODULE_TRUST" and "RPT" in issue.message for issue in issues)
    assert validate_project(project, purpose="production").errors


def test_save_only_group_and_load_preserves_parameters(tmp_path):
    from pne_scheduler.library import MethodLibrary
    model = WorkspaceModel(ProjectDocument.new(autosave_dir=tmp_path / "recovery"), library=MethodLibrary(tmp_path / "library"))
    ids = [model.add_module("rest", {"duration_s": n}) for n in (3, 5, 7)]
    group = model.group_modules(ids[:2], "recipe", 2)
    entry = model.save_method("대기 레시피", module_ids=[group])
    assert entry.module_count == 1
    assert entry.modules[0]["params"]["repeat_count"] == 2
    loaded = model.load_method(model.plan_method_load(entry))
    assert loaded[0] != group
    assert model.project.modules[-1].params["children"][0]["params"]["duration_s"] == 3


def test_http_group_child_edit_and_library_append_are_reachable(tmp_path):
    from pne_scheduler.api.app import create_app
    client = create_app(tmp_path / "library", tmp_path / "storage.sqlite3").test_client()
    project = ScheduleProject("api", CELL, modules=[rest("a", 10), rest("b", 5)]).to_dict()
    result = client.post("/api/edit/groupModules", json={"project": project, "args": {"moduleIds": ["a", "b"], "name": "HTTP block", "repeatCount": 2}})
    assert result.status_code == 200
    body = result.get_json()
    group = body["views"]["selectedModule"]
    assert body["views"]["groupChildren"][0]["form"]["moduleType"] == "primitive"
    edited = client.post("/api/edit/setGroupChildParam", json={"project": body["project"], "args": {"moduleId": group, "index": 0, "key": "duration_s", "text": "30초"}}).get_json()
    saved = client.post("/api/library", json={"project": edited["project"], "name": "HTTP recipe", "moduleIds": [group]})
    assert saved.status_code == 200
    identifier = saved.get_json()["method"]["methodId"]
    appended = client.post("/api/edit/loadMethod", json={"project": edited["project"], "args": {"methodId": identifier}})
    assert appended.status_code == 200
    assert len(appended.get_json()["project"]["modules"]) == 2
    assert appended.get_json()["project"]["modules"][1]["params"]["children"][0]["params"]["duration_s"] == 30


def test_review_group_matrix_files_reparse_with_correct_loop_targets(tmp_path):
    from pne_scheduler.api.app import create_app
    from pne_scheduler.ir.equipment_profile import EquipmentProfile
    from pne_scheduler.io.reader import read_sch
    from pne_scheduler.io.sch_binary import read_loop_info, read_sch_binary
    client = create_app(tmp_path / "library", tmp_path / "storage.sqlite3").test_client()
    group = ModuleNode("group", "sequence", {"name": "cycle and rest", "repeat_count": 3, "children": [ModuleNode("cycle", "cycle_life", {"loop_count": 2}).to_dict(), rest("rest", 5).to_dict()]})
    project = ScheduleProject("api matrix", CELL, modules=[group], equipment=EquipmentProfile.from_unit("PNE02"))
    args = {"phase": "cycle", "kind": "review_candidate", "rows": [{"cellId": "A01", "referenceCapacityMah": 80}, {"cellId": "A02", "referenceCapacityMah": 90}], "matrix": [{"chargeRate": 0.5, "dischargeRate": 1}, {"chargeRate": 1, "dischargeRate": 1.5}]}
    preview = client.post("/api/plan/cellBatch", json={"project": project.to_dict(), "args": args}).get_json()
    assert preview["ok"], preview["errors"]
    assert len(preview["rows"]) == 4
    exported = client.post("/api/export/cell-batch", json={"project": project.to_dict(), "args": args, "token": preview["token"], "outDir": str(tmp_path / "outputs")})
    assert exported.status_code == 200
    paths = [Path(path) for path in exported.get_json()["paths"] if path.endswith(".sch")]
    assert len(paths) == 4
    for path in paths:
        parsed = read_sch(path)
        assert parsed.step_count == 9
        assert parsed.step_size == 612
        binary = read_sch_binary(path)
        # The cycle marker is step 1; its inner loop resumes charging at step 2.
        # The outer group loop repeats the entire child sequence from step 1.
        assert [read_loop_info(step) for step in binary.steps if step.is_loop] == [(2, 2), (1, 3)]
    # A change to the reviewed rate combination invalidates the export token.
    args["matrix"][0]["chargeRate"] = 0.75
    stale = client.post("/api/export/cell-batch", json={"project": project.to_dict(), "args": args, "token": preview["token"], "outDir": str(tmp_path / "stale")})
    assert stale.status_code == 409
    assert not (tmp_path / "stale").exists()
