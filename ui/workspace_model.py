"""Everything the workspace shows and does, with no Tk in sight.

The Tk layer binds widgets to these methods; the rules about what is editable,
what a value means, and what is blocked all live here, so they are testable
without a display.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..edit.diff import StepDiff, diff_projects, preview_module_change
from ..ir.equipment_profile import (
    EquipmentProfile,
    effective_current_limit_mA,
    known_units,
)
from ..ir.procedure import (
    ProcedureView,
    build_procedure,
    detach_module,
    linearize,
    move_module,
    procedure_step_rows,
    reorder_modules,
)
from ..ir.project import ModuleNode, ScheduleProject
from ..modules.base import get_module_class
from ..modules.catalog import get_module_spec, palette_module_types
from ..protocol.recipes import ExperimentGoal, get_goal, search_goals
from ..release import ReleaseState, evaluate_release
from ..report.summary import ProjectSummary, summarize_project
from ..spec import units
from ..spec.form import ModuleForm, apply_field_edit, build_module_form, resolve_params
from ..spec.parameter import VERIFICATION_LABELS_KO
from ..validate.preflight import validate_project
from .document import ProjectDocument

TRUST_LABELS_KO: dict[str, str] = {
    "prototype": "시제 (미검증)",
    "software-checked": "소프트웨어 검증",
    "CTSPro-reopen-verified": "CTSPro 확인 완료",
    "equipment-run-verified": "장비 실행 검증",
}


@dataclass(frozen=True, slots=True)
class SetupField:
    key: str
    label: str
    value: str
    detail: str = ""
    issue: str = ""


@dataclass(frozen=True, slots=True)
class ModuleRow:
    module_id: str
    module_type: str
    title: str
    subtitle: str
    step_count: int
    step_range: str
    duration: str
    trust: str
    error: str = ""


@dataclass(frozen=True, slots=True)
class ValidationRow:
    severity: str
    code: str
    message: str
    location: str
    module_id: str | None = None
    field_key: str | None = None
    step_number: int | None = None
    remediation: str = ""

    @property
    def severity_label(self) -> str:
        return {"error": "오류", "warning": "경고"}.get(self.severity, self.severity)


class WorkspaceModel:
    """Document + derived views + every edit the workspace can perform."""

    def __init__(self, document: ProjectDocument | None = None) -> None:
        self.document = document or ProjectDocument.new()

    # ------------------------------------------------------------ project

    @property
    def project(self) -> ScheduleProject:
        return self.document.project

    @property
    def current_limit_mA(self) -> float | None:
        return effective_current_limit_mA(
            self.project.cell_profile.max_current_mA, self.project.equipment
        )

    def summary(self) -> ProjectSummary:
        return summarize_project(self.project)

    def release(self) -> ReleaseState:
        return evaluate_release(self.project)

    # -------------------------------------------------------------- setup

    def unit_choices(self) -> tuple[str, ...]:
        return known_units()

    def setup_fields(self) -> tuple[SetupField, ...]:
        cell = self.project.cell_profile
        equipment = self.project.equipment
        limit = self.current_limit_mA
        one_c = cell.nominal_capacity_mAh
        fields = [
            SetupField("name", "프로젝트 이름", self.project.name),
            SetupField(
                "equipment_unit",
                "PNE 장비",
                equipment.unit if equipment else "",
                equipment.describe() if equipment else "장비를 선택해야 내보내기가 열립니다.",
                "" if equipment else "장비 미지정",
            ),
            SetupField(
                "nominal_capacity_mAh",
                "셀 공칭 용량 (mAh)",
                f"{cell.nominal_capacity_mAh:g}",
                f"1C = {units.format_current_mA(one_c)}"
                + (
                    f" · 한계 {units.format_current_mA(limit)} 기준 최대 "
                    f"{units.format_c_rate(limit / one_c)}"
                    if limit and one_c > 0
                    else ""
                ),
            ),
            SetupField(
                "v_max", "상한 전압", units.format_voltage(cell.v_max),
                "충전 종료·안전 상한으로 쓰입니다.",
            ),
            SetupField(
                "v_min", "하한 전압", units.format_voltage(cell.v_min),
                "방전 종료·안전 하한으로 쓰입니다.",
            ),
            SetupField(
                "max_current_mA",
                "셀 최대 전류 (mA)",
                "" if cell.max_current_mA is None else f"{cell.max_current_mA:g}",
                (
                    f"실제 적용 한계: {units.format_current_mA(limit)}"
                    if limit
                    else "비워 두면 장비 정격만 사용합니다."
                ),
            ),
        ]
        if equipment:
            fields.append(
                SetupField(
                    "ctspro_build",
                    "CTSPro 버전",
                    equipment.ctspro_build or "",
                    equipment.ctspro_build_source or "레지스트리에 기록이 없습니다.",
                    "" if equipment.ctspro_build else "미기록",
                )
            )
            fields.append(
                SetupField(
                    "sch_layout",
                    "SCH layout",
                    equipment.layout_key or "",
                    "확인된 레이아웃" if equipment.layout_confirmed else "관측 기반 (미확정)",
                    "" if equipment.layout_key else "미지정",
                )
            )
        return tuple(fields)

    def set_project_name(self, name: str) -> None:
        cleaned = name.strip() or "이름 없는 프로젝트"

        def mutate(project: ScheduleProject) -> None:
            project.name = cleaned

        self.document.apply("프로젝트 이름 변경", mutate)

    def set_equipment_unit(self, unit: str) -> EquipmentProfile | None:
        cleaned = unit.strip()

        def mutate(project: ScheduleProject) -> EquipmentProfile | None:
            project.equipment = EquipmentProfile.from_unit(cleaned) if cleaned else None
            return project.equipment

        return self.document.apply(f"장비 선택 ({cleaned or '없음'})", mutate)

    def set_cell_value(self, key: str, text: str) -> None:
        """Parse and store one cell field; unit text like ``4.2 V`` is accepted."""
        cell = self.project.cell_profile
        if key == "nominal_capacity_mAh":
            value = units.parse_number(text)
            if value <= 0:
                raise units.UnitParseError("셀 용량은 0 보다 커야 합니다.")
        elif key in {"v_max", "v_min"}:
            value = units.parse_voltage(text)
        elif key == "max_current_mA":
            stripped = str(text).strip()
            value = None if not stripped else units.parse_number(stripped)
            if value is not None and value <= 0:
                raise units.UnitParseError("최대 전류는 0 보다 커야 합니다.")
        else:
            raise units.UnitParseError(f"알 수 없는 셀 항목입니다: {key}")

        if key == "v_max" and value <= cell.v_min:
            raise units.UnitParseError("상한 전압은 하한 전압보다 커야 합니다.")
        if key == "v_min" and value >= cell.v_max:
            raise units.UnitParseError("하한 전압은 상한 전압보다 작아야 합니다.")

        def mutate(project: ScheduleProject) -> None:
            setattr(project.cell_profile, key, value)

        self.document.apply(f"셀 설정 변경 ({key})", mutate)

    # ----------------------------------------------------------- protocol

    def goal_rows(self, query: str = "") -> tuple[ExperimentGoal, ...]:
        return search_goals(query)

    def palette_types(self) -> tuple[str, ...]:
        return palette_module_types()

    def add_goal(self, goal_id: str) -> str:
        goal = get_goal(goal_id)
        if goal is None:
            raise ValueError(f"알 수 없는 실험 목적입니다: {goal_id}")
        return self.add_module(goal.module_type, goal.params, label=goal.title)

    def add_module(
        self,
        module_type: str,
        params: dict[str, Any] | None = None,
        *,
        label: str | None = None,
    ) -> str:
        if get_module_class(module_type) is None:
            raise ValueError(f"알 수 없는 실험 종류입니다: {module_type}")
        resolved = resolve_params(module_type, dict(params or {}))
        module_id = self._next_id(module_type)

        def mutate(project: ScheduleProject) -> None:
            project.modules.append(ModuleNode(module_id, module_type, resolved))
            linearize(project)

        title = label or (get_module_spec(module_type).title if get_module_spec(module_type) else module_type)
        self.document.apply(f"{title} 추가", mutate)
        return module_id

    def remove_module(self, module_id: str) -> None:
        def mutate(project: ScheduleProject) -> None:
            project.modules[:] = [n for n in project.modules if n.id != module_id]
            project.connections[:] = [
                edge
                for edge in project.connections
                if edge.source_id != module_id and edge.target_id != module_id
            ]
            linearize(project)

        self.document.apply(f"{module_id} 삭제", mutate)

    def duplicate_module(self, module_id: str) -> str:
        node = self._node(module_id)
        new_id = self._next_id(node.module_type)

        def mutate(project: ScheduleProject) -> None:
            index = [n.id for n in project.modules].index(module_id)
            project.modules.insert(
                index + 1, ModuleNode(new_id, node.module_type, dict(node.params))
            )
            linearize(project)

        self.document.apply(f"{module_id} 복제", mutate)
        return new_id

    def module_rows(self) -> tuple[ModuleRow, ...]:
        view = self.procedure()
        rows: list[ModuleRow] = []
        for phase in view.phases:
            rows.append(
                ModuleRow(
                    module_id=phase.module_id,
                    module_type=phase.module_type,
                    title=phase.title,
                    subtitle=phase.subtitle,
                    step_count=phase.step_count,
                    step_range=phase.step_range_text,
                    duration=(
                        units.format_duration_ko(phase.duration_seconds)
                        if phase.duration_seconds
                        else "—"
                    ),
                    trust=TRUST_LABELS_KO.get(phase.trust_status, phase.trust_status),
                    error=phase.error,
                )
            )
        return tuple(rows)

    def form(self, module_id: str, *, include_advanced: bool = True) -> ModuleForm:
        node = self._node(module_id)
        return build_module_form(
            node.module_type,
            node.params,
            cell=self.project.cell_profile,
            current_limit_mA=self.current_limit_mA,
            include_advanced=include_advanced,
        )

    def preview_param(self, module_id: str, key: str, text: Any) -> StepDiff:
        """What this edit would do to the step list — shown before applying."""
        node = self._node(module_id)
        params = apply_field_edit(node.module_type, node.params, key, text)
        return preview_module_change(self.project, module_id, params)

    def set_param(self, module_id: str, key: str, text: Any) -> StepDiff:
        node = self._node(module_id)
        params = apply_field_edit(node.module_type, node.params, key, text)
        before = self.project.copy()

        def mutate(project: ScheduleProject) -> None:
            for candidate in project.modules:
                if candidate.id == module_id:
                    candidate.params = params
                    break

        self.document.apply(f"{module_id}.{key} 변경", mutate)
        return diff_projects(before, self.project)

    def modules_of_type(self, module_type: str) -> tuple[str, ...]:
        return tuple(
            node.id for node in self.project.modules if node.module_type == module_type
        )

    def apply_to_all_of_type(
        self, module_type: str, key: str, text: Any
    ) -> tuple[int, StepDiff]:
        """Set one parameter on every phase of the same type at once.

        This is the bulk editor, folded into the form where the value is being
        typed instead of living in a separate window.
        """
        targets = self.modules_of_type(module_type)
        if not targets:
            return 0, StepDiff((), 0, 0)
        updates = {
            module_id: apply_field_edit(
                module_type, self._node(module_id).params, key, text
            )
            for module_id in targets
        }
        before = self.project.copy()

        def mutate(project: ScheduleProject) -> None:
            for node in project.modules:
                if node.id in updates:
                    node.params = updates[node.id]

        self.document.apply(f"{module_type} 전체 {key} 변경", mutate)
        return len(targets), diff_projects(before, self.project)

    def current_limit_breaches(self) -> tuple[ValidationRow, ...]:
        """Steps whose current exceeds the binding cell/equipment limit."""
        return tuple(
            row for row in self.validation_rows() if row.code == "CURRENT_LIMIT"
        )

    # ---------------------------------------------------------- procedure

    def procedure(self) -> ProcedureView:
        return build_procedure(self.project)

    def step_rows(self) -> tuple[dict[str, Any], ...]:
        return procedure_step_rows(self.procedure())

    def display_step_rows(self) -> tuple[dict[str, str], ...]:
        """The expanded step table with every number already formatted."""
        capacity = self.project.cell_profile.nominal_capacity_mAh
        rows: list[dict[str, str]] = []
        for row in self.step_rows():
            current = ""
            if row["c_rate"] is not None:
                current = (
                    f"{units.format_c_rate(row['c_rate'])} "
                    f"({units.format_current_mA(row['c_rate'] * capacity)})"
                )
            voltage_parts: list[str] = []
            if row["voltage_v"] is not None:
                voltage_parts.append(f"한계 {units.format_voltage(row['voltage_v'])}")
            if row["end_voltage_v"] is not None:
                voltage_parts.append(f"종료 {units.format_voltage(row['end_voltage_v'])}")
            end_parts: list[str] = []
            if row["end_time_s"] is not None:
                end_parts.append(units.format_duration_ko(row["end_time_s"]))
            if row["dod_percent"] is not None:
                end_parts.append(f"DOD {row['dod_percent']:g}%")
            loop = ""
            if row["loop_goto_step"] is not None:
                loop = f"→ {row['loop_goto_step']} × {row['loop_count']}"
            rows.append(
                {
                    "number": str(row["number"]),
                    "phase": row["phase"],
                    "type": row["step_type"],
                    "mode": row["mode"],
                    "current": current,
                    "voltage": " · ".join(voltage_parts),
                    "end": " · ".join(end_parts),
                    "loop": loop,
                }
            )
        return tuple(rows)

    def move(self, module_id: str, delta: int) -> bool:
        moved = False

        def mutate(project: ScheduleProject) -> None:
            nonlocal moved
            moved = move_module(project, module_id, delta)

        self.document.apply(
            f"{module_id} 순서 이동 ({'위로' if delta < 0 else '아래로'})", mutate
        )
        return moved

    def reorder(self, ordered_ids: list[str]) -> None:
        def mutate(project: ScheduleProject) -> None:
            reorder_modules(project, ordered_ids)

        self.document.apply("구간 순서 변경", mutate)

    def detach(self, module_id: str) -> None:
        """Turn a preset into editable steps (explicit, never automatic)."""

        def mutate(project: ScheduleProject) -> None:
            detach_module(project, module_id)

        self.document.apply(f"{module_id} 개별 스텝으로 분리", mutate)

    # ----------------------------------------------------------- validate

    def validation_rows(self) -> tuple[ValidationRow, ...]:
        view = self.procedure()
        rows: list[ValidationRow] = []

        for phase in view.phases:
            if phase.error:
                rows.append(
                    ValidationRow(
                        "error", "MODULE_EXPAND", phase.error,
                        f"{phase.position}. {phase.title}", phase.module_id,
                        remediation="이 구간의 입력값을 확인하세요.",
                    )
                )

        result = validate_project(self.project, purpose="preview")
        for issue in result.issues:
            module_id: str | None = None
            step_number: int | None = None
            location = "프로젝트"
            if issue.object_id and issue.object_id.startswith("step:"):
                step_number = int(issue.object_id.split(":", 1)[1])
                phase = view.phase_for_step(step_number)
                module_id = phase.module_id if phase else None
                location = (
                    f"{step_number}번 스텝" + (f" · {phase.title}" if phase else "")
                )
            elif issue.object_id:
                module_id = issue.object_id
                phase = next(
                    (p for p in view.phases if p.module_id == issue.object_id), None
                )
                location = f"{phase.position}. {phase.title}" if phase else issue.object_id
            rows.append(
                ValidationRow(
                    issue.severity, issue.code, issue.message, location,
                    module_id, issue.field, step_number, issue.remediation or "",
                )
            )

        for node in self.project.modules:
            form = self.form(node.id)
            phase = next((p for p in view.phases if p.module_id == node.id), None)
            location = f"{phase.position}. {phase.title}" if phase else node.id
            for form_field in form.fields:
                for issue in form_field.issues:
                    rows.append(
                        ValidationRow(
                            issue.severity,
                            issue.code or "FIELD",
                            issue.message,
                            f"{location} · {form_field.label}",
                            node.id,
                            form_field.key,
                            remediation="프로토콜 탭에서 값을 조정하세요.",
                        )
                    )

        order = {"error": 0, "warning": 1}
        rows.sort(key=lambda row: (order.get(row.severity, 2), row.location))
        return tuple(_dedupe_rows(rows))

    def unverified_notes(self) -> tuple[str, ...]:
        """Which parts of this schedule are not yet proven, in plain Korean."""
        notes: list[str] = []
        for node in self.project.modules:
            spec = get_module_spec(node.module_type)
            if spec is None:
                continue
            label = VERIFICATION_LABELS_KO.get(spec.trust_status)
            status = label or TRUST_LABELS_KO.get(spec.trust_status, spec.trust_status)
            notes.append(f"{node.id} · {spec.title}: {status}")
            notes.extend(f"    - {limit}" for limit in spec.limitations)
        return tuple(notes)

    # ------------------------------------------------------------- review

    def record_ctspro_review(
        self, *, reviewer: str, sha256: str = "", reviewed_at: str = ""
    ) -> None:
        def mutate(project: ScheduleProject) -> None:
            project.review.ctspro_reviewed = True
            project.review.ctspro_reviewer = reviewer
            project.review.reviewed_sha256 = sha256
            project.review.ctspro_reviewed_at = reviewed_at

        self.document.apply("CTSPro 확인 기록", mutate)

    def record_equipment_approval(self, *, approver: str, approved_at: str = "") -> None:
        def mutate(project: ScheduleProject) -> None:
            project.review.equipment_approved = True
            project.review.equipment_approved_by = approver
            project.review.equipment_approved_at = approved_at

        self.document.apply("장비 실행 승인 기록", mutate)

    def clear_approvals(self) -> None:
        def mutate(project: ScheduleProject) -> None:
            project.review.ctspro_reviewed = False
            project.review.equipment_approved = False

        self.document.apply("승인 기록 해제", mutate)

    # -------------------------------------------------------------- files

    def open_path(self, path: Path) -> tuple[str, ...]:
        autosave_dir = self.document.autosave_dir
        # Drop the outgoing document's recovery copy; it is being replaced, not
        # lost, so it must not resurface at the next launch.
        self.document.clear_autosave()
        self.document = ProjectDocument.open(Path(path), autosave_dir=autosave_dir)
        return self.document.load_repairs

    def new_document(self) -> None:
        autosave_dir = self.document.autosave_dir
        self.document.clear_autosave()
        self.document = ProjectDocument.new(autosave_dir=autosave_dir)

    # ------------------------------------------------------------ helpers

    def _node(self, module_id: str) -> ModuleNode:
        node = next((n for n in self.project.modules if n.id == module_id), None)
        if node is None:
            raise ValueError(f"알 수 없는 구간입니다: {module_id}")
        return node

    def _next_id(self, module_type: str) -> str:
        existing = {node.id for node in self.project.modules}
        index = 1
        while f"{module_type}_{index}" in existing:
            index += 1
        return f"{module_type}_{index}"


def _dedupe_rows(rows: list[ValidationRow]) -> list[ValidationRow]:
    seen: set[tuple[str, str, str, str | None]] = set()
    unique: list[ValidationRow] = []
    for row in rows:
        key = (row.code, row.message, row.location, row.module_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


__all__ = [
    "ModuleRow",
    "SetupField",
    "TRUST_LABELS_KO",
    "ValidationRow",
    "WorkspaceModel",
]
