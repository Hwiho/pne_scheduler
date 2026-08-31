from __future__ import annotations

from dataclasses import dataclass, field

from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from .base import register_module


@register_module("hppc")
@dataclass
class HppcModule:
    soc_fractions: list[float] = field(default_factory=lambda: [0.9, 0.5, 0.1])
    pulse_c_rate: float = 1.0
    pulse_s: float = 10.0
    rest_between_s: float = 40.0

    @classmethod
    def from_params(cls, params: dict) -> HppcModule:
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
            if soc < previous_soc:
                steps.append(
                    StepIntent(
                        step_type="discharge",
                        mode="CC",
                        label=f"HPPC SOC adjust to {soc:.0%}",
                        c_rate=1.0 / 3.0,
                        end_capacity_fraction=previous_soc - soc,
                    )
                )
                steps.append(StepIntent(step_type="rest", end_time_s=self.rest_between_s))
            steps.extend(
                [
                    StepIntent(
                        step_type="discharge",
                        mode="CC",
                        label=f"HPPC discharge pulse @ {soc:.0%}",
                        c_rate=self.pulse_c_rate,
                        end_time_s=self.pulse_s,
                    ),
                    StepIntent(step_type="rest", end_time_s=self.rest_between_s),
                    StepIntent(
                        step_type="charge",
                        mode="CC",
                        label=f"HPPC charge pulse @ {soc:.0%}",
                        c_rate=self.pulse_c_rate,
                        end_time_s=self.pulse_s,
                    ),
                    StepIntent(step_type="rest", end_time_s=self.rest_between_s),
                ]
            )
            previous_soc = soc
        return steps
