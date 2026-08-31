from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from ..protocol.defaults import CYCLE_DEFAULT_C_RATE
from .base import register_module
from .composable import expand_materialized, materialize_recipe, rebuild_from_preset
from .recipe import ModuleRecipe

_KNOBS = ("charge_c_rate", "discharge_c_rate", "rest_s", "loop_count")


@register_module("cycle_life")
@dataclass
class CycleLifeModule:
    preset: str = "cycle_life.default"
    charge_c_rate: float = CYCLE_DEFAULT_C_RATE
    discharge_c_rate: float = CYCLE_DEFAULT_C_RATE
    rest_s: float = 300.0
    loop_count: int = 100
    setup: list[dict[str, Any]] = field(default_factory=list)
    repeat: list[dict[str, Any]] = field(default_factory=list)
    after: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_params(cls, params: dict) -> CycleLifeModule:
        known = {k: v for k, v in params.items() if k in cls.__dataclass_fields__}
        instance = cls(**known)
        materialize_recipe(instance, module_type="cycle_life", knob_keys=_KNOBS)
        return instance

    def validate(self, cell: CellProfile) -> list[str]:
        if self.loop_count < 1:
            return ["loop_count must be >= 1"]
        return []

    def recipe(self) -> ModuleRecipe:
        return materialize_recipe(self, module_type="cycle_life", knob_keys=_KNOBS)

    def apply_preset(self, preset_key: str | None = None) -> ModuleRecipe:
        return rebuild_from_preset(
            self,
            preset_key or self.preset or "cycle_life.default",
            knob_keys=_KNOBS,
        )

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        return expand_materialized(
            self,
            cell,
            module_type="cycle_life",
            knob_keys=_KNOBS,
        )
