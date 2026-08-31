"""Bulk-edit module parameters in a .schproj project."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..ir.project import ModuleNode, ScheduleProject
from ..modules.base import get_module_class, list_module_types


@dataclass(frozen=True, slots=True)
class ParamChange:
    module_id: str
    module_type: str
    key: str
    old_value: Any
    new_value: Any


@dataclass
class BulkEditResult:
    updated_module_ids: list[str] = field(default_factory=list)
    skipped_module_ids: list[str] = field(default_factory=list)
    changes: list[ParamChange] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def updated_count(self) -> int:
        return len(self.updated_module_ids)


def parse_param_value(raw: str, *, target_type: type | None = None) -> Any:
    """Parse CLI/UI string into a Python value."""
    text = raw.strip()
    if not text:
        raise ValueError("empty value")

    lowered = text.lower()
    if lowered in ("true", "false"):
        return lowered == "true"

    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [parse_param_value(part.strip()) for part in inner.split(",")]

    if "/" in text and text[0].lower() == "c":
        # C/3 → 0.333...
        _, denom = text.split("/", 1)
        return 1.0 / float(denom)

    if target_type is int or (target_type is None and text.isdigit()):
        return int(text)

    try:
        return float(text)
    except ValueError:
        return text


def coerce_param_for_field(module_type: str, key: str, raw: Any) -> Any:
    cls = get_module_class(module_type)
    if cls is None:
        raise ValueError(f"Unknown module type: {module_type}")
    fields = cls.__dataclass_fields__
    if key not in fields:
        raise ValueError(f"Unknown param '{key}' for module type '{module_type}'")

    if not isinstance(raw, str):
        return raw

    field_type = fields[key].type
    # list[float] etc.
    if str(field_type).startswith("list") or getattr(field_type, "__origin__", None) is list:
        if raw.startswith("["):
            return parse_param_value(raw)
        return [parse_param_value(part.strip()) for part in raw.split(",") if part.strip()]

    return parse_param_value(raw, target_type=field_type if field_type in (int, float, str, bool) else None)


def list_editable_params(module_type: str) -> tuple[str, ...]:
    cls = get_module_class(module_type)
    if cls is None:
        return ()
    skip = {"setup", "repeat", "after"}
    return tuple(
        key for key in cls.__dataclass_fields__ if key not in skip
    )


def common_bulk_params() -> tuple[str, ...]:
    """Frequently bulk-edited params across experiment modules."""
    return (
        "charge_c_rate",
        "discharge_c_rate",
        "initial_c_rate",
        "measurement_c_rate",
        "measurement_cycles",
        "reference_c_rate",
        "dcir_pulse_c_rate",
        "pulse_c_rate",
        "loop_count",
        "cycle_count",
        "rest_s",
    )


def select_modules(
    project: ScheduleProject,
    *,
    module_ids: list[str] | None = None,
    module_types: list[str] | None = None,
    all_modules: bool = False,
) -> list[ModuleNode]:
    if all_modules:
        return list(project.modules)

    selected: list[ModuleNode] = []
    if module_ids is not None:
        id_set = set(module_ids)
        selected = [m for m in project.modules if m.id in id_set]
        missing = id_set - {m.id for m in selected}
        if missing:
            raise ValueError(f"Unknown module id(s): {', '.join(sorted(missing))}")
        return selected

    if module_types is not None:
        type_set = set(module_types)
        return [m for m in project.modules if m.module_type in type_set]

    return list(project.modules)


def apply_bulk_edit(
    project: ScheduleProject,
    param_patch: dict[str, Any],
    *,
    module_ids: list[str] | None = None,
    module_types: list[str] | None = None,
    all_modules: bool = False,
    skip_incompatible: bool = True,
) -> BulkEditResult:
    """Apply parameter patch to all or selected modules.

    Keys not defined on a module type are skipped when *skip_incompatible* is True.
    """
    if not param_patch:
        raise ValueError("param_patch must not be empty")

    result = BulkEditResult()
    try:
        targets = select_modules(
            project,
            module_ids=module_ids,
            module_types=module_types,
            all_modules=all_modules,
        )
    except ValueError as exc:
        result.errors.append(str(exc))
        return result

    if not targets:
        result.errors.append("no modules matched selection")
        return result

    for node in targets:
        cls = get_module_class(node.module_type)
        if cls is None:
            result.errors.append(f"{node.id}: unknown module type '{node.module_type}'")
            result.skipped_module_ids.append(node.id)
            continue

        allowed = set(cls.__dataclass_fields__)
        module_changed = False

        for key, raw_value in param_patch.items():
            if key not in allowed:
                if skip_incompatible:
                    continue
                result.errors.append(
                    f"{node.id}: param '{key}' not valid for type '{node.module_type}'"
                )
                continue

            try:
                new_value = coerce_param_for_field(node.module_type, key, raw_value)
            except ValueError as exc:
                result.errors.append(f"{node.id}.{key}: {exc}")
                continue

            old_value = node.params.get(key)
            if old_value == new_value:
                continue

            node.params[key] = new_value
            result.changes.append(
                ParamChange(
                    module_id=node.id,
                    module_type=node.module_type,
                    key=key,
                    old_value=old_value,
                    new_value=new_value,
                )
            )
            module_changed = True

        if module_changed:
            result.updated_module_ids.append(node.id)
        else:
            result.skipped_module_ids.append(node.id)

    return result


def parse_set_args(set_args: list[str]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    for item in set_args:
        if "=" not in item:
            raise ValueError(f"Expected key=value, got: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Empty key in: {item}")
        patch[key] = value.strip()
    return patch
