"""Generic editable sequence of charge / discharge / rest units."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from .base import register_module
from .composable import expand_materialized, materialize_recipe, rebuild_from_preset
from .recipe import ModuleRecipe

_KNOBS = ("repeat_count",)


@register_module("sequence")
@dataclass
class SequenceModule:
    preset: str = "sequence.blank"
    repeat_count: int = 1
    setup: list[dict[str, Any]] = field(default_factory=list)
    repeat: list[dict[str, Any]] = field(default_factory=list)
    after: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_params(cls, params: dict) -> SequenceModule:
        known = {k: v for k, v in params.items() if k in cls.__dataclass_fields__}
        instance = cls(**known)
        materialize_recipe(instance, module_type="sequence", knob_keys=_KNOBS)
        return instance

    def validate(self, cell: CellProfile) -> list[str]:
        return []

    def recipe(self) -> ModuleRecipe:
        return materialize_recipe(self, module_type="sequence", knob_keys=_KNOBS)

    def apply_preset(self, preset_key: str | None = None) -> ModuleRecipe:
        return rebuild_from_preset(
            self,
            preset_key or self.preset or "sequence.blank",
            knob_keys=_KNOBS,
        )

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        return expand_materialized(
            self,
            cell,
            module_type="sequence",
            knob_keys=_KNOBS,
        )
