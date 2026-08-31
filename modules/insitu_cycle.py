from __future__ import annotations

from dataclasses import dataclass

from ..ir.cell_profile import CellProfile
from ..protocol.defaults import CYCLE_DEFAULT_C_RATE
from ..ir.step_intent import StepIntent
from .base import register_module
from .cycle_life import CycleLifeModule


@register_module("insitu_cycle")
@dataclass
class InsituCycleModule(CycleLifeModule):
    """In-situ aging cycle — 0.5C default, no RPT measurement blocks."""

    charge_c_rate: float = CYCLE_DEFAULT_C_RATE
    discharge_c_rate: float = CYCLE_DEFAULT_C_RATE

    @classmethod
    def from_params(cls, params: dict) -> InsituCycleModule:
        return cls(**{k: v for k, v in params.items() if k in cls.__dataclass_fields__})

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        steps = super().expand(cell)
        if steps and steps[0].label is None:
            steps[0] = StepIntent(step_type="cycle", label="in-situ cycle marker (no RPT)")
        return steps
