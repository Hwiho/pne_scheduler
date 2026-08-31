from __future__ import annotations

from dataclasses import dataclass

from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from ..protocol.defaults import (
    CAPACHECK_INITIAL_C_RATE,
    CAPACHECK_MEASUREMENT_C_RATE,
)
from .base import register_module


@register_module("capacheck")
@dataclass
class CapacheckModule:
    """Initial capacity check / derating — 0.1C then C/3 (optionally C/3 twice).

    Reference: `0.1C capa_*.sch`, `*capacheck*.sch`
  Topology: REST → LOOP → CYCLE → steps → END
    """

    initial_c_rate: float = CAPACHECK_INITIAL_C_RATE
    measurement_c_rate: float = CAPACHECK_MEASUREMENT_C_RATE
    measurement_cycles: int = 1  # set to 2 for double C/3
    rest_s: float = 1800.0
    loop_count: int = 1

    @classmethod
    def from_params(cls, params: dict) -> CapacheckModule:
        return cls(**{k: v for k, v in params.items() if k in cls.__dataclass_fields__})

    def validate(self, cell: CellProfile) -> list[str]:
        if self.measurement_cycles < 1:
            return ["measurement_cycles must be >= 1"]
        return []

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        body: list[StepIntent] = [
            StepIntent(step_type="rest", label="capacheck initial rest", end_time_s=600.0),
            StepIntent(
                step_type="charge",
                mode="CCCV",
                label="capacheck 0.1C charge",
                c_rate=self.initial_c_rate,
                voltage_v=cell.v_max,
                cv_cutoff_c_rate=0.05,
            ),
            StepIntent(step_type="rest", label="capacheck rest after 0.1C charge", end_time_s=self.rest_s),
            StepIntent(
                step_type="discharge",
                mode="CC",
                label="capacheck 0.1C discharge",
                c_rate=self.initial_c_rate,
                end_voltage_v=cell.v_min,
            ),
            StepIntent(step_type="rest", label="capacheck rest after 0.1C discharge", end_time_s=self.rest_s),
        ]

        for cycle in range(self.measurement_cycles):
            body.extend(
                [
                    StepIntent(
                        step_type="charge",
                        mode="CCCV",
                        label=f"capacheck C/3 charge {cycle + 1}",
                        c_rate=self.measurement_c_rate,
                        voltage_v=cell.v_max,
                        cv_cutoff_c_rate=0.05,
                    ),
                    StepIntent(
                        step_type="rest",
                        label=f"capacheck rest after C/3 charge {cycle + 1}",
                        end_time_s=self.rest_s,
                    ),
                    StepIntent(
                        step_type="discharge",
                        mode="CC",
                        label=f"capacheck C/3 discharge {cycle + 1}",
                        c_rate=self.measurement_c_rate,
                        end_voltage_v=cell.v_min,
                    ),
                    StepIntent(
                        step_type="rest",
                        label=f"capacheck rest after C/3 discharge {cycle + 1}",
                        end_time_s=self.rest_s,
                    ),
                ]
            )

        steps: list[StepIntent] = [
            StepIntent(step_type="cycle", label="capacheck cycle marker"),
            *body,
            StepIntent(step_type="loop", loop_goto_step=2, loop_count=self.loop_count),
            StepIntent(step_type="end"),
        ]
        return steps
