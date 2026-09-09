"""Model objects → JSON-safe dicts.

Lifted from `ui/workspace_qt.py`, which had to do exactly this conversion for
QML and is therefore the tested draft of it. Keeping the conversion here rather
than in the route handlers means the Qt shell can be deleted (G4) without taking
the knowledge with it.
"""

from __future__ import annotations

from typing import Any

from ..edit.diff import StepDiff
from ..release import ReleaseState
from ..report.summary import ProjectSummary
from ..spec.form import ModuleForm
from ..ui.workspace_model import WorkspaceModel


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def summary_json(summary: ProjectSummary) -> dict[str, Any]:
    return {
        "headline": summary.headline,
        "text": summary.as_text(),
        "totalSteps": summary.total_steps,
        "durationText": summary.duration_text,
    }


def release_json(state: ReleaseState) -> dict[str, Any]:
    label = state.label
    return {
        "stage": state.stage,
        "stageLabel": state.stage_label,
        "stageIndex": state.stage_index,
        "label": (
            {
                "label": label.label,
                "labelKo": label.label_ko,
                "meaning": label.meaning_ko,
                "reasons": list(label.reasons),
                "equipmentExecutable": label.equipment_executable,
                "digestMismatch": label.digest_mismatch,
            }
            if label is not None
            else None
        ),
        "options": [
            {
                "kind": option.kind,
                "title": option.title,
                "description": option.description,
                "allowed": option.allowed,
                "blockers": list(option.blockers),
                "nextAction": option.next_action,
                "danger": option.danger,
                "recommended": option.recommended,
                "status": option.status_text,
            }
            for option in state.options
        ],
    }


def diff_json(diff: StepDiff | None) -> dict[str, Any] | None:
    if diff is None:
        return None
    return {
        "headline": diff.headline(),
        "beforeCount": diff.before_count,
        "afterCount": diff.after_count,
        "note": diff.note,
        "changes": [
            {
                "kind": change.kind,
                "label": change.label,
                "beforeIndex": change.before_index,
                "afterIndex": change.after_index,
                "fields": [
                    {"field": field.field, "before": field.before, "after": field.after}
                    for field in change.fields
                ],
            }
            for change in diff.changes
        ],
    }


def field_json(field: Any) -> dict[str, Any]:
    """A spec-driven form field. Same shape the Qt bridge proved out."""
    spec = field.spec
    return {
        "key": spec.key,
        "label": spec.label,
        "labelEn": spec.label_en,
        "kind": spec.kind,
        "unit": spec.unit_label,
        "value": field.view.text,
        "detail": field.view.detail,
        "help": spec.help,
        "basis": spec.basis,
        "affects": spec.affects,
        "range": spec.range_text(),
        "risk": spec.risk,
        "verification": spec.verification_label(),
        "advanced": spec.advanced,
        "choices": [
            {"value": choice.value, "label": choice.label, "help": choice.help}
            for choice in spec.choices
        ],
        "checked": bool(field.value) if spec.kind == "bool" else False,
        "notes": list(field.view.notes),
        "issues": [
            ("오류: " if issue.is_error else "경고: ") + issue.message
            for issue in field.issues
        ],
        "hasError": field.has_error,
    }


def setup_field_json(item: Any, unit_choices: tuple[str, ...]) -> dict[str, Any]:
    """Setup-tab fields are plainer than spec fields: value plus its reading."""
    return {
        "key": item.key,
        "label": item.label,
        "value": item.value,
        "detail": item.detail,
        "issue": item.issue,
        "readOnly": item.key in {"ctspro_build", "sch_layout"},
        "choices": ["", *unit_choices] if item.key == "equipment_unit" else [],
    }


def form_json(form: ModuleForm | None, module_id: str, sibling_count: int) -> dict[str, Any]:
    if form is None:
        return {"moduleId": "", "sections": [], "derived": [], "title": ""}
    return {
        "moduleId": module_id,
        "moduleType": form.module_type,
        "title": form.title,
        "trust": form.trust_status,
        "limitations": list(form.limitations),
        "siblingCount": sibling_count,
        "derived": [
            {
                "label": value.label,
                "text": value.text,
                "severity": value.severity,
                "help": value.help,
            }
            for value in form.derived
        ],
        "sections": [
            {
                "title": section.title,
                "fields": [field_json(field) for field in section.fields],
            }
            for section in form.sections
        ],
    }


