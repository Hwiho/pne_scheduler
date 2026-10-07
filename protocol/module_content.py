"""Read-only, composable views of a module's actual schedule steps.

The editor keeps presets and sequence children as modules.  This view expands
one selected module for inspection without changing that representation: a
sequence still exposes its retained child nodes, while its step list shows the
same LOOP-rebased fragment that the schedule engine will compose.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from ..edit.steps import step_fields
from ..ir.composer import compose_module_steps
from ..ir.project import ModuleNode, ScheduleProject
from ..ir.step_intent import StepIntent
from ..modules.catalog import get_module_spec
from ..report.summary import module_headline
from ..spec import units


STEP_TITLES_KO: dict[str, str] = {
    "charge": "충전",
    "discharge": "방전",
    "rest": "휴지",
    "ocv": "개방전압 측정",
    "impedance": "임피던스 측정",
    "pattern": "패턴 실행",
    "balance": "밸런싱",
    "cycle": "사이클 구분",
    "loop": "반복 제어",
    "end": "종료",
}


@dataclass(frozen=True, slots=True)
class ModuleContentChild:
    index: int
    node: ModuleNode
    title: str
    summary: str
    repeat_count: int
    step_count: int


@dataclass(frozen=True, slots=True)
class ModuleContent:
    module_id: str
    child_index: int | None
    node: ModuleNode
    title: str
    customized: bool
    steps: tuple[dict[str, Any], ...]
    children: tuple[ModuleContentChild, ...]


def derive_module_content(
    project: ScheduleProject,
    module_id: str,
    child_index: int | None = None,
) -> ModuleContent:
    """Expand a root module or one retained sequence child without mutation."""
    root = next((node for node in project.modules if node.id == module_id), None)
    if root is None:
        raise ValueError(f"알 수 없는 구간입니다: {module_id}")

    selected = root
    if child_index is not None:
        if root.module_type != "sequence":
            raise ValueError("반복 블록의 내부 모듈만 선택할 수 있습니다.")
        children = _child_nodes(root)
        if not 0 <= child_index < len(children):
            raise ValueError("블록 내부 모듈 위치가 잘못되었습니다.")
        selected = children[child_index]

    steps = _step_rows(selected, project)
    children_view: tuple[ModuleContentChild, ...] = ()
    if child_index is None and root.module_type == "sequence":
        children_view = tuple(
            ModuleContentChild(
                index=index,
                node=child,
                title=_module_title(child),
                summary=_module_summary(child, project),
                repeat_count=_repeat_count(child),
                step_count=len(_expanded_without_end(child, project)),
            )
            for index, child in enumerate(_child_nodes(root))
        )

    return ModuleContent(
        module_id=module_id,
        child_index=child_index,
        node=selected,
        title=_module_title(selected),
        customized=selected.module_type == "custom_steps",
        steps=steps,
        children=children_view,
    )


def _child_nodes(node: ModuleNode) -> list[ModuleNode]:
    raw_children = node.params.get("children", [])
    if not isinstance(raw_children, list):
        raise ValueError("블록 내부 모듈 형식이 잘못되었습니다.")
    try:
        return [ModuleNode.from_dict(dict(raw)) for raw in raw_children]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("블록 내부 모듈 형식이 잘못되었습니다.") from exc


def _expanded_without_end(
    node: ModuleNode, project: ScheduleProject
) -> list[StepIntent]:
    # The composer resolves fragment-local LOOP targets exactly as it does for
    # export. append_end=False means the view never invents or duplicates END;
    # a trailing END emitted by a preset is normalized away by the composer.
    return compose_module_steps([node], project.cell_profile, append_end=False)


def _step_rows(
    node: ModuleNode, project: ScheduleProject
) -> tuple[dict[str, Any], ...]:
    capacity = project.cell_profile.nominal_capacity_mAh
    rows: list[dict[str, Any]] = []
    for index, step in enumerate(_expanded_without_end(node, project)):
        raw = step.to_dict()
        fields = step_fields(raw, nominal_capacity_mAh=capacity)
        rows.append(
            {
                "index": index,
                "number": index + 1,
                "stepType": step.step_type,
                "mode": step.mode or step.step_type.upper()
                if step.step_type in {"cycle", "loop"}
                else step.mode or "",
                "title": _step_title(step),
                "summary": _step_summary(step, capacity),
                "fields": [
                    {
                        "key": field.key,
                        "label": field.label,
                        "kind": field.kind,
                        "text": field.text,
                        "numericValue": (
                            raw[field.key] if isinstance(raw.get(field.key), (int, float))
                            and not isinstance(raw[field.key], bool)
                            and math.isfinite(raw[field.key]) else None
                        ),
                        "detail": field.detail,
                    }
                    for field in fields
                ],
            }
        )
    return tuple(rows)


def _step_title(step: StepIntent) -> str:
    title = STEP_TITLES_KO.get(step.step_type, step.step_type)
    return f"{title} ({step.mode})" if step.mode else title


def _step_summary(step: StepIntent, capacity_mAh: float) -> str:
    parts: list[str] = []
    if step.c_rate is not None:
        parts.append(
            f"{units.format_c_rate(step.c_rate)} "
            f"({units.format_current_mA(step.c_rate * capacity_mAh)})"
        )
    elif step.current_mA is not None:
        parts.append(units.format_current_mA(step.current_mA))
    if step.voltage_v is not None:
        parts.append(f"목표 {units.format_voltage(step.voltage_v)}")
    if step.end_voltage_v is not None:
        parts.append(f"종료 {units.format_voltage(step.end_voltage_v)}")
    if step.end_capacity_fraction is not None:
        parts.append(
            f"용량 종료: 기준용량의 {units.format_percent(step.end_capacity_fraction * 100)} "
            f"({step.end_capacity_fraction * capacity_mAh:.4g} mAh)"
        )
    if step.end_time_s is not None:
        competing = step.step_type in {"charge", "discharge"} and any(value is not None for value in (step.end_voltage_v, step.end_capacity_fraction, step.cv_cutoff_c_rate, step.dod_percent))
        parts.append(("시간 제한 최대 " if competing else "") + units.format_duration_ko(step.end_time_s))
    if step.dod_percent is not None:
        parts.append(f"DOD {step.dod_percent:g}%")
    if step.step_type == "loop":
        if step.loop_goto_step is not None:
            parts.append(f"{step.loop_goto_step}번으로")
        if step.loop_count is not None:
            parts.append(f"{step.loop_count}회 반복")
    if not parts and step.step_type == "cycle":
        parts.append("사이클 제어 스텝")
    return " · ".join(parts) or step.label


def _module_title(node: ModuleNode) -> str:
    if node.module_type == "sequence":
        return str(node.params.get("name") or "반복 블록")
    if node.module_type == "primitive":
        from ..modules.primitive import PrimitiveModule

        return PrimitiveModule.from_params(node.params).title()
    spec = get_module_spec(node.module_type)
    return spec.title if spec else node.module_type


def _module_summary(node: ModuleNode, project: ScheduleProject) -> str:
    try:
        return module_headline(node, project.cell_profile)
    except (TypeError, ValueError):
        return f"{len(_expanded_without_end(node, project))}개 스텝"


def _repeat_count(node: ModuleNode) -> int:
    value = node.params.get("repeat_count", 1)
    return value if isinstance(value, int) and not isinstance(value, bool) else 1


__all__ = [
    "ModuleContent",
    "ModuleContentChild",
    "derive_module_content",
]
