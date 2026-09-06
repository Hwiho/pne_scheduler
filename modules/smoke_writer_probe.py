"""Gate C5 combinatorial smoke probe (optimized single-reopen writer check).

`smoke_rest_cc_end` only exercises REST -> CCCV charge -> END, which leaves the
discharge codepath, the LOOP construct, and per-step (non-default) sampling
untouched on a from-scratch build. Every one of those fields is already
``writer_ready``/``corpus_inferred`` in ``schema/fields.py`` with controlled-pair
or corpus evidence -- so a single file can pack all of them at once, each with a
distinct numeric value, and one CTSEditorPro reopen confirms (or falsifies) all
of them together instead of needing a separate physical smoke test per field or
per future module (Formation/Cycle Life share this exact step shape).

No field without prior evidence is packed here (see ``schema/fields.py``
``SEMANTIC_UNVERIFIED`` entries) -- this module only recombines already
evidence-qualified fields for maximum information density per lab visit.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from .base import register_module


@register_module("smoke_writer_probe")
@dataclass
class SmokeWriterProbeModule:
    charge_c_rate: float = 0.1
    cv_cutoff_c_rate: float = 0.05
    charge_record_time_s: float = 30.0
    charge_record_dV_mV: float = 20.0

    rest1_s: float = 50.0
    rest1_record_time_s: float = 25.0

    discharge_c_rate: float = 0.1
    discharge_record_time_s: float = 15.0
    discharge_record_dV_mV: float = 5.0
    discharge_dod_percent: float = 40.0

    rest2_s: float = 35.0
    rest2_record_time_s: float = 10.0

    loop_count: int = 2

    @classmethod
    def from_params(cls, params: dict) -> SmokeWriterProbeModule:
        return cls(**{k: v for k, v in params.items() if k in cls.__dataclass_fields__})

    def validate(self, cell: CellProfile) -> list[str]:
        errors: list[str] = []
        if self.charge_c_rate <= 0 or self.discharge_c_rate <= 0:
            errors.append("charge_c_rate and discharge_c_rate must be positive")
        if self.rest1_s <= 0 or self.rest2_s <= 0:
            errors.append("rest1_s and rest2_s must be positive")
        if self.loop_count < 2:
            errors.append("loop_count must be >= 2 to exercise the LOOP construct")
        return errors

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        return [
            StepIntent(step_type="cycle", label="probe cycle marker"),
            StepIntent(
                step_type="charge",
                mode="CCCV",
                label="probe CCCV charge",
                c_rate=self.charge_c_rate,
                voltage_v=cell.v_max,
                cv_cutoff_c_rate=self.cv_cutoff_c_rate,
                record_time_s=self.charge_record_time_s,
                record_dV_mV=self.charge_record_dV_mV,
            ),
            StepIntent(
                step_type="rest",
                label="probe rest 1",
                end_time_s=self.rest1_s,
                record_time_s=self.rest1_record_time_s,
            ),
            StepIntent(
                step_type="discharge",
                mode="CC",
                label="probe CC discharge",
                c_rate=self.discharge_c_rate,
                end_voltage_v=cell.v_min,
                record_time_s=self.discharge_record_time_s,
                record_dV_mV=self.discharge_record_dV_mV,
                dod_percent=self.discharge_dod_percent,
            ),
            StepIntent(
                step_type="rest",
                label="probe rest 2",
                end_time_s=self.rest2_s,
                record_time_s=self.rest2_record_time_s,
            ),
            StepIntent(
                step_type="loop",
                label="probe loop",
                loop_goto_step=2,
                loop_count=self.loop_count,
            ),
            StepIntent(step_type="end", label="probe end"),
        ]
