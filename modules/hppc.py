"""HPPC module with editable charge/discharge/rest recipes."""

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
    "soc_fractions",
    "pulse_c_rate",
    "pulse_s",
    "rest_between_s",
    "rest_s",
    "repeat_count",
)


@register_module("hppc")
@dataclass
class HppcModule:
    preset: str = "hppc.full_range"
    soc_fractions: list[float] = field(default_factory=lambda: [0.9, 0.5, 0.1])
    pulse_c_rate: float = 1.0
    pulse_s: float = 10.0
    rest_between_s: float = 40.0
    rest_s: float = 1800.0
    repeat_count: int = 1
    setup: list[dict[str, Any]] = field(default_factory=list)
    repeat: list[dict[str, Any]] = field(default_factory=list)
    after: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_params(cls, params: dict) -> HppcModule:
        known = {k: v for k, v in params.items() if k in cls.__dataclass_fields__}
        instance = cls(**known)
        materialize_recipe(instance, module_type="hppc", knob_keys=_KNOBS)
        return instance

    def validate(self, cell: CellProfile) -> list[str]:
        if self.recipe().is_empty:
            return ["HPPC recipe must not be empty"]
        return []

    def recipe(self) -> ModuleRecipe:
        return materialize_recipe(self, module_type="hppc", knob_keys=_KNOBS)

    def apply_preset(self, preset_key: str | None = None) -> ModuleRecipe:
        return rebuild_from_preset(
            self,
            preset_key or self.preset or DEFAULT_PRESET_FOR_TYPE["hppc"],
            knob_keys=_KNOBS,
        )

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        return expand_materialized(self, cell, module_type="hppc", knob_keys=_KNOBS)
