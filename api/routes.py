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
from typing import Any, Callable

from ..edit.steps import StepEditError
from ..exporting import ExportBlocked, export_preview, export_review_candidate
from ..import_session import ImportSession
from ..library import MethodLibrary, MethodVersion
from ..ui.document import ProjectDocument
from ..ui.workspace_model import WorkspaceModel
from .errors import ApiError
from .serializers import diff_json, views_json


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


# --- transform --------------------------------------------------------------


def _run(model: WorkspaceModel, call: Callable[[], Any]) -> dict[str, Any]:
    try:
        result = call()
    except (StepEditError, ValueError) as exc:
        raise ApiError(str(exc)) from exc
    return {
        "ok": True,
        "project": model.project.to_dict(),
        "label": model.document.last_label,
        "diff": diff_json(result if hasattr(result, "changes") else None),
        "views": views_json(model, model.project.modules[0].id if model.project.modules else None),
    }


TRANSFORMS: dict[str, Callable[[WorkspaceModel, dict[str, Any]], Any]] = {
    "setProjectName": lambda m, a: m.set_project_name(a["name"]),
    "setEquipmentUnit": lambda m, a: m.set_equipment_unit(a["unit"]),
    "setCellValue": lambda m, a: m.set_cell_value(a["key"], a["text"]),
    "addGoal": lambda m, a: m.add_goal(a["goalId"]),
    "addModule": lambda m, a: m.add_module(a["moduleType"], a.get("params")),
    "removeModule": lambda m, a: m.remove_module(a["moduleId"]),
    "duplicateModule": lambda m, a: m.duplicate_module(a["moduleId"]),
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


def transform(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    handler = TRANSFORMS.get(action)
    if handler is None:
        raise ApiError(f"알 수 없는 편집입니다: {action}", status=404)
    model = _model(payload)
    args = _args(payload)
    try:
        return _run(model, lambda: handler(model, args))
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
            float(rate) for rate in options.get("dcirRates", [1.0, 1.5, 2.0])
        ],
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
        entry = model.save_method(name, description=payload.get("description", ""))
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

    `exporting` re-checks the release ladder itself, so a direct call cannot slip
    past a blocked path — this route adds no judgement of its own, it just names
    the failure. The two writers not exposed here are deliberate: the template
    patch runs through `patch-sch` against a real CTSPro file, and the
    equipment-ready path needs recorded human approval, neither of which should
    be reachable by one POST.
    """
    model = _model(payload)
    kind = str(payload.get("kind", ""))
    writer = EXPORTS.get(kind)
    if writer is None:
        raise ApiError(f"알 수 없는 내보내기 경로입니다: {kind}", status=404)

    out_dir = Path(str(payload.get("outDir", ""))).expanduser()
    if not out_dir.is_dir():
        raise ApiError(f"출력 폴더가 없습니다: {out_dir}")

    try:
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


def import_open(path: str) -> tuple[ImportSession, dict[str, Any]]:
    try:
        session = ImportSession.open(Path(path))
    except (OSError, ValueError) as exc:
        raise ApiError(f"열 수 없습니다: {exc}") from exc
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
            }
            for field in session.editable_fields()
        ],
        "dropIfCloned": list(session.propose_clone().dropped),
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
    "plan",
    "steps",
    "transform",
    "views",
]
