"""Minimal Rest → CCCV charge → END schedule for Gate C5 equipment smoke."""

from __future__ import annotations

from dataclasses import dataclass

from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from .base import register_module


@register_module("smoke_rest_cc_end")
@dataclass
class SmokeRestCcEndModule:
    rest_s: float = 60.0
    charge_c_rate: float = 0.1
    cv_cutoff_c_rate: float = 0.05
    record_time_s: float = 60.0

    @classmethod
    def from_params(cls, params: dict) -> SmokeRestCcEndModule:
        return cls(**{k: v for k, v in params.items() if k in cls.__dataclass_fields__})

    def validate(self, cell: CellProfile) -> list[str]:
        if self.rest_s <= 0:
            return ["rest_s must be positive"]
        if self.charge_c_rate <= 0:
            return ["charge_c_rate must be positive"]
        return []

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        return [
            StepIntent(
                step_type="rest",
                label="smoke rest",
                end_time_s=self.rest_s,
                record_time_s=self.record_time_s,
            ),
            StepIntent(
                step_type="charge",
                mode="CCCV",
                label="smoke CC charge",
                c_rate=self.charge_c_rate,
                voltage_v=cell.v_max,
                cv_cutoff_c_rate=self.cv_cutoff_c_rate,
                record_time_s=self.record_time_s,
            ),
            StepIntent(step_type="end", label="smoke end"),
        ]
