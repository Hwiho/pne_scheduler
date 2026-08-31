"""QPEED experiment module (includes SOC setting sub-protocol)."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from .base import register_module
from .hppc import HppcModule


@register_module("qpeed")
@dataclass
class QpeedModule(HppcModule):
    """Bimodal QPEED pulse protocol.

    Sub-variants:
    - ``full``: full pulse train (e.g. ``..._QPEED-2.sch``)
    - ``soc_setting``: SOC conditioning block only (e.g. ``..._QPEED_SOC_setting_...``)
    """

    variant: str = "full"
    soc_fractions: list[float] = field(default_factory=lambda: [0.5])

    @classmethod
    def from_params(cls, params: dict) -> QpeedModule:
        known = {k: v for k, v in params.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        if self.variant == "soc_setting":
            return self._expand_soc_setting(cell)
        return super().expand(cell)

    def _expand_soc_setting(self, cell: CellProfile) -> list[StepIntent]:
        steps: list[StepIntent] = []
        previous_soc = 1.0
        for soc in self.soc_fractions:
            if soc < previous_soc:
                steps.append(
                    StepIntent(
                        step_type="discharge",
                        mode="CC",
                        label=f"QPEED SOC setting to {soc:.0%}",
                        c_rate=1.0 / 3.0,
                        end_capacity_fraction=previous_soc - soc,
                    )
                )
                steps.append(
                    StepIntent(
                        step_type="rest",
                        label=f"QPEED SOC rest @ {soc:.0%}",
                        end_time_s=self.rest_between_s,
                    )
                )
            previous_soc = soc
        steps.append(StepIntent(step_type="loop", label="QPEED soc_setting loop anchor"))
        steps.append(StepIntent(step_type="end"))
        return steps
