from __future__ import annotations

from dataclasses import dataclass

from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from .base import register_module


@register_module("rest")
@dataclass
class RestModule:
    duration_s: float = 600.0

    @classmethod
    def from_params(cls, params: dict) -> RestModule:
        return cls(**{k: v for k, v in params.items() if k in cls.__dataclass_fields__})

    def validate(self, cell: CellProfile) -> list[str]:
        if self.duration_s <= 0:
            return ["duration_s must be positive"]
        return []

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        return [StepIntent(step_type="rest", end_time_s=self.duration_s)]