def views_json(
    model: WorkspaceModel,
    selected: str | None = None,
    *,
    include_steps: bool = False,
) -> dict[str, Any]:
    """Every derived view of one project, in one payload.

    A screen needs several of these at once and they all come from the same
    project, so splitting them into separate round trips would only add latency
    and the chance of showing two views of different states.

    The expanded step table is the exception. It is read-only, it is shown on one
    tab, and it grew to 312 KB of a 400 KB response on a 2000-cycle campaign —
    sent on every keystroke that committed a field. It is fetched on demand
    instead; `stepCount` still travels so a caller knows what it would get.
    """
    modules = [node.id for node in model.project.modules]
    module_id = selected if selected in modules else (modules[0] if modules else "")
    form = model.form(module_id) if module_id else None
    procedure = model.procedure()

    return {
        "title": model.document.title,
        "dirty": model.document.dirty,
        "selectedModule": module_id,
        "summary": summary_json(model.summary()),
        "release": release_json(model.release()),
        "setupFields": [
            setup_field_json(item, model.unit_choices())
            for item in model.setup_fields()
        ],
        "unitChoices": list(model.unit_choices()),
        "currentLimitmA": model.current_limit_mA,
        "cRatePresets": [
            {
                "label": preset.label,
                "value": preset.value,
                "usage": preset.usage,
                "currentmA": preset.current_mA(
                    model.project.cell_profile.nominal_capacity_mAh
                ),
            }
            for preset in model.c_rate_presets()
        ],
        "goals": [
            {
                "goalId": row.goal_id,
                "title": row.title,
                "question": row.question,
                "outcome": row.outcome,
                "trust": row.trust_status,
                "note": row.note,
            }
            for row in model.goal_rows()
        ],
        "paletteTypes": list(model.palette_types()),
        "modules": [
            {
                "moduleId": row.module_id,
                "moduleType": row.module_type,
                "position": position,
                "title": row.title,
                "subtitle": row.subtitle,
                "steps": row.step_count,
                "range": row.step_range,
                "duration": row.duration,
                "trust": row.trust,
                "error": row.error,
            }
            for position, row in enumerate(model.module_rows(), start=1)
        ],
        "form": form_json(form, module_id, len(model.modules_of_type(form.module_type)) if form else 0),
        "procedure": {
            "durationSeconds": procedure.duration_seconds,
            "durationExact": procedure.duration_exact,
            "stepCount": len(model.step_rows()),
        },
        "steps": list(model.display_step_rows()) if include_steps else [],
        "canEditSteps": bool(module_id) and model.can_edit_steps(module_id),
        "customSteps": (
            [
                {
                    "index": row["index"],
                    "number": row["number"],
                    "stepType": row["stepType"],
                    "mode": row["mode"],
                    "label": row["label"],
                    "fields": [
                        {
                            "key": view.key,
                            "label": view.label,
                            "kind": view.kind,
                            "text": view.text,
                            "detail": view.detail,
                        }
                        for view in row["fields"]
                    ],
                }
                for row in model.custom_step_rows(module_id)
            ]
            if module_id and model.can_edit_steps(module_id)
            else []
        ),
        "validation": [
            {
                "severity": row.severity,
                "severityLabel": row.severity_label,
                "code": row.code,
                "location": row.location,
                "message": row.message,
                "moduleId": _text(row.module_id),
                "fieldKey": _text(row.field_key),
                "stepNumber": row.step_number or 0,
                "remediation": row.remediation,
            }
            for row in model.validation_rows()
        ],
        "unverified": list(model.unverified_notes()),
        "currentLimitBreaches": [
            {"stepNumber": item[0], "label": item[1], "text": item[2]}
            if isinstance(item, tuple)
            else item
            for item in model.current_limit_breaches()
        ],
    }


__all__ = [
    "diff_json",
    "form_json",
    "release_json",
    "setup_field_json",
    "summary_json",
    "views_json",
]
