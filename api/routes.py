"""The four operation groups, as plain functions.

Grouped by what an operation *is*, not by which screen calls it:

* **derive**   project → views. No mutation.
* **transform** project + args → project. The client keeps the history.
* **plan**     project + args → a proposal. Nothing changes until it is applied.
* **local**    the filesystem. The only group that cannot move off the lab PC.

Keeping *plan* separate from *transform* is not tidiness: it is what preserves the
preview-then-apply step, and with it the warnings that must be read before a value
is committed — that a campaign's DC-IR resistance window never reaches the
equipment file, or that a rescaled QC time is a constant-current approximation.
"""

from __future__ import annotations

from pathlib import Path
import hashlib
import json
from typing import Any, Callable

from ..edit.steps import StepEditError
from ..batch import export_cell_batch as write_cell_batch, plan_cell_batch
from ..exporting import ExportBlocked, export_preview, export_review_candidate
from ..import_session import ImportSession
from ..library import MethodLibrary, MethodVersion
from ..protocol.explain import explain_schedule, format_explanation
from ..protocol.module_content import derive_module_content
from ..spec.form import build_module_form
from ..ui.document import ProjectDocument
from ..ui.workspace_model import WorkspaceModel
from .errors import ApiError
from .serializers import diff_json, form_json, views_json


def _model(
    payload: dict[str, Any], *, library: MethodLibrary | None = None
) -> WorkspaceModel:
    project = payload.get("project")
    if not isinstance(project, dict):
        raise ApiError("요청에 project 가 없습니다.")
    try:
        return WorkspaceModel(ProjectDocument.detached(project), library=library)
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiError(f"프로젝트를 읽을 수 없습니다: {exc}") from exc


def _args(payload: dict[str, Any]) -> dict[str, Any]:
    args = payload.get("args", {})
    if not isinstance(args, dict):
        raise ApiError("args 는 객체여야 합니다.")
    return args


# --- derive -----------------------------------------------------------------


