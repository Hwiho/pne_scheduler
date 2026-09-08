"""Tolerant ``.schproj`` loading.

A project with a bad value must still open — otherwise the user cannot fix
the very thing that is wrong.  This loader repairs what it can, records every
repair in plain Korean, and leaves everything it cannot repair in place for
the validator to report.  Nothing here relaxes an export gate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..schema import DEFAULT_SCH_VERSION
from .cell_profile import CellProfile
from .equipment_profile import EquipmentProfile
from .project import (
    ModuleConnection,
    ModuleNode,
    ReviewState,
    SCHPROJ_SCHEMA_V1,
    ScheduleProject,
)

PLACEHOLDER_CAPACITY_mAh = 24.0
PLACEHOLDER_V_MAX = 4.2
PLACEHOLDER_V_MIN = 2.5


class ProjectLoadError(ValueError):
    """The file could not be read as a project at all (not a repairable value)."""


@dataclass(frozen=True, slots=True)
class ProjectLoad:
    project: ScheduleProject
    repairs: tuple[str, ...] = ()
    migrated_from: str | None = None

    @property
    def needs_attention(self) -> bool:
        return bool(self.repairs)


def load_project_lenient(path: Path) -> ProjectLoad:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProjectLoadError(f"파일을 찾을 수 없습니다: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ProjectLoadError(
            f"JSON 형식이 아닙니다 ({exc.lineno}행 {exc.colno}열): {exc.msg}"
        ) from exc
    if not isinstance(raw, dict):
        raise ProjectLoadError("프로젝트 파일의 최상위는 객체(JSON object)여야 합니다.")
    return repair_project_dict(raw)


def repair_project_dict(raw: dict[str, Any]) -> ProjectLoad:
    """Coerce a project dict into a loadable project, listing every repair."""
    repairs: list[str] = []
    schema = str(raw.get("schema") or SCHPROJ_SCHEMA_V1)
    migrated_from = schema if schema == SCHPROJ_SCHEMA_V1 else None

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        name = "이름 없는 프로젝트"
        repairs.append("프로젝트 이름이 없어 '이름 없는 프로젝트' 로 채웠습니다.")

    cell, cell_repairs = _repair_cell(raw.get("cell_profile"))
    repairs.extend(cell_repairs)

    try:
        sch_version = int(raw.get("sch_version", DEFAULT_SCH_VERSION))
    except (TypeError, ValueError):
        sch_version = DEFAULT_SCH_VERSION
        repairs.append("sch_version 을 읽을 수 없어 기본값으로 되돌렸습니다.")

    modules, module_repairs = _repair_modules(raw.get("modules"))
    repairs.extend(module_repairs)

    known_ids = {node.id for node in modules}
    connections: list[ModuleConnection] = []
    seen: set[tuple[str, str]] = set()
    for entry in raw.get("connections") or []:
        if not isinstance(entry, dict):
            repairs.append("연결 정보 하나가 객체가 아니어서 제거했습니다.")
            continue
        source = str(entry.get("source_id", ""))
        target = str(entry.get("target_id", ""))
        if source not in known_ids or target not in known_ids:
            repairs.append(f"없는 모듈을 가리키는 연결을 제거했습니다: {source} → {target}")
            continue
        if source == target:
            repairs.append(f"자기 자신을 가리키는 연결을 제거했습니다: {source}")
            continue
        if (source, target) in seen:
            repairs.append(f"중복 연결을 제거했습니다: {source} → {target}")
            continue
        seen.add((source, target))
        connections.append(ModuleConnection(source, target))

    equipment_raw = raw.get("equipment")
    equipment: EquipmentProfile | None = None
    if isinstance(equipment_raw, dict) and equipment_raw.get("unit"):
        try:
            equipment = EquipmentProfile.from_dict(equipment_raw)
        except TypeError:
            equipment = None
            repairs.append("장비 프로파일을 읽을 수 없어 비웠습니다. 설정 탭에서 다시 지정하세요.")
    elif migrated_from is not None:
        repairs.append(
            "이전 버전(v1) 파일입니다. 장비 프로파일이 없어 비어 있습니다 — "
            "설정 탭에서 PNE 장비를 지정해야 내보내기가 열립니다."
        )

    review_raw = raw.get("review")
    review = ReviewState.from_dict(review_raw) if isinstance(review_raw, dict) else ReviewState()

    project = ScheduleProject(
        name=name,
        cell_profile=cell,
        sch_version=sch_version,
        modules=modules,
        connections=connections,
        equipment=equipment,
        review=review,
    )

    # From here on the module list order is what runs, so fold any graph-editor
    # wiring into it once, at the boundary.
    from .procedure import adopt_connection_order

    try:
        if adopt_connection_order(project) and connections:
            repairs.append(
                "모듈 연결을 실행 순서대로 정리했습니다 (분기가 있었다면 순서대로 폈습니다)."
            )
    except ValueError as exc:
        repairs.append(f"모듈 연결을 정리할 수 없어 목록 순서를 사용합니다: {exc}")

    return ProjectLoad(project, tuple(repairs), migrated_from)


def _repair_cell(raw: Any) -> tuple[CellProfile, list[str]]:
    repairs: list[str] = []
    data = raw if isinstance(raw, dict) else {}
    if not isinstance(raw, dict):
        repairs.append("셀 정보가 없어 기본값(24 mAh, 2.5–4.2 V)으로 채웠습니다.")

    def number(key: str, fallback: float) -> float:
        value = data.get(key, fallback)
        try:
            return float(value)
        except (TypeError, ValueError):
            repairs.append(f"셀 항목 {key} 을(를) 숫자로 읽을 수 없어 {fallback:g} 로 되돌렸습니다.")
            return fallback

    capacity = number("nominal_capacity_mAh", PLACEHOLDER_CAPACITY_mAh)
    if capacity <= 0:
        repairs.append(
            f"셀 용량이 {capacity:g} mAh 여서 {PLACEHOLDER_CAPACITY_mAh:g} mAh 로 되돌렸습니다. "
            "실제 값으로 고쳐야 C-rate 계산이 맞습니다."
        )
        capacity = PLACEHOLDER_CAPACITY_mAh

    v_min = number("v_min", PLACEHOLDER_V_MIN)
    v_max = number("v_max", PLACEHOLDER_V_MAX)
    if v_max <= v_min:
        repairs.append(
            f"상한 전압({v_max:g} V)이 하한({v_min:g} V) 이하여서 {v_min + 0.1:g} V 로 올렸습니다."
        )
        v_max = v_min + 0.1

    max_current = data.get("max_current_mA")
    if max_current is not None:
        try:
            max_current = float(max_current)
            if max_current <= 0:
                repairs.append("셀 최대 전류가 0 이하여서 비웠습니다.")
                max_current = None
        except (TypeError, ValueError):
            repairs.append("셀 최대 전류를 숫자로 읽을 수 없어 비웠습니다.")
            max_current = None

    formation = data.get("formation_capacity_mAh")
    if formation is not None:
        try:
            formation = float(formation)
        except (TypeError, ValueError):
            repairs.append("화성 용량을 숫자로 읽을 수 없어 비웠습니다.")
            formation = None

    return (
        CellProfile(
            nominal_capacity_mAh=capacity,
            v_max=v_max,
            v_min=v_min,
            max_current_mA=max_current,
            formation_capacity_mAh=formation,
        ),
        repairs,
    )


def _repair_modules(raw: Any) -> tuple[list[ModuleNode], list[str]]:
    repairs: list[str] = []
    if not isinstance(raw, list):
        if raw is not None:
            repairs.append("모듈 목록이 배열이 아니어서 비웠습니다.")
        return [], repairs

    modules: list[ModuleNode] = []
    used_ids: set[str] = set()
    for position, entry in enumerate(raw, start=1):
        if not isinstance(entry, dict):
            repairs.append(f"{position}번째 모듈이 객체가 아니어서 제거했습니다.")
            continue
        module_type = str(entry.get("module_type") or "").strip()
        if not module_type:
            repairs.append(f"{position}번째 모듈에 종류가 없어 제거했습니다.")
            continue
        identifier = str(entry.get("id") or "").strip() or f"{module_type}_{position}"
        if identifier in used_ids:
            original = identifier
            suffix = 2
            while f"{identifier}_{suffix}" in used_ids:
                suffix += 1
            identifier = f"{identifier}_{suffix}"
            repairs.append(f"모듈 ID 가 중복되어 {original} 을(를) {identifier} 로 바꿨습니다.")
        used_ids.add(identifier)
        params = entry.get("params")
        if not isinstance(params, dict):
            if params is not None:
                repairs.append(f"{identifier} 의 설정값이 객체가 아니어서 기본값으로 되돌렸습니다.")
            params = {}
        modules.append(ModuleNode(identifier, module_type, dict(params)))
    return modules, repairs


__all__ = [
    "ProjectLoad",
    "ProjectLoadError",
    "load_project_lenient",
    "repair_project_dict",
]
