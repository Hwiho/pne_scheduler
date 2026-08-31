from __future__ import annotations

from dataclasses import dataclass

from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from ..protocol.defaults import CYCLE_DEFAULT_C_RATE
from .base import register_module


@register_module("cycle_life")
@dataclass
class CycleLifeModule:
    charge_c_rate: float = CYCLE_DEFAULT_C_RATE
    discharge_c_rate: float = CYCLE_DEFAULT_C_RATE
    rest_s: float = 300.0
    loop_count: int = 100

    @classmethod
    def from_params(cls, params: dict) -> CycleLifeModule:
        return cls(**{k: v for k, v in params.items() if k in cls.__dataclass_fields__})

    def validate(self, cell: CellProfile) -> list[str]:
        if self.loop_count < 1:
            return ["loop_count must be >= 1"]
        return []

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        body = [
            StepIntent(
                step_type="charge",
                mode="CCCV",
                c_rate=self.charge_c_rate,
                voltage_v=cell.v_max,
                cv_cutoff_c_rate=0.05,
            ),
            StepIntent(step_type="rest", end_time_s=self.rest_s),
            StepIntent(
                step_type="discharge",
                mode="CC",
                c_rate=self.discharge_c_rate,
                end_voltage_v=cell.v_min,
            ),
            StepIntent(step_type="rest", end_time_s=self.rest_s),
        ]
        steps: list[StepIntent] = [StepIntent(step_type="cycle", label="cycle marker")]
        steps.extend(body)
        steps.append(
            StepIntent(
                step_type="loop",
                loop_goto_step=2,
                loop_count=self.loop_count,
            )
        )
        steps.append(StepIntent(step_type="end"))
        return steps
