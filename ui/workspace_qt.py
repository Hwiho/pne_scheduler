"""PySide6 + QML workspace — the one GUI for authoring a schedule.

The QML layer draws; every decision stays in :mod:`ui.workspace_model`, which
has no Qt import.  This class only converts that model into the plain lists
and maps QML understands, and turns QML callbacks back into model calls.

The other tools (viewer, flow canvas, bulk editor, resume wizard) remain
Tkinter; only the workspace is Qt.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from ..edit.diff import StepDiff
from ..protocol.campaign import build_cycle_rpt_campaign
from ..spec import units
from .document import ProjectDocument
from .workspace_model import TRUST_LABELS_KO, WorkspaceModel

QML_DIR = Path(__file__).resolve().parent / "qml"
MAIN_QML = QML_DIR / "Workspace.qml"
AUTOSAVE_INTERVAL_MS = 30_000

# Warm paper palette, carried over from the Tk tools so the suite stays one product.
THEME: dict[str, Any] = {
    "bg": "#f6f1ea",
    "panel": "#fffdfa",
    "panelAlt": "#f2ece3",
    "line": "#e3d9cc",
    "ink": "#3b2f27",
    "muted": "#7a6452",
    "accent": "#245c3d",
    "accentSoft": "#e6f0e9",
    "danger": "#b03a2e",
    "dangerSoft": "#fbeceb",
    "warn": "#9a5b00",
    "warnSoft": "#fdf2e2",
    "radius": 10,
    "pad": 14,
}


def _text(value: Any) -> str:
    return "" if value is None else str(value)


class WorkspaceBridge(QObject):
    """The QML-facing surface of :class:`WorkspaceModel`."""

    changed = Signal()
    statusChanged = Signal()
    selectionChanged = Signal()
    notified = Signal(str, str, str)  # title, body, kind: info | warn | error

    def __init__(self, initial_path: Path | None = None) -> None:
        super().__init__()
        self.model = WorkspaceModel()
        self._status = "준비됨"
        self._autosave_note = ""
        self._selected = ""
        self._pending_recovery = ProjectDocument.recoveries(
            self.model.document.autosave_dir
        )
        if initial_path is not None and Path(initial_path).exists():
            self.openPath(QUrl.fromLocalFile(str(Path(initial_path).resolve())).toString())

    # ------------------------------------------------------------ properties

    def _title(self) -> str:
        return self.model.document.title

    def _dirty(self) -> bool:
        return self.model.document.dirty

    def _headline(self) -> str:
        return self.model.summary().headline

    def _stage(self) -> str:
        return self.model.release().stage_label

    def _can_undo(self) -> bool:
        return self.model.document.can_undo

    def _can_redo(self) -> bool:
        return self.model.document.can_redo

    def _undo_label(self) -> str:
        return self.model.document.undo_label

    def _redo_label(self) -> str:
        return self.model.document.redo_label

    def _summary_text(self) -> str:
        return self.model.summary().as_text()

    def _selected_module(self) -> str:
        return self._selected

    def _status_text(self) -> str:
        return self._status

    def _autosave_text(self) -> str:
        return self._autosave_note

    def _has_recovery(self) -> bool:
        return bool(self._pending_recovery)

    def _recovery_text(self) -> str:
        return self._pending_recovery[0].describe() if self._pending_recovery else ""

    title = Property(str, _title, notify=changed)
    dirty = Property(bool, _dirty, notify=changed)
    summaryHeadline = Property(str, _headline, notify=changed)
    stageLabel = Property(str, _stage, notify=changed)
    canUndo = Property(bool, _can_undo, notify=changed)
    canRedo = Property(bool, _can_redo, notify=changed)
    undoLabel = Property(str, _undo_label, notify=changed)
    redoLabel = Property(str, _redo_label, notify=changed)
    summaryText = Property(str, _summary_text, notify=changed)
    selectedModule = Property(str, _selected_module, notify=selectionChanged)
    statusText = Property(str, _status_text, notify=statusChanged)
    autosaveText = Property(str, _autosave_text, notify=statusChanged)
    hasRecovery = Property(bool, _has_recovery, notify=changed)
    recoveryText = Property(str, _recovery_text, notify=changed)

    # --------------------------------------------------------------- helpers

    def _emit(self, status: str | None = None) -> None:
        if status is not None:
            self._status = status
            self.statusChanged.emit()
        self._ensure_selection()
        self.changed.emit()

    def _ensure_selection(self) -> None:
        ids = [node.id for node in self.model.project.modules]
        if self._selected not in ids:
            self._selected = ids[0] if ids else ""
            self.selectionChanged.emit()

    # --------------------------------------------------------------- reading

    @Slot(result="QVariantList")
    def setupFields(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.model.setup_fields():
            row: dict[str, Any] = {
                "key": item.key,
                "label": item.label,
                "value": item.value,
                "detail": item.detail,
                "issue": item.issue,
                "readOnly": item.key in {"ctspro_build", "sch_layout"},
                "choices": [],
            }
            if item.key == "equipment_unit":
                row["choices"] = ["", *self.model.unit_choices()]
            rows.append(row)
        return rows

    @Slot(str, result="QVariantList")
    def goals(self, query: str = "") -> list[dict[str, Any]]:
        return [
            {
                "goalId": goal.goal_id,
                "title": goal.title,
                "question": goal.question,
                "outcome": goal.outcome,
                "note": goal.note,
                "trust": TRUST_LABELS_KO.get(goal.trust_status, goal.trust_status),
            }
            for goal in self.model.goal_rows(query)
        ]

    @Slot(result="QVariantList")
    def moduleRows(self) -> list[dict[str, Any]]:
        return [
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
            for position, row in enumerate(self.model.module_rows(), start=1)
        ]

    @Slot(result="QVariantMap")
    def form(self) -> dict[str, Any]:
        if not self._selected:
            return {"moduleId": "", "sections": [], "derived": [], "title": ""}
        module_form = self.model.form(self._selected)
        sections = [
            {
                "title": section.title,
                "fields": [self._field_map(field) for field in section.fields],
            }
            for section in module_form.sections
        ]
        return {
            "moduleId": self._selected,
            "moduleType": module_form.module_type,
            "title": module_form.title,
            "trust": TRUST_LABELS_KO.get(module_form.trust_status, module_form.trust_status),
            "limitations": list(module_form.limitations),
            "siblingCount": len(self.model.modules_of_type(module_form.module_type)),
            "derived": [
                {
                    "label": value.label,
                    "text": value.text,
                    "severity": value.severity,
                    "help": value.help,
                }
                for value in module_form.derived
            ],
            "sections": sections,
        }

    @staticmethod
    def _field_map(field) -> dict[str, Any]:
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
            "choices": [choice.label for choice in spec.choices],
            "checked": bool(field.value) if spec.kind == "bool" else False,
            "notes": list(field.view.notes),
            "issues": [
                ("오류: " if issue.is_error else "경고: ") + issue.message
                for issue in field.issues
            ],
            "hasError": field.has_error,
        }

    @Slot(result="QVariantList")
    def phases(self) -> list[dict[str, Any]]:
        return self.moduleRows()

    @Slot(result="QVariantList")
    def stepRows(self) -> list[dict[str, str]]:
        return list(self.model.display_step_rows())

    @Slot(result="QVariantList")
    def validationRows(self) -> list[dict[str, Any]]:
        return [
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
            for row in self.model.validation_rows()
        ]

    @Slot(result="QVariantList")
    def unverifiedNotes(self) -> list[str]:
        return list(self.model.unverified_notes())

    @Slot(result="QVariantList")
    def releaseOptions(self) -> list[dict[str, Any]]:
        return [
            {
                "kind": option.kind,
                "title": option.title,
                "description": option.description,
                "allowed": option.allowed,
                "blockers": list(option.blockers),
                "nextAction": option.next_action,
                "danger": option.danger,
                "status": option.status_text,
            }
            for option in self.model.release().options
        ]

    @Slot(result="QVariantList")
    def ladder(self) -> list[dict[str, Any]]:
        return [
            {"stage": stage, "label": label, "reached": reached}
            for stage, label, reached in self.model.release().ladder()
        ]

    @Slot(result="QVariantMap")
    def reviewState(self) -> dict[str, Any]:
        review = self.model.project.review
        return {
            "ctsproReviewed": review.ctspro_reviewed,
            "ctsproReviewer": review.ctspro_reviewer,
            "equipmentApproved": review.equipment_approved,
            "equipmentApprovedBy": review.equipment_approved_by,
        }

    # --------------------------------------------------------------- editing

    @Slot(str)
    def selectModule(self, module_id: str) -> None:
        if module_id != self._selected:
            self._selected = module_id
            self.selectionChanged.emit()

    @Slot(str, str, result="QVariantMap")
    def setSetupValue(self, key: str, text: str) -> dict[str, Any]:
        try:
            if key == "name":
                self.model.set_project_name(text)
            elif key == "equipment_unit":
                self.model.set_equipment_unit(text)
            else:
                self.model.set_cell_value(key, text)
        except (units.UnitParseError, ValueError) as exc:
            return {"ok": False, "message": str(exc)}
        self._emit(f"설정 변경: {key}")
        if key in {"nominal_capacity_mAh", "equipment_unit", "max_current_mA"}:
            breaches = self.model.current_limit_breaches()
            if breaches:
                body = "\n".join(
                    f"· {row.location}: {row.message}" for row in breaches[:5]
                )
                if len(breaches) > 5:
                    body += "\n· …"
                self.notified.emit(
                    "전류 한계를 넘습니다",
                    f"이 설정에서는 {len(breaches)}개 스텝이 허용 전류를 넘습니다.\n\n{body}"
                    "\n\n검증 탭에서 전체 목록을 볼 수 있습니다. 저장은 계속 가능합니다.",
                    "warn",
                )
        return {"ok": True, "message": ""}

    @Slot(result="QVariantList")
    def cRatePresets(self) -> list[dict[str, Any]]:
        """One-tap C-rates, already priced in mA for this cell."""
        capacity = self.model.project.cell_profile.nominal_capacity_mAh
        return [
            {
                "label": preset.label,
                "value": preset.value,
                "usage": preset.usage,
                "currentText": (
                    units.format_current_mA(preset.current_mA(capacity))
                    if capacity
                    else ""
                ),
            }
            for preset in self.model.c_rate_presets()
        ]

    @Slot(float, int, result="QVariantMap")
    def cyclesWithin(self, days: float, step: int) -> dict[str, Any]:
        budget = self.model.cycles_within(days * 86400.0, step=max(1, step))
        return {
            "ok": budget.ok,
            "totalCycles": budget.total_cycles,
            "text": budget.as_text(),
            "notes": list(budget.notes),
            "warnings": list(budget.warnings),
            "errors": list(budget.errors),
        }

    @Slot(int, result="QVariantMap")
    def applyCycleCount(self, count: int) -> dict[str, Any]:
        target = next(
            (
                node.id
                for node in self.model.project.modules
                if node.module_type in {"cycle_life", "insitu_cycle"}
            ),
            None,
        )
        if target is None:
            return {"ok": False, "message": "사이클 구간이 없습니다."}
        self.model.set_cycle_count(target, count)
        self._emit(f"{target} 를 {count} 사이클로 맞췄습니다.")
        return {"ok": True, "message": target}

    def _campaign_plan(self, options: dict[str, Any]):
        return build_cycle_rpt_campaign(
            total_cycles=int(options.get("totalCycles", 0) or 0),
            rpt_every=int(options.get("rptEvery", 50) or 50),
            charge_c_rate=float(options.get("chargeCRate", 0.5) or 0.0),
            discharge_c_rate=float(options.get("dischargeCRate", 0.5) or 0.0),
            dcir_pulse_c_rates=[
                float(rate) for rate in options.get("dcirRates", [1.0, 1.5, 2.0])
            ],
            baseline_rpt=bool(options.get("baselineRpt", True)),
        )

    @Slot("QVariantMap", result="QVariantMap")
    def planCampaign(self, options: dict[str, Any]) -> dict[str, Any]:
        """Preview a cycle/RPT campaign; the project is not touched."""
        plan = self._campaign_plan(options)
        return {
            "ok": plan.ok,
            "blocks": [
                {"moduleType": block.module_type, "title": block.title}
                for block in plan.blocks
            ],
            "totalCycles": plan.total_cycles,
            "rptCount": plan.rpt_count,
            "notes": list(plan.notes),
            "warnings": list(plan.warnings),
            "errors": list(plan.errors),
        }

    @Slot("QVariantMap", result="QVariantMap")
    def addCampaign(self, options: dict[str, Any]) -> dict[str, Any]:
        plan = self._campaign_plan(options)
        if not plan.ok:
            return {"ok": False, "message": " ".join(plan.errors)}
        ids = self.model.add_campaign(plan)
        self._selected = ids[0]
        self.selectionChanged.emit()
        self._emit(
            f"사이클 {plan.total_cycles}회 · RPT {plan.rpt_count}회를 추가했습니다."
        )
        self.notified.emit(
            "캠페인을 추가했습니다",
            "\n\n".join([*plan.notes, *plan.warnings]),
            "warn",
        )
        return {"ok": True, "message": ids[0]}

    @Slot(str, "QVariantList", result="QVariantMap")
    def planQcFastCharge(self, module_id: str, rates: list[Any]) -> dict[str, Any]:
        """Derive the voltage and time lists that go with these QC rates."""
        node = next(
            (n for n in self.model.project.modules if n.id == module_id), None
        )
        if node is None or node.module_type != "qc":
            return {"ok": False, "errors": ["QC 구간을 먼저 선택하세요."]}
        try:
            values = [float(rate) for rate in rates]
        except (TypeError, ValueError):
            return {"ok": False, "errors": ["전류 값을 숫자로 입력하세요."]}
        plan = self.model.plan_qc_fast_charge(module_id, values)
        return {
            "ok": plan.ok,
            "rates": list(plan.rates_c),
            "voltages": list(plan.voltages_v),
            "times": list(plan.times_s),
            "notes": list(plan.notes),
            "warnings": list(plan.warnings),
            "errors": list(plan.errors),
        }

    @Slot(str, "QVariantList", result="QVariantMap")
    def applyQcFastCharge(self, module_id: str, rates: list[Any]) -> dict[str, Any]:
        preview = self.planQcFastCharge(module_id, rates)
        if not preview.get("ok"):
            return {"ok": False, "message": " ".join(preview.get("errors", []))}
        plan = self.model.plan_qc_fast_charge(
            module_id, [float(rate) for rate in rates]
        )
        self.model.apply_qc_fast_charge(module_id, plan)
        self._emit("급속충전 전류에 맞춰 전압·시간을 함께 바꿨습니다.")
        self.notified.emit(
            "급속충전 값을 다시 계산했습니다",
            "\n\n".join([*plan.notes, *plan.warnings]),
            "warn",
        )
        return {"ok": True, "message": module_id}

    @Slot(str, result="QVariantMap")
    def addGoal(self, goal_id: str) -> dict[str, Any]:
        try:
            module_id = self.model.add_goal(goal_id)
        except ValueError as exc:
            return {"ok": False, "message": str(exc)}
        self._selected = module_id
        self.selectionChanged.emit()
        self._emit("실험을 추가했습니다. 값은 오른쪽에서 바로 고칠 수 있습니다.")
        return {"ok": True, "message": module_id}

    @Slot()
    def removeSelected(self) -> None:
        if not self._selected:
            return
        removed = self._selected
        self.model.remove_module(removed)
        self._emit(f"{removed} 구간을 삭제했습니다.")

    @Slot()
    def duplicateSelected(self) -> None:
        if not self._selected:
            return
        self._selected = self.model.duplicate_module(self._selected)
        self.selectionChanged.emit()
        self._emit("구간을 복제했습니다.")

    @Slot(str, str, result="QVariantMap")
    def previewParam(self, key: str, text: str) -> dict[str, Any]:
        if not self._selected:
            return {"ok": False, "message": ""}
        try:
            diff = self.model.preview_param(self._selected, key, text)
        except (units.UnitParseError, ValueError) as exc:
            return {"ok": False, "message": str(exc)}
        return {"ok": True, "message": diff.headline(), "lines": list(diff.preview_lines(6))}

    @Slot(str, str, result="QVariantMap")
    def setParam(self, key: str, text: str) -> dict[str, Any]:
        if not self._selected:
            return {"ok": False, "message": "선택된 구간이 없습니다."}
        try:
            diff: StepDiff = self.model.set_param(self._selected, key, text)
        except (units.UnitParseError, ValueError) as exc:
            return {"ok": False, "message": str(exc)}
        self._emit(diff.headline())
        return {"ok": True, "message": diff.headline()}

    @Slot(str, str, result="QVariantMap")
    def applyToAll(self, key: str, text: str) -> dict[str, Any]:
        if not self._selected:
            return {"ok": False, "message": "선택된 구간이 없습니다."}
        module_type = self.model.form(self._selected).module_type
        try:
            count, diff = self.model.apply_to_all_of_type(module_type, key, text)
        except (units.UnitParseError, ValueError) as exc:
            return {"ok": False, "message": str(exc)}
        self._emit(f"{count}개 구간에 적용됨 · {diff.headline()}")
        return {"ok": True, "message": f"{count}개 구간에 적용됨"}

    @Slot(int)
    def moveSelected(self, delta: int) -> None:
        if not self._selected:
            return
        if self.model.move(self._selected, delta):
            self._emit("구간 순서를 옮겼습니다.")

    @Slot("QVariantList")
    def reorder(self, ordered_ids: list[str]) -> None:
        try:
            self.model.reorder([str(item) for item in ordered_ids])
        except ValueError as exc:
            self.notified.emit("순서를 바꿀 수 없습니다", str(exc), "error")
            return
        self._emit("구간 순서를 바꿨습니다.")

    @Slot()
    def detachSelected(self) -> None:
        if not self._selected:
            return
        try:
            self.model.detach(self._selected)
        except ValueError as exc:
            self.notified.emit("분리할 수 없습니다", str(exc), "error")
            return
        self._emit("개별 스텝으로 분리했습니다. 이제 '직접 편집' 상태입니다.")

    # ---------------------------------------------------------------- review

    @Slot(str)
    def recordReview(self, reviewer: str) -> None:
        if not reviewer.strip():
            self.notified.emit("검토자 필요", "검토자 이름을 입력하세요.", "info")
            return
        self.model.record_ctspro_review(
            reviewer=reviewer.strip(),
            reviewed_at=datetime.now().isoformat(timespec="seconds"),
        )
        self._emit("CTSPro 확인을 기록했습니다.")

    @Slot(str)
    def recordApproval(self, approver: str) -> None:
        if not approver.strip():
            self.notified.emit("승인자 필요", "승인자 이름을 입력하세요.", "info")
            return
        self.model.record_equipment_approval(
            approver=approver.strip(),
            approved_at=datetime.now().isoformat(timespec="seconds"),
        )
        self._emit("장비 실행 승인을 기록했습니다.")

    @Slot()
    def clearApprovals(self) -> None:
        self.model.clear_approvals()
        self._emit("승인 기록을 해제했습니다.")

    # ----------------------------------------------------------------- files

    @Slot()
    def newProject(self) -> None:
        self.model.new_document()
        self._selected = ""
        self.selectionChanged.emit()
        self._emit("새 프로젝트를 만들었습니다.")

    @Slot(str)
    def openPath(self, url: str) -> None:
        from ..ir.loader import ProjectLoadError

        path = _local_path(url)
        try:
            repairs = self.model.open_path(path)
        except ProjectLoadError as exc:
            self.notified.emit("열 수 없습니다", str(exc), "error")
            return
        self._selected = ""
        self.selectionChanged.emit()
        if repairs:
            self.notified.emit(
                "일부 값을 고쳐서 열었습니다",
                "\n".join(f"· {item}" for item in repairs)
                + "\n\n확인 후 저장하면 고쳐진 값이 파일에 반영됩니다.",
                "warn",
            )
        self._emit(f"{path.name} 을(를) 열었습니다.")

    @Slot(result=bool)
    def needsSavePath(self) -> bool:
        return self.model.document.path is None

    @Slot()
    def save(self) -> None:
        if self.model.document.path is None:
            return
        path = self.model.document.save()
        self._emit(f"저장됨: {path}")

    @Slot(str)
    def saveAs(self, url: str) -> None:
        path = _local_path(url)
        if path.suffix != ".schproj":
            path = path.with_suffix(".schproj")
        saved = self.model.document.save(path)
        self._emit(f"저장됨: {saved}")

    @Slot(result=str)
    def suggestedFileName(self) -> str:
        return f"{self.model.project.name}.schproj"

    @Slot()
    def undo(self) -> None:
        label = self.model.document.undo()
        self._emit(f"실행 취소: {label}" if label else "되돌릴 작업이 없습니다.")

    @Slot()
    def redo(self) -> None:
        label = self.model.document.redo()
        self._emit(f"다시 실행: {label}" if label else "다시 실행할 작업이 없습니다.")

    @Slot()
    def acceptRecovery(self) -> None:
        if not self._pending_recovery:
            return
        self.model.document = ProjectDocument.recover(
            self._pending_recovery[0], autosave_dir=self.model.document.autosave_dir
        )
        self._pending_recovery = ()
        self._selected = ""
        self.selectionChanged.emit()
        self._emit("자동 저장본을 복구했습니다. 확인 후 저장하세요.")

    @Slot()
    def discardRecovery(self) -> None:
        for snapshot in self._pending_recovery:
            ProjectDocument.discard_recovery(snapshot)
        self._pending_recovery = ()
        self._emit()

    @Slot()
    def autosave(self) -> None:
        try:
            path = self.model.document.autosave()
        except OSError:
            path = None
        if path:
            self._autosave_note = f"자동 저장됨 {datetime.now():%H:%M:%S}"
            self.statusChanged.emit()

    @Slot()
    def clearAutosave(self) -> None:
        self.model.document.clear_autosave()

    # --------------------------------------------------------------- exports

    @Slot(str)
    def exportPreview(self, url: str) -> None:
        from ..exporting import ExportBlocked, export_preview

        try:
            result = export_preview(self.model.project, _local_path(url))
        except (ExportBlocked, OSError, ValueError) as exc:
            self.notified.emit("아직 내보낼 수 없습니다", str(exc), "error")
            return
        self.notified.emit(
            "미리보기 저장 완료",
            "\n".join([result.note, "", *[str(path) for path in result.paths]]),
            "info",
        )
        self._emit("미리보기를 저장했습니다.")

    @Slot(str)
    def exportReviewCandidate(self, url: str) -> None:
        from ..exporting import ExportBlocked, export_review_candidate

        try:
            result = export_review_candidate(self.model.project, _local_path(url))
        except (ExportBlocked, OSError, ValueError) as exc:
            self.notified.emit("아직 내보낼 수 없습니다", str(exc), "error")
            return
        self.notified.emit(
            "검토 전용 파일 생성됨",
            "\n".join(
                [
                    result.note,
                    "",
                    "이 파일은 CTSEditorPro 에서 열어 확인하는 용도입니다.",
                    "절대 장비에서 실행하지 마세요.",
                    "",
                    *[str(path) for path in result.paths],
                ]
            ),
            "warn",
        )
        self._emit("CTSPro 검토용 후보를 만들었습니다.")

    @Slot()
    def templatePatchHelp(self) -> None:
        self.notified.emit(
            "템플릿 패치",
            "CTSPro 가 만든 원본 .sch 와 그 SHA-256 이 필요합니다.\n\n"
            "python -m pne_scheduler patch-sch 원본.sch 계획.json -o 결과.sch "
            "--allow-analysis-output\n\n"
            "검증된 필드만 바뀌고 나머지 바이트는 그대로 보존됩니다.",
            "info",
        )

    @Slot()
    def equipmentExport(self) -> None:
        self.notified.emit(
            "장비 실행용 내보내기",
            "장비 실행용 경로는 아직 열려 있지 않습니다.\n"
            "CTSPro 확인과 장비 승인이 기록된 뒤에도, 실제 장비 스모크 테스트가 "
            "끝나야 사용할 수 있습니다.",
            "warn",
        )

    @Slot()
    def copySummary(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.model.summary().as_text())
        self._emit("요약을 클립보드에 복사했습니다.")

    # ------------------------------------------------------- advanced (Tk)

    @Slot(str)
    def openLegacyTool(self, name: str) -> None:
        """Launch one of the Tkinter tools in its own process.

        They keep their own event loop, so they are started detached rather
        than nested inside the Qt one.
        """
        import subprocess

        scripts = {
            "viewer": "run_pne_scheduler_viewer.py",
            "flow": "run_pne_scheduler_flow.py",
            "editor": "run_pne_scheduler_editor.py",
            "resume": "run_pne_scheduler_resume.py",
        }
        script = scripts.get(name)
        if script is None:
            return
        path = Path(__file__).resolve().parents[1] / script
        try:
            subprocess.Popen([sys.executable, str(path)])
        except OSError as exc:
            self.notified.emit("실행할 수 없습니다", str(exc), "error")
            return
        self._emit(f"{name} 도구를 별도 창으로 열었습니다.")


def _local_path(url: str) -> Path:
    candidate = QUrl(url)
    if candidate.isLocalFile():
        return Path(candidate.toLocalFile())
    return Path(url)


def build_engine(
    initial_path: Path | None = None,
) -> tuple[QQmlApplicationEngine, WorkspaceBridge]:
    """Create the QML engine with the bridge and theme in its root context."""
    engine = QQmlApplicationEngine()
    bridge = WorkspaceBridge(initial_path)
    engine.rootContext().setContextProperty("workspace", bridge)
    engine.rootContext().setContextProperty("Theme", THEME)
    engine.load(QUrl.fromLocalFile(str(MAIN_QML)))
    if not engine.rootObjects():
        raise RuntimeError(f"QML 화면을 불러오지 못했습니다: {MAIN_QML}")
    return engine, bridge


def launch_workspace(initial_path: Path | None = None) -> int:
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    app.setApplicationName("PNE 스케줄 워크스페이스")
    app.setOrganizationName("pne_scheduler")
    engine, bridge = build_engine(initial_path)

    timer = QTimer()
    timer.setInterval(AUTOSAVE_INTERVAL_MS)
    timer.timeout.connect(bridge.autosave)
    timer.start()

    exit_code = app.exec()
    bridge.clearAutosave()
    del engine
    return exit_code


__all__ = ["THEME", "WorkspaceBridge", "build_engine", "launch_workspace"]
