from __future__ import annotations

from dataclasses import dataclass

from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from .base import register_module


@register_module("charge")
@dataclass
class ChargeModule:
    mode: str = "CCCV"
    c_rate: float = 1.0
    end_voltage_v: float | None = None
    end_time_s: float | None = None
    cv_cutoff_c_rate: float | None = 0.05
    label: str = ""

    @classmethod
    def from_params(cls, params: dict) -> ChargeModule:
        return cls(**{k: v for k, v in params.items() if k in cls.__dataclass_fields__})

    def validate(self, cell: CellProfile) -> list[str]:
        if self.c_rate <= 0:
            return ["c_rate must be positive"]
        if self.mode not in {"CC", "CCCV", "CV"}:
            return [f"Unknown charge mode: {self.mode}"]
        return []

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        voltage = self.end_voltage_v if self.end_voltage_v is not None else cell.v_max
        return [
            StepIntent(
                step_type="charge",
                mode=self.mode,  # type: ignore[arg-type]
                label=self.label or f"{self.mode} charge",
                c_rate=self.c_rate,
                voltage_v=voltage if self.mode == "CCCV" else None,
                end_voltage_v=voltage,
                end_time_s=self.end_time_s,
                cv_cutoff_c_rate=self.cv_cutoff_c_rate if self.mode == "CCCV" else None,
            )
        ]
