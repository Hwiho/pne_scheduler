"""QC pattern candidates reconstructed from the Set2/Set3/Set4 corpus."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from .base import register_module


@register_module("qc")
@dataclass
class QcModule:
    """Build QC-cycle/1N1Q or QC-1-charge reopen candidates.

    Defaults model the three-segment Set2 family. Add a leading rate/voltage/time
    entry (for example 5C) to obtain the 18-step Set4 shape.
    """

    variant: str = "cycle"
    conditioning_c_rate: float = 2.0 / 3.0
    discharge_c_rate: float = 1.0
    rest_s: float = 1800.0
    initial_voltage_v: float = 3.448
    fast_rates_c: list[float] = field(default_factory=lambda: [4.0, 3.0, 2.0])
    fast_voltages_v: list[float] = field(
        default_factory=lambda: [3.918, 4.008, 4.006]
    )
    fast_times_s: list[float] = field(default_factory=lambda: [534.0, 524.0, 290.0])
    one_c_time_s: float = 751.0
    one_charge_final_time_s: float = 10800.0
    cv_cutoff_c_rate: float = 0.1
    time_limit_s: float = 21600.0
    long_rest_s: float = 7200.0

    @classmethod
    def from_params(cls, params: dict) -> QcModule:
        known = {k: v for k, v in params.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def validate(self, cell: CellProfile) -> list[str]:
        errors: list[str] = []
        if self.variant not in {"cycle", "1n1q", "1_charge"}:
            errors.append("variant must be cycle, 1n1q, or 1_charge")
        lengths = {
            len(self.fast_rates_c),
            len(self.fast_voltages_v),
            len(self.fast_times_s),
        }
        if len(lengths) != 1 or not self.fast_rates_c:
            errors.append(
                "fast_rates_c, fast_voltages_v, and fast_times_s must have equal nonzero lengths"
            )
        if any(rate <= 0 for rate in self.fast_rates_c):
            errors.append("fast charge rates must be positive")
        if any(
            not (cell.v_min < voltage <= cell.v_max)
            for voltage in self.fast_voltages_v
        ):
            errors.append("fast charge voltages must be within the cell voltage window")
        if not (cell.v_min < self.initial_voltage_v <= cell.v_max):
            errors.append("initial_voltage_v must be within the cell voltage window")
        return errors

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        if self.variant == "1_charge":
            return self._expand_one_charge(cell)
        return self._expand_cycle(cell)

    def _full_charge(self, cell: CellProfile, *, label: str) -> StepIntent:
        return StepIntent(
            step_type="charge",
            mode="CCCV",
            label=label,
            c_rate=self.conditioning_c_rate,
            voltage_v=cell.v_max,
            cv_cutoff_c_rate=self.cv_cutoff_c_rate,
            end_time_s=self.time_limit_s,
        )

    def _discharge(self, cell: CellProfile, *, c_rate: float | None = None) -> StepIntent:
        return StepIntent(
            step_type="discharge",
            mode="CC",
            c_rate=self.discharge_c_rate if c_rate is None else c_rate,
            end_voltage_v=cell.v_min,
            end_time_s=self.time_limit_s,
        )

    def _fast_charge_steps(self, cell: CellProfile) -> list[StepIntent]:
        steps = [
            StepIntent(
                step_type="charge",
                mode="CCCV",
                label="QC initial voltage segment",
                c_rate=1.0,
                voltage_v=self.initial_voltage_v,
                cv_cutoff_c_rate=self.cv_cutoff_c_rate,
                end_time_s=self.time_limit_s,
            )
        ]
        for rate, voltage, seconds in zip(
            self.fast_rates_c,
            self.fast_voltages_v,
            self.fast_times_s,
        ):
            steps.append(
                StepIntent(
                    step_type="charge",
                    mode="CCCV",
                    label=f"QC {rate:g}C segment",
                    c_rate=rate,
                    voltage_v=voltage,
                    end_time_s=seconds,
                )
            )
        steps.extend(
            [
                StepIntent(
                    step_type="charge",
                    mode="CCCV",
                    label="QC 1C timed segment",
                    c_rate=1.0,
                    voltage_v=cell.v_max,
                    end_time_s=self.one_c_time_s,
                ),
                StepIntent(
                    step_type="charge",
                    mode="CCCV",
                    label="QC final CV taper",
                    c_rate=1.0,
                    voltage_v=cell.v_max,
                    cv_cutoff_c_rate=self.cv_cutoff_c_rate,
                    end_time_s=self.time_limit_s,
                ),
            ]
        )
        return steps

    def _expand_cycle(self, cell: CellProfile) -> list[StepIntent]:
        start_ref = "qc_start"
        return [
            self._full_charge(cell, label="QC conditioning charge"),
            StepIntent(step_type="rest", ref_id=start_ref, end_time_s=self.rest_s),
            self._discharge(cell),
            StepIntent(step_type="rest", end_time_s=self.rest_s),
            StepIntent(step_type="loop", loop_target_ref=start_ref, loop_count=1),
            StepIntent(step_type="cycle", label="QC cycle marker"),
            *self._fast_charge_steps(cell),
            StepIntent(step_type="rest", end_time_s=self.rest_s),
            self._discharge(cell),
            StepIntent(step_type="rest", end_time_s=self.rest_s),
            StepIntent(step_type="loop", loop_target_ref=start_ref, loop_count=1),
            StepIntent(step_type="end"),
        ]

    def _expand_one_charge(self, cell: CellProfile) -> list[StepIntent]:
        start_ref = "qc_1_charge_start"
        conditioning_ref = "qc_1_charge_conditioning"
        return [
            StepIntent(
                step_type="rest",
                ref_id=start_ref,
                label="QC 1-charge initial rest",
                end_time_s=self.long_rest_s,
            ),
            StepIntent(step_type="loop", loop_target_ref=start_ref, loop_count=1),
            StepIntent(step_type="cycle", ref_id=conditioning_ref),
            self._full_charge(cell, label="QC 1-charge conditioning charge 1"),
            StepIntent(step_type="rest", end_time_s=self.rest_s),
            self._discharge(cell, c_rate=self.conditioning_c_rate),
            StepIntent(step_type="rest", end_time_s=self.rest_s),
            StepIntent(
                step_type="loop",
                loop_target_ref=conditioning_ref,
                loop_count=2,
            ),
            StepIntent(step_type="cycle"),
            self._full_charge(cell, label="QC 1-charge conditioning charge 2"),
            StepIntent(step_type="rest", end_time_s=self.rest_s),
            self._discharge(cell, c_rate=self.conditioning_c_rate),
            StepIntent(step_type="rest", end_time_s=self.rest_s),
            StepIntent(
                step_type="charge",
                mode="CCCV",
                label="QC 90% capacity reference charge",
                c_rate=self.conditioning_c_rate,
                voltage_v=cell.v_max,
                end_time_s=self.time_limit_s,
                dod_percent=10.0,
                extra={"cap_ref_step": 7},
            ),
            StepIntent(step_type="loop", loop_target_ref=start_ref, loop_count=1),
            StepIntent(step_type="cycle", label="QC charge-rate marker"),
            *[
                StepIntent(
                    step_type="charge",
                    mode="CC",
                    label=f"QC 1-charge {rate:g}C segment",
                    c_rate=rate,
                    voltage_v=cell.v_max,
                    end_time_s=seconds,
                )
                for rate, seconds in zip(self.fast_rates_c, self.fast_times_s)
            ],
            StepIntent(
                step_type="charge",
                mode="CCCV",
                label="QC 1-charge final taper",
                c_rate=1.0,
                voltage_v=cell.v_max,
                cv_cutoff_c_rate=self.cv_cutoff_c_rate,
                end_time_s=self.one_charge_final_time_s,
            ),
            StepIntent(step_type="rest", end_time_s=self.long_rest_s),
            self._discharge(cell),
            StepIntent(step_type="rest", end_time_s=self.rest_s),
            StepIntent(step_type="loop", loop_target_ref=start_ref, loop_count=1),
            StepIntent(step_type="end"),
        ]
