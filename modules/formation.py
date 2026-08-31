from __future__ import annotations

from dataclasses import dataclass

from ..protocol.defaults import FORMATION_C_RATE
from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from .base import register_module


@register_module("formation")
@dataclass
class FormationModule:
    charge_c_rate: float = FORMATION_C_RATE
    discharge_c_rate: float = FORMATION_C_RATE
    rest_s: float = 600.0
    cycle_count: int = 3

    @classmethod
    def from_params(cls, params: dict) -> FormationModule:
        return cls(**{k: v for k, v in params.items() if k in cls.__dataclass_fields__})

    def validate(self, cell: CellProfile) -> list[str]:
        if self.cycle_count < 1:
            return ["cycle_count must be >= 1"]
        return []

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        steps: list[StepIntent] = []
        for cycle in range(self.cycle_count):
            steps.extend(
                [
                    StepIntent(
                        step_type="charge",
                        mode="CCCV",
                        label=f"Formation charge {cycle + 1}",
                        c_rate=self.charge_c_rate,
                        voltage_v=cell.v_max,
                        cv_cutoff_c_rate=0.05,
                    ),
                    StepIntent(
                        step_type="rest",
                        label=f"Formation rest after charge {cycle + 1}",
                        end_time_s=self.rest_s,
                    ),
                    StepIntent(
                        step_type="discharge",
                        mode="CC",
                        label=f"Formation discharge {cycle + 1}",
                        c_rate=self.discharge_c_rate,
                        end_voltage_v=cell.v_min,
                    ),
                    StepIntent(
                        step_type="rest",
                        label=f"Formation rest after discharge {cycle + 1}",
                        end_time_s=self.rest_s,
                    ),
                ]
            )
        return steps
