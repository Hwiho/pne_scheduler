from __future__ import annotations

from dataclasses import dataclass, field

from ..protocol.defaults import RPT_DCIR_PULSE_C_RATE_DEFAULT, RPT_DISCHARGE_C_RATE
from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from .base import register_module


@register_module("dcir")
@dataclass
class DcirModule:
    soc_fractions: list[float] = field(default_factory=lambda: [0.8, 0.5, 0.2])
    pulse_c_rate: float = RPT_DCIR_PULSE_C_RATE_DEFAULT
    pulse_s: float = 10.0
    rest_s: float = 1800.0
    dcr_start_s: float = 1.0
    dcr_end_s: float = 10.0

    @classmethod
    def from_params(cls, params: dict) -> DcirModule:
        known = {k: v for k, v in params.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def validate(self, cell: CellProfile) -> list[str]:
        if not self.soc_fractions:
            return ["soc_fractions must not be empty"]
        return []

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        steps: list[StepIntent] = []
        previous_soc = 1.0
        for soc in self.soc_fractions:
            steps.append(
                StepIntent(
                    step_type="discharge",
                    mode="CC",
                    label=f"DC-IR SOC setting to {soc:.0%}",
                    c_rate=RPT_DISCHARGE_C_RATE,
                    end_capacity_fraction=previous_soc - soc,
                )
            )
            steps.append(StepIntent(step_type="rest", end_time_s=self.rest_s))
            steps.append(
                StepIntent(
                    step_type="discharge",
                    mode="CC",
                    label=f"DC-IR pulse @ {soc:.0%}",
                    c_rate=self.pulse_c_rate,
                    end_time_s=self.pulse_s,
                    dcr_start_s=self.dcr_start_s,
                    dcr_end_s=self.dcr_end_s,
                )
            )
            steps.append(StepIntent(step_type="rest", end_time_s=self.rest_s))
            previous_soc = soc
        return steps
