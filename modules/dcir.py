from __future__ import annotations

from dataclasses import dataclass, field

from ..protocol.defaults import RPT_DCIR_PULSE_C_RATE_DEFAULT, RPT_DISCHARGE_C_RATE
from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from ..protocol.soc_ladder import (
    CHARGE_TO_FULL,
    UNCONFIRMED_ENTRY,
    ladder_capacity_fractions,
    validate_soc_ladder,
)
from .base import register_module


@register_module("dcir")
@dataclass
class DcirModule:
    soc_fractions: list[float] = field(default_factory=lambda: [0.8, 0.5, 0.2])
    reference_c_rate: float = RPT_DISCHARGE_C_RATE
    pulse_c_rate: float = RPT_DCIR_PULSE_C_RATE_DEFAULT
    pulse_s: float = 10.0
    rest_s: float = 1800.0
    dcr_start_s: float = 1.0
    dcr_end_s: float = 10.0
    preparation_policy: str = UNCONFIRMED_ENTRY
    start_soc: float = 1.0

    @classmethod
    def from_params(cls, params: dict) -> DcirModule:
        known = {k: v for k, v in params.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def validate(self, cell: CellProfile) -> list[str]:
        return validate_soc_ladder(
            start_soc=self.start_soc,
            soc_fractions=self.soc_fractions,
            setting_c_rate=self.reference_c_rate,
            pulse_c_rates=[self.pulse_c_rate],
            pulse_s=self.pulse_s,
            rest_s=self.rest_s,
            preparation_policy=self.preparation_policy,
            dcr_start_s=self.dcr_start_s,
            dcr_end_s=self.dcr_end_s,
        )

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        steps: list[StepIntent] = []
        if self.preparation_policy == CHARGE_TO_FULL:
            steps.extend(
                [
                    StepIntent(
                        step_type="charge",
                        mode="CCCV",
                        label="DC-IR user-selected preparation charge to full",
                        c_rate=self.reference_c_rate,
                        voltage_v=cell.v_max,
                        cv_cutoff_c_rate=0.05,
                    ),
                    StepIntent(
                        step_type="rest",
                        label="DC-IR rest after user-selected preparation charge",
                        end_time_s=self.rest_s,
                    ),
                ]
            )
        setting_fractions = ladder_capacity_fractions(
            start_soc=self.start_soc,
            soc_fractions=self.soc_fractions,
            pulse_c_rates=[self.pulse_c_rate],
            pulse_s=self.pulse_s,
        )
        for soc, delta in zip(self.soc_fractions, setting_fractions):
            steps.append(
                StepIntent(
                    step_type="discharge",
                    mode="CC",
                    label=f"DC-IR SOC setting to {soc:.0%}",
                    c_rate=self.reference_c_rate,
                    end_capacity_fraction=delta,
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
        return steps
