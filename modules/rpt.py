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


def _rate_label(rate: float) -> str:
    """Render a pulse rate the way the lab writes it: 1C, 1.5C, 2C."""
    text = f"{rate:.2f}".rstrip("0").rstrip(".")
    return f"{text}C"


@register_module("rpt")
@dataclass
class RptModule:
    """Reference performance test — C/3 discharge + DC-IR pulse @ SOC 80/50/20."""

    reference_c_rate: float = RPT_DISCHARGE_C_RATE
    dcir_pulse_c_rates: list[float] = field(
        default_factory=lambda: [RPT_DCIR_PULSE_C_RATE_DEFAULT]
    )
    dcir_pulse_s: float = 10.0
    rest_s: float = 1800.0
    soc_fractions: list[float] = field(default_factory=lambda: list(RPT_DCIR_SOC_FRACTIONS))
    include_dcir_pulses: bool = True

    @classmethod
    def from_params(cls, params: dict) -> RptModule:
        known = {k: v for k, v in params.items() if k in cls.__dataclass_fields__}
        # Projects written before multi-rate DC-IR carry a single `dcir_pulse_c_rate`.
        # Seed the list from it so an old file keeps producing the same schedule.
        if "dcir_pulse_c_rates" not in known and "dcir_pulse_c_rate" in params:
            known["dcir_pulse_c_rates"] = [float(params["dcir_pulse_c_rate"])]
        return cls(**known)

    def validate(self, cell: CellProfile) -> list[str]:
        errors: list[str] = []
        if not self.soc_fractions:
            errors.append("soc_fractions must not be empty")
        if self.include_dcir_pulses:
            if not self.dcir_pulse_c_rates:
                errors.append("dcir_pulse_c_rates must not be empty when pulses are included")
            if any(rate <= 0 for rate in self.dcir_pulse_c_rates):
                errors.append("DC-IR pulse C-rates must be positive")
        return errors

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
                # Each rate gets its own pulse and its own recovery rest, so the
                # cell returns to the same SOC before the next rate is applied and
                # the resistances stay comparable across rates.
                for rate in self.dcir_pulse_c_rates:
                    steps.append(
                        StepIntent(
                            step_type="discharge",
                            mode="CC",
                            label=f"RPT DC-IR pulse {_rate_label(rate)} @ SOC {soc:.0%}",
                            c_rate=rate,
                            end_time_s=self.dcir_pulse_s,
                            dcr_start_s=1.0,
                            dcr_end_s=10.0,
                        )
                    )
                    steps.append(
                        StepIntent(
                            step_type="rest",
                            label=(
                                f"RPT rest after DC-IR {_rate_label(rate)} @ SOC {soc:.0%}"
                            ),
                            end_time_s=self.rest_s,
                        )
                    )
            previous_soc = soc

        return steps