def open_project(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a browser-selected project, without reading arbitrary paths."""
    from ..ir.loader import repair_project_dict
    from ..ir.project import SCHPROJ_SCHEMA_V1, SCHPROJ_SCHEMA_V2

    raw = payload.get("data")
    if not isinstance(raw, dict) or "cell_profile" not in raw or "modules" not in raw:
        raise ApiError(".schproj 프로젝트 파일을 선택하세요. 셀 정보와 모듈 목록이 필요합니다.")
    if raw.get("schema", SCHPROJ_SCHEMA_V1) not in {SCHPROJ_SCHEMA_V1, SCHPROJ_SCHEMA_V2}:
        raise ApiError("지원하지 않는 프로젝트 버전입니다. v1/v2 .schproj 파일을 선택하세요.")
    try:
        loaded = repair_project_dict(raw)
        return {"ok": True, "project": loaded.project.to_dict(), "repairs": list(loaded.repairs),
                "migratedFrom": loaded.migrated_from}
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        raise ApiError(f"프로젝트를 읽을 수 없습니다: {exc}") from exc


def views(payload: dict[str, Any]) -> dict[str, Any]:
    model = _model(payload)
    return {
        "ok": True,
        "views": views_json(
            model, payload.get("selected"), include_steps=bool(payload.get("includeSteps"))
        ),
    }


def steps(payload: dict[str, Any]) -> dict[str, Any]:
    """The expanded step table on its own, for the tab that shows it."""
    model = _model(payload)
    return {"ok": True, "steps": list(model.display_step_rows())}


def module_content(payload: dict[str, Any]) -> dict[str, Any]:
    """A non-mutating expanded view of one module or retained group child."""
    model = _model(payload)
    module_id = payload.get("moduleId")
    if not isinstance(module_id, str) or not module_id:
        raise ApiError("moduleId 가 필요합니다.")
    raw_child_index = payload.get("childIndex")
    if raw_child_index is None:
        child_index = None
    elif isinstance(raw_child_index, bool) or not isinstance(raw_child_index, int):
        raise ApiError("childIndex 는 정수여야 합니다.")
    else:
        child_index = raw_child_index
    try:
        content = derive_module_content(model.project, module_id, child_index)
        children = []
        for child in content.children:
            form = build_module_form(
                child.node.module_type,
                child.node.params,
                cell=model.project.cell_profile,
                current_limit_mA=model.current_limit_mA,
            )
            children.append(
                {
                    "index": child.index,
                    "moduleId": child.node.id,
                    "moduleType": child.node.module_type,
                    "title": child.title,
                    "summary": child.summary,
                    "repeatCount": child.repeat_count,
                    "stepCount": child.step_count,
                    "form": form_json(form, child.node.id, 1),
                }
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiError(str(exc)) from exc
    return {
        "ok": True,
        "moduleId": content.module_id,
        "childIndex": content.child_index,
        "moduleType": content.node.module_type,
        "title": content.title,
        "customized": content.customized,
        "stepCount": len(content.steps),
        "steps": list(content.steps),
        "children": children,
    }


# --- transform --------------------------------------------------------------

def _qpeed_voltage_preview(model: WorkspaceModel, args: dict[str, Any]) -> dict[str, Any]:
    from ..protocol.qpeed_results import preview_soc_voltages
    nodes = [node for node in model.project.modules if node.id == args.get("moduleId")]
    if not nodes or nodes[0].module_type != "qpeed":
        raise ValueError("전압을 불러올 QPEED 모듈을 선택하세요.")
    mapping = args.get("mapping", {})
    if not isinstance(mapping, dict):
        raise ValueError("열 대응은 객체여야 합니다.")
    preview = preview_soc_voltages(args.get("text", ""), mapping=mapping,
                                  reference_capacity_mAh=(model.project.cell_profile.nominal_capacity_mAh
                                                          if args.get("useReferenceCapacity") is True else None))
    signed = {"project": model.project.to_dict(), "moduleId": args["moduleId"],
              "mapping": preview["mapping"], "digest": preview["digest"],
              "fileName": str(args.get("fileName", ""))[:512],
              "useReferenceCapacity": args.get("useReferenceCapacity") is True}
    preview["token"] = hashlib.sha256(json.dumps(signed, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return preview


def _apply_qpeed_voltage(model: WorkspaceModel, args: dict[str, Any]):
    preview = _qpeed_voltage_preview(model, args)
    if args.get("token") != preview["token"]:
        raise ApiError("미리보기 후 파일·열·프로젝트가 바뀌었습니다. 다시 미리보기 하세요.", status=409)
    chosen = next((row for row in preview["candidates"] if row["id"] == args.get("candidateId")), None)
    if chosen is None:
        raise ValueError("미리보기 목록의 전압 행을 직접 선택하세요.")
    source = json.dumps({"fileName": Path(str(args.get("fileName", "결과 파일"))).name[:512],
                         "textSha256": preview["digest"], **chosen}, ensure_ascii=False, sort_keys=True)
    return model.apply_qpeed_voltage(args["moduleId"], chosen["voltageV"], source, chosen["socPercent"])


def _run(
    model: WorkspaceModel,
    call: Callable[[], Any],
    *,
    selected: str | None = None,
    select_new: bool = False,
) -> dict[str, Any]:
    try:
        result = call()
    except (StepEditError, ValueError) as exc:
        raise ApiError(str(exc)) from exc
    if select_new and model.project.modules:
        ids = {node.id for node in model.project.modules}
        selected = result if isinstance(result, str) and result in ids else model.project.modules[-1].id
    return {
        "ok": True,
        "project": model.project.to_dict(),
        "label": model.document.last_label,
        "diff": diff_json(result if hasattr(result, "changes") else None),
        "views": views_json(model, selected),
    }


TRANSFORMS: dict[str, Callable[[WorkspaceModel, dict[str, Any]], Any]] = {
    "applyQpeedVoltage": _apply_qpeed_voltage,
    "setProjectName": lambda m, a: m.set_project_name(a["name"]),
    "setEquipmentUnit": lambda m, a: m.set_equipment_unit(a["unit"]),
    "setCellValue": lambda m, a: m.set_cell_value(a["key"], a["text"]),
    "addGoal": lambda m, a: m.add_goal(a["goalId"]),
    "addModule": lambda m, a: m.add_module(
        a["moduleType"], a.get("params"),
        index=int(a["index"]) if "index" in a else None,
    ),
    "removeModule": lambda m, a: m.remove_module(a["moduleId"]),
    "duplicateModule": lambda m, a: m.duplicate_module(a["moduleId"]),
    "groupModules": lambda m, a: m.group_modules(a["moduleIds"], a["name"], a.get("repeatCount", 1)),
    "loadMethod": lambda m, a: m.load_saved_method(a["methodId"]),
    "ungroupModule": lambda m, a: m.ungroup_module(a["moduleId"]),
    "setGroupChildParam": lambda m, a: m.set_group_child_param(a["moduleId"], int(a["index"]), a["key"], a["text"]),
    "detachGroupChild": lambda m, a: m.detach_group_child(
        a["moduleId"], int(a["index"])
    ),
    "setGroupChildStepField": lambda m, a: m.set_group_child_step_field(
        a["moduleId"], int(a["childIndex"]), int(a["index"]), a["key"], a["text"]
    ),
    "setParam": lambda m, a: m.set_param(a["moduleId"], a["key"], a["text"]),
    "applyToAllOfType": lambda m, a: m.apply_to_all_of_type(
        a["moduleType"], a["key"], a["text"]
    ),
    "move": lambda m, a: m.move(a["moduleId"], int(a["delta"])),
    "reorder": lambda m, a: m.reorder(list(a["order"])),
    "detach": lambda m, a: m.detach(a["moduleId"]),
    "insertStep": lambda m, a: m.insert_step(a["moduleId"], int(a["index"]), a["kind"]),
    "removeStep": lambda m, a: m.remove_step(a["moduleId"], int(a["index"])),
    "moveStep": lambda m, a: m.move_step(a["moduleId"], int(a["index"]), int(a["delta"])),
    "setStepField": lambda m, a: m.set_step_field(
        a["moduleId"], int(a["index"]), a["key"], a["text"]
    ),
    "setCycleCount": lambda m, a: m.set_cycle_count(a["moduleId"], int(a["count"])),
    "addCampaign": lambda m, a: m.add_campaign(m.plan_campaign(**campaign_options(a))),
    "applyQcFastCharge": lambda m, a: m.apply_qc_fast_charge(
        a["moduleId"], m.plan_qc_fast_charge(a["moduleId"], a["rates"])
    ),
    "recordCtsproReview": lambda m, a: m.record_ctspro_review(**a),
    "recordEquipmentApproval": lambda m, a: m.record_equipment_approval(**a),
    "clearApprovals": lambda m, a: m.clear_approvals(),
}


def transform(action: str, payload: dict[str, Any], *, library: MethodLibrary | None = None) -> dict[str, Any]:
    handler = TRANSFORMS.get(action)
    if handler is None:
        raise ApiError(f"알 수 없는 편집입니다: {action}", status=404)
    model = _model(payload, library=library)
    args = _args(payload)
    try:
        return _run(
            model,
            lambda: handler(model, args),
            selected=str(payload.get("selected") or ""),
            select_new=action in {"addGoal", "addModule", "addCampaign", "duplicateModule", "groupModules"},
        )
    except KeyError as exc:
        raise ApiError(f"필요한 값이 없습니다: {exc.args[0]}") from exc
    except TypeError as exc:
        raise ApiError(f"인자가 맞지 않습니다: {exc}") from exc


# --- plan -------------------------------------------------------------------


def _plan_body(plan: Any) -> dict[str, Any]:
    return {
        "ok": getattr(plan, "ok", True),
        "notes": list(getattr(plan, "notes", ())),
        "warnings": list(getattr(plan, "warnings", ())),
        "errors": list(getattr(plan, "errors", ())),
    }


def campaign_options(args: dict[str, Any]) -> dict[str, Any]:
    """Wire names → the builder's keywords, in one place.

    `plan/campaign` and `edit/addCampaign` must read a request identically, or a
    preview would describe something other than what applying it produces.
    """
    options = args.get("options", args)
    if not isinstance(options, dict):
        raise ApiError("options 는 객체여야 합니다.")
    return {
        "total_cycles": int(options.get("totalCycles", 0) or 0),
        "rpt_every": int(options.get("rptEvery", 50) or 50),
        "charge_c_rate": float(options.get("chargeCRate", 0.5) or 0.0),
        "discharge_c_rate": float(options.get("dischargeCRate", 0.5) or 0.0),
        "dcir_pulse_c_rates": [
            float(rate) for rate in options.get("dcirRates", [1.5])
        ],
        "reference_c_rate": float(options.get("referenceCRate", 1 / 3)),
        "start_soc": float(options.get("startSoc", 1.0)),
        "preparation_policy": str(options.get("preparationPolicy", "unconfirmed_entry")),
        "baseline_rpt": bool(options.get("baselineRpt", True)),
    }


def _campaign(model: WorkspaceModel, args: dict[str, Any]) -> dict[str, Any]:
    plan = model.plan_campaign(**campaign_options(args))
    return {
        **_plan_body(plan),
        "blocks": [
            {"moduleType": block.module_type, "title": block.title}
            for block in plan.blocks
        ],
        "totalCycles": plan.total_cycles,
        "rptCount": plan.rpt_count,
    }


def _qc(model: WorkspaceModel, args: dict[str, Any]) -> dict[str, Any]:
    plan = model.plan_qc_fast_charge(args["moduleId"], args["rates"])
    return {
        **_plan_body(plan),
        "rates": list(plan.rates_c),
        "voltages": list(plan.voltages_v),
        "times": list(plan.times_s),
    }


def _budget(model: WorkspaceModel, args: dict[str, Any]) -> dict[str, Any]:
    budget = model.cycles_within(
        float(args["days"]) * 86400.0,
        args.get("moduleId"),
        step=int(args.get("step", 1)),
    )
    return {
        **_plan_body(budget),
        "totalCycles": budget.total_cycles,
        "text": budget.as_text(),
    }


PLANS: dict[str, Callable[[WorkspaceModel, dict[str, Any]], dict[str, Any]]] = {
    "qpeedVoltage": _qpeed_voltage_preview,
    "cellBatch": lambda m, a: plan_cell_batch(
        m.project, phase=str(a.get("phase", "")), basis=str(a.get("basis", "manual_reference")),
        kind=str(a.get("kind", "")), rows=a.get("rows"), matrix=a.get("matrix"),
    ).to_dict(),
    "campaign": _campaign,
    "qcFastCharge": _qc,
    "cycleBudget": _budget,
    "param": lambda m, a: {
        "ok": True,
        "diff": diff_json(m.preview_param(a["moduleId"], a["key"], a["text"])),
    },
    "stepField": lambda m, a: {
        "ok": True,
        "diff": diff_json(
            m.preview_step_field(a["moduleId"], int(a["index"]), a["key"], a["text"])
        ),
    },
}


def plan(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    handler = PLANS.get(action)
    if handler is None:
        raise ApiError(f"알 수 없는 계획입니다: {action}", status=404)
    model = _model(payload)
    args = _args(payload)
    try:
        return handler(model, args)
    except KeyError as exc:
        raise ApiError(f"필요한 값이 없습니다: {exc.args[0]}") from exc
    except TypeError as exc:
        raise ApiError(f"인자가 맞지 않습니다: {exc}") from exc
    except (StepEditError, ValueError) as exc:
        raise ApiError(str(exc)) from exc


# --- local resources --------------------------------------------------------


def _method_json(entry: MethodVersion) -> dict[str, Any]:
    return {
        "methodId": entry.method_id,
        "version": entry.version,
        "name": entry.name,
        "label": entry.label,
        "description": entry.description,
        "equipmentUnit": entry.equipment_unit,
        "equipmentLayout": entry.equipment_layout,
        "moduleCount": entry.module_count,
        "savedAt": entry.saved_at,
    }


def library_list(store: MethodLibrary) -> dict[str, Any]:
    return {"ok": True, "methods": [_method_json(e) for e in store.methods()]}


def library_versions(store: MethodLibrary, method_id: str) -> dict[str, Any]:
    return {
        "ok": True,
        "versions": [_method_json(e) for e in store.versions(method_id)],
    }


def library_save(store: MethodLibrary, payload: dict[str, Any]) -> dict[str, Any]:
    model = _model(payload, library=store)
    name = str(payload.get("name", "")).strip()
    try:
        entry = model.save_method(name, description=payload.get("description", ""), module_ids=payload.get("moduleIds"))
    except ValueError as exc:
        raise ApiError(str(exc)) from exc
    return {"ok": True, "method": _method_json(entry)}


def library_load(store: MethodLibrary, payload: dict[str, Any]) -> dict[str, Any]:
    model = _model(payload, library=store)
    entry = store.latest(str(payload.get("methodId", "")))
    if entry is None:
        raise ApiError("저장된 방법을 찾을 수 없습니다.", status=404)
    version = payload.get("version")
    if version is not None:
        entry = next(
            (v for v in store.versions(entry.method_id) if v.version == int(version)),
            None,
        )
        if entry is None:
            raise ApiError("그 버전을 찾을 수 없습니다.", status=404)

    load_plan = model.plan_method_load(entry)
    if payload.get("preview"):
        return {
            "ok": load_plan.ok,
            "method": _method_json(entry),
            "notes": list(load_plan.notes),
            "warnings": list(load_plan.warnings),
            "errors": list(load_plan.errors),
        }
    try:
        model.load_method(load_plan, replace=bool(payload.get("replace")))
    except ValueError as exc:
        raise ApiError(str(exc)) from exc
    return {
        "ok": True,
        "project": model.project.to_dict(),
        "label": model.document.last_label,
        "warnings": list(load_plan.warnings),
        "views": views_json(model),
    }


EXPORTS: dict[str, Callable[[Any, Path], Any]] = {
    "preview": export_preview,
    "review_candidate": export_review_candidate,
}


def export(payload: dict[str, Any]) -> dict[str, Any]:
    """Write an output, but only through the gate that guards it.

    `exporting` re-checks the release ladder for preview and review candidates.
    Draft saving remains available with validation errors. The two writers not
    exposed here are deliberate: the template
    patch runs through `patch-sch` against a real CTSPro file, and the
    equipment-ready path needs recorded human approval, neither of which should
    be reachable by one POST.
    """
    model = _model(payload)
    kind = str(payload.get("kind", ""))
    writer = EXPORTS.get(kind)
    if writer is None and kind != "draft_save":
        raise ApiError(f"알 수 없는 내보내기 경로입니다: {kind}", status=404)

    out_dir = Path(str(payload.get("outDir", ""))).expanduser()
    if not out_dir.is_absolute():
        raise ApiError("새 출력 폴더의 절대 경로를 입력하세요.")
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        occupied = any(out_dir.iterdir())
    except OSError as exc:
        raise ApiError(f"출력 폴더를 만들거나 읽을 수 없습니다: {exc}") from exc
    if occupied:
        raise ApiError("출력 폴더가 비어 있지 않습니다. 새 빈 폴더를 지정하십시오.")

    if kind == "draft_save":
        draft_path = out_dir / "project.schproj"
        try:
            model.project.save(draft_path)
        except (OSError, ValueError) as exc:
            raise ApiError(f"초안 저장에 실패했습니다: {exc}") from exc
        return {
            "ok": True,
            "kind": kind,
            "paths": [str(draft_path)],
            "note": "초안은 검증 오류가 있어도 저장할 수 있습니다.",
        }

    try:
        assert writer is not None
        result = writer(model.project, out_dir)
    except ExportBlocked as exc:
        raise ApiError(str(exc), status=409) from exc
    except (OSError, ValueError) as exc:
        raise ApiError(f"내보내기에 실패했습니다: {exc}") from exc

    return {
        "ok": True,
        "kind": result.kind,
        "paths": [str(path) for path in result.paths],
        "note": result.note,
    }


def export_batch(payload: dict[str, Any]) -> dict[str, Any]:
    """Replan before writing: only the exact reviewed project and cell list may run."""
    model = _model(payload)
    args = _args(payload)
    plan = plan_cell_batch(
        model.project, phase=str(args.get("phase", "")), basis=str(args.get("basis", "manual_reference")),
        kind=str(args.get("kind", "")), rows=args.get("rows"), matrix=args.get("matrix"),
    )
    try:
        paths = write_cell_batch(
            plan, Path(str(payload.get("outDir", ""))), token=str(payload.get("token", "")),
        )
    except ExportBlocked as exc:
        raise ApiError(str(exc), status=409) from exc
    except (OSError, ValueError) as exc:
        raise ApiError(f"배치 생성에 실패했습니다: {exc}") from exc
    return {
        "ok": True, "kind": plan.kind, "paths": [str(path) for path in paths],
        "note": "셀별 수동 입력 용량으로 생성했습니다. 검토용 SCH는 장비 실행 금지입니다.",
    }


def import_open(path: str) -> tuple[ImportSession, dict[str, Any]]:
    try:
        session = ImportSession.open(Path(path))
    except (OSError, ValueError) as exc:
        raise ApiError(f"열 수 없습니다: {exc}") from exc
    # Legacy binary names are deliberately retained as patch keys. Their
    # evidence-qualified Ensol meanings, not the names, define the UI units.
    descriptions = {
        "fVref": ("설정 전류", "mA"),
        "fIref": ("휴지 시간 / 전류 스텝 시간 제한", "초"),
        "fEndV": ("종료 전압", "mV"),
        "fEndI": ("CV 종료 전류", "mA"),
        "loop_target": ("반복 시작 스텝 번호", "스텝"),
        "loop_count": ("반복 횟수", "회"),
        "record_time_s": ("기록 간격", "초"),
    }
    body = {
        "ok": True,
        "path": str(session.path),
        "sha256": session.sha256,
        "schVersion": (
            f"0x{session.sch_version:08X}" if session.sch_version is not None else ""
        ),
        "stepCount": session.step_count,
        "editableFields": [
            {
                "name": field.name,
                "offset": field.offset,
                "dtype": field.dtype,
                "evidence": field.evidence,
                "label": descriptions.get(field.name, (field.name, ""))[0],
                "unit": descriptions.get(field.name, (field.name, ""))[1],
            }
            for field in session.editable_fields()
        ],
        "dropIfCloned": list(session.propose_clone().dropped),
        # What the file actually does, in plain language with its evidence
        # limits attached — the question a user opening someone else's schedule
        # asks first, and the one the step table alone does not answer.
        "explanation": format_explanation(explain_schedule(session.document)),
    }
    return session, body


def import_proposal(session: ImportSession) -> dict[str, Any]:
    proposal = session.propose_patch()
    return {
        "ok": proposal.ok,
        "accepted": [
            {"stepNo": p.step_no, "field": p.field, "value": p.value}
            for p in proposal.accepted
        ],
        "rejected": [
            {"stepNo": r.step_no, "field": r.field, "reason": r.reason}
            for r in proposal.rejected
        ],
        "notes": list(proposal.notes),
        "warnings": list(proposal.warnings),
        "plan": proposal.plan.to_dict() if proposal.plan else None,
    }


__all__ = [
    "EXPORTS",
    "PLANS",
    "TRANSFORMS",
    "export",
    "import_open",
    "import_proposal",
    "library_list",
    "library_load",
    "library_save",
    "library_versions",
    "module_content",
    "plan",
    "steps",
    "transform",
    "views",
]
