from __future__ import annotations

from dataclasses import dataclass

from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from .base import register_module


@register_module("discharge")
@dataclass
class DischargeModule:
    mode: str = "CC"
    c_rate: float = 1.0
    end_voltage_v: float | None = None
    end_time_s: float | None = None
    end_capacity_fraction: float | None = None
    label: str = ""

    @classmethod
    def from_params(cls, params: dict) -> DischargeModule:
        return cls(**{k: v for k, v in params.items() if k in cls.__dataclass_fields__})

    def validate(self, cell: CellProfile) -> list[str]:
        if self.c_rate <= 0:
            return ["c_rate must be positive"]
        return []

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        voltage = self.end_voltage_v
        if voltage is None and self.end_capacity_fraction is None:
            voltage = cell.v_min
        return [
            StepIntent(
                step_type="discharge",
                mode=self.mode,  # type: ignore[arg-type]
                label=self.label or "CC discharge",
                c_rate=self.c_rate,
                end_voltage_v=voltage,
                end_time_s=self.end_time_s,
                end_capacity_fraction=self.end_capacity_fraction,
            )
        ]
