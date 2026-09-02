"""Shared recipe-backed parameter helpers for experiment modules."""

from __future__ import annotations

from typing import Any

from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from .presets import DEFAULT_PRESET_FOR_TYPE, PRESETS_BY_KEY, build_preset
from .recipe import ModuleRecipe, RecipeUnit, format_seconds


def knobs_from(instance: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: getattr(instance, key) for key in keys if hasattr(instance, key)}


def stored_recipe(instance: Any) -> ModuleRecipe:
    return ModuleRecipe(
        preset=getattr(instance, "preset", "custom") or "custom",
        setup=_as_units(getattr(instance, "setup", [])),
        repeat=_as_units(getattr(instance, "repeat", [])),
        repeat_count=_repeat_count_of(instance),
        after=_as_units(getattr(instance, "after", [])),
    )


def apply_recipe(instance: Any, recipe: ModuleRecipe) -> None:
    if hasattr(instance, "preset"):
        instance.preset = recipe.preset
    instance.setup = [unit.to_dict() for unit in recipe.setup]
    instance.repeat = [unit.to_dict() for unit in recipe.repeat]
    instance.after = [unit.to_dict() for unit in recipe.after]
    if hasattr(instance, "repeat_count"):
        instance.repeat_count = recipe.repeat_count
    if hasattr(instance, "cycle_count"):
        instance.cycle_count = recipe.repeat_count
    if hasattr(instance, "loop_count"):
        instance.loop_count = recipe.repeat_count


def has_editable_recipe(instance: Any) -> bool:
    return hasattr(instance, "setup") and hasattr(instance, "repeat")


def summarize_instance(instance: Any, *, limit: int = 8) -> list[str]:
    if has_editable_recipe(instance) and hasattr(instance, "recipe"):
        recipe = instance.recipe()
        lines: list[str] = []
        spec = PRESETS_BY_KEY.get(recipe.preset)
        if spec is not None:
            lines.append(spec.title)
        elif recipe.preset and recipe.preset != "custom":
            lines.append(recipe.preset)
        elif recipe.preset == "custom":
            lines.append("Custom recipe")
        lines.extend(recipe.card_lines(limit=limit))
        return lines or ["Empty recipe"]
    module_type = getattr(instance, "module_type", "")
    if module_type == "charge":
        rate = getattr(instance, "c_rate", None)
        mode = getattr(instance, "mode", "CC")
        voltage = getattr(instance, "end_voltage_v", None)
        suffix = f" → {voltage:g} V" if voltage is not None else ""
        return [f"{rate:g}C {mode}{suffix}".strip()]
    if module_type == "discharge":
        rate = getattr(instance, "c_rate", None)
        voltage = getattr(instance, "end_voltage_v", None)
        if voltage is not None:
            return [f"{rate:g}C DCHG → {voltage:g} V"]
        fraction = getattr(instance, "end_capacity_fraction", None)
        if fraction is not None:
            return [f"{rate:g}C DCHG ΔSOC {fraction:.0%}"]
        return [f"{rate:g}C DCHG"]
    if module_type == "rest":
        return [f"REST {format_seconds(getattr(instance, 'duration_s', None))}"]
    return [module_type or "module"]


def _repeat_count_of(instance: Any) -> int:
    for key in ("repeat_count", "cycle_count", "loop_count"):
        if hasattr(instance, key):
            value = getattr(instance, key)
            if value is not None:
                return max(int(value), 1)
    return 1


def materialize_recipe(
    instance: Any,
    *,
    module_type: str,
    knob_keys: tuple[str, ...],
) -> ModuleRecipe:
    recipe = stored_recipe(instance)
    if not recipe.is_empty:
        return recipe
    preset = recipe.preset
    if preset in {"custom", ""}:
        preset = DEFAULT_PRESET_FOR_TYPE.get(module_type, "sequence.blank")
    variant = getattr(instance, "variant", None)
    if variant == "soc_setting" and module_type == "qpeed":
        preset = "qpeed.soc_setting"
    built = build_preset(preset, knobs_from(instance, knob_keys))
    apply_recipe(instance, built)
    return built


def expand_materialized(
    instance: Any,
    cell: CellProfile,
    *,
    module_type: str,
    knob_keys: tuple[str, ...],
) -> list[StepIntent]:
    return materialize_recipe(
        instance,
        module_type=module_type,
        knob_keys=knob_keys,
    ).expand(cell)


def rebuild_from_preset(
    instance: Any,
    preset_key: str,
    *,
    knob_keys: tuple[str, ...],
) -> ModuleRecipe:
    recipe = build_preset(preset_key, knobs_from(instance, knob_keys))
    apply_recipe(instance, recipe)
    return recipe


def _as_units(items: list[Any]) -> list[RecipeUnit]:
    return [RecipeUnit.from_dict(item) for item in items or []]
