"""Cell-specific schedule batches with explicit, manually entered reference capacity.

This is deliberately a one-reference-per-file workflow. A Formation recipe and a
Cycle recipe that use different capacities must be exported as two batches.
The batch writer delegates each artifact to the existing release-gated writers.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .exporting import ExportBlocked, export_preview, export_review_candidate
from .ir.project import ReviewState, ScheduleProject
from .modules.base import get_module_class
from .release import evaluate_release

PHASE_BASES = {
    "formation": ("manual_reference", "design"),
    "derating": ("manual_reference", "design", "activation_discharge"),
    "cycle": ("manual_reference", "design", "derating_discharge"),
}
BASIS_FIELD = {
    "design": "designCapacityMah",
    "activation_discharge": "activationCapacityMah",
    "derating_discharge": "deratingCapacityMah",
}
CELL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,49}$")
MAX_CELLS = 100
MAX_MATRIX_VARIANTS = 25
MAX_BATCH_OUTPUTS = 500
RATE_MODULE_TYPES = frozenset({"formation", "cycle_life", "insitu_cycle"})
RATE_FIELDS = frozenset({"charge_c_rate", "discharge_c_rate"})


@dataclass(frozen=True)
class RateVariant:
    variant_id: str
    charge_rate: float
    discharge_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "variantId": self.variant_id,
            "chargeRate": self.charge_rate,
            "dischargeRate": self.discharge_rate,
        }


@dataclass(frozen=True)
class PreparedCell:
    cell_id: str
    capacity_mAh: float
    project: ScheduleProject
    row: dict[str, Any]
    output_parts: tuple[str, ...]


@dataclass(frozen=True)
class CellBatchPlan:
    phase: str
    basis: str
    kind: str
    token: str
    matrix: tuple[dict[str, Any], ...]
    rows: tuple[dict[str, Any], ...]
    cells: tuple[PreparedCell, ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors and all(row["allowed"] for row in self.rows)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "phase": self.phase,
            "basis": self.basis,
            "kind": self.kind,
            "token": self.token,
            "matrix": list(self.matrix),
            "rows": list(self.rows),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "note": "각 셀의 기준용량을 직접 입력했습니다. 측정 결과 파일과 자동 대조되지는 않았습니다.",
        }


def _capacity(value: Any, label: str) -> float:
    if isinstance(value, bool) or value is None or str(value).strip() == "":
        raise ValueError(f"{label} 값이 없습니다.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}은(는) 숫자여야 합니다.") from exc
    if not math.isfinite(result) or not 0 < result <= 1_000_000:
        raise ValueError(f"{label}은(는) 0 초과 1,000,000 mAh 이하여야 합니다.")
    return result


def _rate(value: Any, label: str) -> float:
    if isinstance(value, bool) or value is None or str(value).strip() == "":
        raise ValueError(f"{label} 값이 없습니다.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}은(는) 숫자여야 합니다.") from exc
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{label}은(는) 유한한 양수여야 합니다.")
    return result


def _parse_matrix(matrix: Any, errors: list[str]) -> tuple[RateVariant, ...]:
    if matrix is None:
        return ()
    if not isinstance(matrix, list) or not 1 <= len(matrix) <= MAX_MATRIX_VARIANTS:
        errors.append(f"C-rate 조합은 1개 이상 {MAX_MATRIX_VARIANTS}개 이하여야 합니다.")
        return ()
    variants: list[RateVariant] = []
    seen: set[tuple[float, float]] = set()
    for index, raw in enumerate(matrix, start=1):
        if not isinstance(raw, dict) or set(raw) != {"chargeRate", "dischargeRate"}:
            errors.append(f"C-rate 조합 {index}는 chargeRate와 dischargeRate만 가져야 합니다.")
            continue
        try:
            charge_rate = _rate(raw["chargeRate"], f"C-rate 조합 {index} 충전율")
            discharge_rate = _rate(raw["dischargeRate"], f"C-rate 조합 {index} 방전율")
        except ValueError as exc:
            errors.append(str(exc))
            continue
        pair = (charge_rate, discharge_rate)
        if pair in seen:
            errors.append(f"C-rate 조합 {index}가 중복됩니다.")
            continue
        seen.add(pair)
        variants.append(RateVariant(f"v{index:02d}", charge_rate, discharge_rate))
    return tuple(variants)


def _matrix_compatibility_errors(project: ScheduleProject) -> list[str]:
    supported_count = 0
    errors: list[str] = []

    def check(module_id: str, module_type: str, params: Any) -> None:
        nonlocal supported_count
        params = params if isinstance(params, dict) else {}
        if module_type in RATE_MODULE_TYPES:
            supported_count += 1
            return
        if module_type == "sequence":
            children = params.get("children", [])
            if not isinstance(children, list):
                return
            for child in children:
                if not isinstance(child, dict):
                    continue
                child_id = str(child.get("id") or "(ID 없음)")
                child_type = str(child.get("module_type") or "")
                if child_type == "sequence":
                    errors.append(f"{module_id}/{child_id}: 중첩 sequence는 C-rate 조합을 지원하지 않습니다.")
                    continue
                check(f"{module_id}/{child_id}", child_type, child.get("params", {}))
            return
        cls = get_module_class(module_type)
        declared = set(getattr(cls, "__dataclass_fields__", ())) if cls else set()
        if RATE_FIELDS & (declared | set(params)):
            errors.append(
                f"{module_id}({module_type})는 배치 C-rate 조합을 지원하지 않습니다. "
                "Formation, Cycle, In-situ의 선언된 충·방전율만 변경할 수 있습니다."
            )

    for node in project.modules:
        check(node.id, node.module_type, node.params)
    if not supported_count:
        errors.append("C-rate 조합을 적용할 Formation, Cycle 또는 In-situ 모듈이 없습니다.")
    return errors


def _apply_variant(project: ScheduleProject, variant: RateVariant) -> None:
    def apply(params: dict[str, Any]) -> None:
        params["charge_c_rate"] = variant.charge_rate
        params["discharge_c_rate"] = variant.discharge_rate

    for node in project.modules:
        if node.module_type in RATE_MODULE_TYPES:
            apply(node.params)
        elif node.module_type == "sequence":
            children = node.params.get("children", [])
            if not isinstance(children, list):
                continue
            for child in children:
                if not isinstance(child, dict) or child.get("module_type") not in RATE_MODULE_TYPES:
                    continue
                params = child.get("params")
                if isinstance(params, dict):
                    apply(params)


def _token(
    project: ScheduleProject, phase: str, basis: str, kind: str,
    rows: list[Any], matrix: tuple[RateVariant, ...], matrix_requested: bool,
) -> str:
    body = {
        "project": project.to_dict(), "phase": phase, "basis": basis, "kind": kind,
        "rows": rows,
        "matrix": [variant.to_dict() for variant in matrix] if matrix_requested else None,
    }
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def plan_cell_batch(
    project: ScheduleProject, *, phase: str, basis: str, kind: str, rows: Any,
    matrix: Any = None,
) -> CellBatchPlan:
    errors: list[str] = []
    warnings = ["파일당 기준용량 하나를 모든 C-rate 전류에 적용합니다. 다른 기준용량이 필요한 단계는 별도 배치로 만드세요."]
    if phase not in PHASE_BASES:
        errors.append("실험 단계는 formation, derating, cycle 중 하나여야 합니다.")
    elif basis not in PHASE_BASES[phase]:
        errors.append(f"{phase} 단계에서 {basis} 용량 기준을 사용할 수 없습니다.")
    if kind not in {"preview", "review_candidate"}:
        errors.append("배치는 스텝 미리보기 또는 재열기 전용 SCH만 생성할 수 있습니다.")
    matrix_requested = matrix is not None
    variants = _parse_matrix(matrix, errors)
    if matrix_requested:
        errors.extend(_matrix_compatibility_errors(project))
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_CELLS:
        errors.append(f"셀은 1개 이상 {MAX_CELLS}개 이하로 입력하세요.")
        rows = []
    elif matrix_requested and variants and len(rows) * len(variants) > MAX_BATCH_OUTPUTS:
        errors.append(f"셀×C-rate 조합 출력은 {MAX_BATCH_OUTPUTS}개 이하여야 합니다.")
    module_types = {node.module_type for node in project.modules}
    for node in project.modules:
        if node.module_type == "sequence" and isinstance(node.params.get("children"), list):
            module_types.update(
                str(child.get("module_type", ""))
                for child in node.params["children"] if isinstance(child, dict)
            )
    if phase != "formation" and "formation" in module_types:
        errors.append("Formation 모듈이 포함돼 있습니다. 단계별 기준 용량이 다르면 레시피를 분리하세요.")
    if phase == "formation" and module_types & {"cycle_life", "insitu_cycle", "qpeed", "qc", "qc_charge"}:
        errors.append("Formation 배치에 수명/급속충전 모듈이 섞여 있습니다. 레시피를 분리하세요.")

    global_errors = bool(errors)
    global_blockers = tuple(errors)
    seen: set[str] = set()
    prepared: list[PreparedCell] = []
    display_rows: list[dict[str, Any]] = []
    for number, raw in enumerate(rows, start=1):
        row_errors: list[str] = []
        if not isinstance(raw, dict):
            raw = {}
        cell_id = str(raw.get("cellId", "")).strip()
        if not CELL_ID.fullmatch(cell_id):
            row_errors.append("셀 ID는 영문/숫자로 시작하는 1–50자 영문·숫자·_·-만 허용합니다.")
        elif cell_id.casefold() in seen:
            row_errors.append("셀 ID가 중복됩니다.")
        seen.add(cell_id.casefold())
        design = None
        selected = None
        if basis == "manual_reference":
            if set(raw) - {"cellId", "referenceCapacityMah"}:
                row_errors.append("셀 ID와 기준용량 두 열만 입력하세요. 이전 4열 형식은 사용할 수 없습니다.")
            try:
                selected = _capacity(raw.get("referenceCapacityMah"), "기준용량")
            except ValueError as exc:
                row_errors.append(str(exc))
        else:
            try:
                design = _capacity(raw.get("designCapacityMah"), "설계용량")
            except ValueError as exc:
                row_errors.append(str(exc))
            selected = design
            if basis != "design" and basis in BASIS_FIELD:
                try:
                    selected = _capacity(raw.get(BASIS_FIELD[basis]), "선택한 방전용량")
                except ValueError as exc:
                    selected = None
                    row_errors.append(str(exc))
        row_variants: tuple[RateVariant | None, ...] = variants if matrix_requested else (None,)
        if matrix_requested and not variants:
            row_variants = (None,)
        for variant in row_variants:
            clone: ScheduleProject | None = None
            option_blockers: list[str] = []
            max_current = 0.0
            fixed_currents = 0
            if selected is not None and not row_errors and not global_errors:
                clone = project.copy()
                if variant is not None:
                    _apply_variant(clone, variant)
                suffix = f"__{variant.variant_id}" if variant else ""
                clone.name = f"{project.name}__{cell_id}{suffix}"
                clone.cell_profile.nominal_capacity_mAh = selected
                clone.review = ReviewState()  # approval never follows changed capacity/rates
                try:
                    steps = clone.expand_steps()
                    for step in steps:
                        if step.current_mA is not None:
                            fixed_currents += 1
                            max_current = max(max_current, abs(step.current_mA))
                        elif step.c_rate is not None:
                            max_current = max(max_current, abs(step.c_rate * selected))
                        if step.cv_cutoff_mA is not None:
                            fixed_currents += 1
                    option = evaluate_release(clone).option(kind)
                    option_blockers.extend(option.blockers if option else ["내보내기 종류를 확인할 수 없습니다."])
                except (ValueError, TypeError) as exc:
                    option_blockers.append(f"스텝 생성 실패: {exc}")
            variant_errors = [*row_errors, *option_blockers]
            variant_label = f" / {variant.variant_id}" if variant else ""
            if variant_errors:
                errors.append(
                    f"{number}행 {cell_id or '(ID 없음)'}{variant_label}: "
                    f"{'; '.join(variant_errors)}"
                )
            display = {
                "cellId": cell_id,
                "variantId": variant.variant_id if variant else None,
                "chargeRate": variant.charge_rate if variant else None,
                "dischargeRate": variant.discharge_rate if variant else None,
                "chargeCurrentmA": round(selected * variant.charge_rate, 6) if selected is not None and variant else None,
                "dischargeCurrentmA": round(selected * variant.discharge_rate, 6) if selected is not None and variant else None,
                "designCapacityMah": design,
                "selectedCapacityMah": selected,
                "basis": basis,
                "oneCmA": selected,
                "maxCurrentmA": round(max_current, 6) if clone is not None else None,
                "fixedCurrentSteps": fixed_currents,
                "allowed": not global_errors and not variant_errors,
                "blockers": [*global_blockers, *variant_errors],
                "evidence": "manual_reference_unverified" if basis == "manual_reference" else "manual_entry_unverified",
            }
            display_rows.append(display)
            if clone is not None:
                output_parts = (cell_id, variant.variant_id) if variant else (cell_id,)
                prepared.append(PreparedCell(cell_id, selected, clone, display, output_parts))
    try:
        token = _token(project, phase, basis, kind, rows, variants, matrix_requested)
    except (TypeError, ValueError):
        token = ""
        errors.append("배치 입력을 직렬화할 수 없습니다.")
    return CellBatchPlan(
        phase, basis, kind, token, tuple(variant.to_dict() for variant in variants),
        tuple(display_rows), tuple(prepared),
        tuple(dict.fromkeys(errors)), tuple(warnings),
    )


def export_cell_batch(plan: CellBatchPlan, out_dir: Path, *, token: str) -> list[Path]:
    if not plan.ok or not token or token != plan.token:
        raise ExportBlocked("배치 미리보기와 현재 입력이 다르거나 차단 항목이 있습니다. 다시 미리보세요.")
    target = Path(out_dir).expanduser()
    if not target.is_absolute() or not target.name or not target.parent.is_dir() or target.exists():
        raise ExportBlocked("출력 위치는 존재하지 않는 새 폴더의 절대 경로여야 합니다.")
    stage = Path(tempfile.mkdtemp(prefix=f".{target.name}.pending-", dir=target.parent))
    paths: list[Path] = []
    try:
        manifest_rows = []
        for prepared in plan.cells:
            cell_dir = stage.joinpath(*prepared.output_parts)
            cell_dir.mkdir(parents=True)
            if plan.kind == "preview":
                result = export_preview(prepared.project, cell_dir)
            else:
                result = export_review_candidate(prepared.project, cell_dir)
            files = []
            for path in result.paths:
                files.append({
                    "path": str(path.relative_to(stage)),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                })
                paths.append(target / path.relative_to(stage))
            manifest_rows.append({**prepared.row, "files": files})
        manifest = stage / "batch-manifest.json"
        manifest.write_text(json.dumps({
            "schema": "pne_scheduler.cell_batch/v2" if plan.matrix else "pne_scheduler.cell_batch/v1",
            "phase": plan.phase,
            "basis": plan.basis,
            "kind": plan.kind,
            "matrix": list(plan.matrix) if plan.matrix else None,
            "planDigest": plan.token,
            "equipmentExecutable": False,
            "evidence": "manual_reference_unverified" if plan.basis == "manual_reference" else "manual_entry_unverified",
            "cells": manifest_rows,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        paths.append(target / manifest.name)
        if target.exists():
            raise ExportBlocked("출력 폴더가 생성되었습니다. 기존 내용을 덮어쓰지 않습니다.")
        os.rename(stage, target)
        return paths
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise
