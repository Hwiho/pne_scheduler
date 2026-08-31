from __future__ import annotations

from dataclasses import dataclass, field

from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from ..protocol.defaults import (
    RPT_DCIR_PULSE_C_RATE_DEFAULT,
    RPT_DCIR_SOC_FRACTIONS,
    RPT_DISCHARGE_C_RATE,
)
from .base import register_module


@register_module("rpt")
@dataclass
class RptModule:
    """Reference performance test — C/3 discharge + DC-IR pulse @ SOC 80/50/20."""

    reference_c_rate: float = RPT_DISCHARGE_C_RATE
    dcir_pulse_c_rate: float = RPT_DCIR_PULSE_C_RATE_DEFAULT
    dcir_pulse_s: float = 10.0
    rest_s: float = 1800.0
    soc_fractions: list[float] = field(default_factory=lambda: list(RPT_DCIR_SOC_FRACTIONS))
    include_dcir_pulses: bool = True

    @classmethod
    def from_params(cls, params: dict) -> RptModule:
        known = {k: v for k, v in params.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def validate(self, cell: CellProfile) -> list[str]:
        if not self.soc_fractions:
            return ["soc_fractions must not be empty"]
        return []

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        steps: list[StepIntent] = []
        previous_soc = 1.0

        for index, soc in enumerate(self.soc_fractions):
            delta = previous_soc - soc
            steps.append(
                StepIntent(
                    step_type="discharge",
                    mode="CC",
                    label=f"RPT C/3 to SOC {soc:.0%}",
                    c_rate=self.reference_c_rate,
                    end_capacity_fraction=delta if delta > 0 else None,
                    end_voltage_v=cell.v_min if soc == 0.0 else None,
                )
            )
            steps.append(
                StepIntent(
                    step_type="rest",
                    label=f"RPT rest at SOC {soc:.0%}",
                    end_time_s=self.rest_s,
                )
            )
            if self.include_dcir_pulses:
                steps.append(
                    StepIntent(
                        step_type="discharge",
                        mode="CC",
                        label=f"RPT DC-IR pulse @ SOC {soc:.0%}",
                        c_rate=self.dcir_pulse_c_rate,
                        end_time_s=self.dcir_pulse_s,
                        dcr_start_s=1.0,
                        dcr_end_s=10.0,
                    )
                )
                steps.append(
                    StepIntent(
                        step_type="rest",
                        label=f"RPT rest after DC-IR @ SOC {soc:.0%}",
                        end_time_s=self.rest_s,
                    )
                )
            previous_soc = soc

        return steps
