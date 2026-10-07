from __future__ import annotations

from dataclasses import dataclass, field

from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from ..protocol.defaults import (
    RPT_DCIR_PULSE_C_RATE_DEFAULT,
    RPT_DCIR_SOC_FRACTIONS,
    RPT_DISCHARGE_C_RATE,
)
from ..protocol.soc_ladder import (
    CHARGE_TO_FULL,
    PREPARATION_POLICIES,
    UNCONFIRMED_ENTRY,
    is_finite_number,
    ladder_capacity_fractions,
    validate_soc_ladder,
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
    preparation_policy: str = UNCONFIRMED_ENTRY
    start_soc: float = 1.0

    @classmethod
    def from_params(cls, params: dict) -> RptModule:
        known = {k: v for k, v in params.items() if k in cls.__dataclass_fields__}
        # Projects written before multi-rate DC-IR carry a single `dcir_pulse_c_rate`.
        # Seed the list from it so an old file keeps producing the same schedule.
        if "dcir_pulse_c_rates" not in known and "dcir_pulse_c_rate" in params:
            known["dcir_pulse_c_rates"] = [float(params["dcir_pulse_c_rate"])]
        return cls(**known)

    def validate(self, cell: CellProfile) -> list[str]:
        if not self.include_dcir_pulses:
            errors: list[str] = []
            if self.preparation_policy not in PREPARATION_POLICIES:
                errors.append(
                    "preparation_policy must be 'unconfirmed_entry', "
                    "'user_confirmed_start_soc', or user-selected 'charge_to_full'"
                )
            if not is_finite_number(self.reference_c_rate) or self.reference_c_rate <= 0.0:
                errors.append("reference C-rate must be finite and positive")
            if not is_finite_number(self.rest_s) or self.rest_s <= 0.0:
                errors.append("final rest duration must be finite and positive")
            return errors

        pulse_rates = self.dcir_pulse_c_rates if self.include_dcir_pulses else []
        errors = validate_soc_ladder(
            start_soc=self.start_soc,
            soc_fractions=self.soc_fractions,
            setting_c_rate=self.reference_c_rate,
            pulse_c_rates=pulse_rates,
            pulse_s=self.dcir_pulse_s,
            rest_s=self.rest_s,
            preparation_policy=self.preparation_policy,
            dcr_start_s=1.0 if self.include_dcir_pulses else None,
            dcr_end_s=10.0 if self.include_dcir_pulses else None,
        )
        if self.include_dcir_pulses:
            if not self.dcir_pulse_c_rates:
                errors.append("dcir_pulse_c_rates must not be empty when pulses are included")
        return errors

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        if not self.include_dcir_pulses:
            steps: list[StepIntent] = []
            if self.preparation_policy == CHARGE_TO_FULL:
                steps.extend(
                    [
                        StepIntent(
                            step_type="charge",
                            mode="CCCV",
                            label="RPT user-selected preparation charge to full",
                            c_rate=self.reference_c_rate,
                            voltage_v=cell.v_max,
                            cv_cutoff_c_rate=0.05,
                        ),
                        StepIntent(
                            step_type="rest",
                            label="RPT rest after user-selected preparation charge",
                            end_time_s=self.rest_s,
                        ),
                    ]
                )
            steps.extend(
                [
                    StepIntent(
                        step_type="discharge",
                        mode="CC",
                        label="RPT reference discharge to lower voltage",
                        c_rate=self.reference_c_rate,
                        end_voltage_v=cell.v_min,
                    ),
                    StepIntent(
                        step_type="rest",
                        label="RPT final rest after reference discharge",
                        end_time_s=self.rest_s,
                    ),
                ]
            )
            return steps

        steps: list[StepIntent] = []
        if self.preparation_policy == CHARGE_TO_FULL:
            steps.extend(
                [
                    StepIntent(
                        step_type="charge",
                        mode="CCCV",
                        label="RPT user-selected preparation charge to full",
                        c_rate=self.reference_c_rate,
                        voltage_v=cell.v_max,
                        cv_cutoff_c_rate=0.05,
                    ),
                    StepIntent(
                        step_type="rest",
                        label="RPT rest after user-selected preparation charge",
                        end_time_s=self.rest_s,
                    ),
                ]
            )
        pulse_rates = self.dcir_pulse_c_rates if self.include_dcir_pulses else []
        setting_fractions = ladder_capacity_fractions(
            start_soc=self.start_soc,
            soc_fractions=self.soc_fractions,
            pulse_c_rates=pulse_rates,
            pulse_s=self.dcir_pulse_s,
        )

        for soc, delta in zip(self.soc_fractions, setting_fractions):
            steps.append(
                StepIntent(
                    step_type="discharge",
                    mode="CC",
                    label=f"RPT C/3 to SOC {soc:.0%}",
                    c_rate=self.reference_c_rate,
                    end_capacity_fraction=delta,
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
                # Rest recovers voltage, not SOC. Every pulse therefore lowers
                # the actual SOC used to calculate the next ladder segment.
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
        return steps
