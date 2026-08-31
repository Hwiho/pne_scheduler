"""QPEED experiment module with editable charge/discharge/rest recipes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from .base import register_module
from .composable import expand_materialized, materialize_recipe, rebuild_from_preset
from .presets import DEFAULT_PRESET_FOR_TYPE
from .recipe import ModuleRecipe

_KNOBS = (
    "soc_voltage_v",
    "condition_c_rate",
    "pulse_c_rate",
    "rest_s",
    "short_rest_s",
    "repeat_count",
    "soc_fractions",
    "pulse_s",
    "rest_between_s",
)


@register_module("qpeed")
@dataclass
class QpeedModule:
    """QPEED pulse/fast-charge family.

    Default preset ``qpeed.full_3318`` matches the checked-in QPEED-2 topology:
    1C condition to 3.318 V, then 1.5C to 4.2 V, repeated. Edit the recipe
    units directly, or rebuild from a preset / knobs.
    """

    preset: str = "qpeed.full_3318"
    variant: str = "full"
    soc_voltage_v: float = 3.318
    condition_c_rate: float = 1.0
    pulse_c_rate: float = 1.5
    rest_s: float = 1800.0
    short_rest_s: float = 1.0
    repeat_count: int = 12
    soc_fractions: list[float] = field(default_factory=lambda: [0.5])
    pulse_s: float = 10.0
    rest_between_s: float = 40.0
    setup: list[dict[str, Any]] = field(default_factory=list)
    repeat: list[dict[str, Any]] = field(default_factory=list)
    after: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_params(cls, params: dict) -> QpeedModule:
        known = {k: v for k, v in params.items() if k in cls.__dataclass_fields__}
        if known.get("variant") == "soc_setting" and "preset" not in params:
            known["preset"] = "qpeed.soc_setting"
        instance = cls(**known)
        materialize_recipe(instance, module_type="qpeed", knob_keys=_KNOBS)
        return instance

    def validate(self, cell: CellProfile) -> list[str]:
        recipe = self.recipe()
        if recipe.is_empty:
            return ["QPEED recipe must not be empty"]
        if recipe.repeat and self.repeat_count < 1:
            return ["repeat_count must be >= 1"]
        return []

    def recipe(self) -> ModuleRecipe:
        return materialize_recipe(self, module_type="qpeed", knob_keys=_KNOBS)

    def apply_preset(self, preset_key: str | None = None) -> ModuleRecipe:
        key = preset_key or self.preset or DEFAULT_PRESET_FOR_TYPE["qpeed"]
        if key == "qpeed.soc_setting":
            self.variant = "soc_setting"
        elif key.startswith("qpeed."):
            self.variant = "full"
        return rebuild_from_preset(self, key, knob_keys=_KNOBS)

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        return expand_materialized(self, cell, module_type="qpeed", knob_keys=_KNOBS)
