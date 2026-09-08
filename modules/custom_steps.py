"""A module holding explicit steps, produced by detaching a preset.

Advanced users occasionally need one step of a preset changed.  Rather than
letting them edit a preset in place — which would quietly break the "this is
the locked golden topology" claim — the preset is expanded once, frozen into
this module, and marked as user-edited from then on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from .base import register_module

_VALID_STEP_TYPES = {
    "charge", "discharge", "rest", "ocv", "impedance",
    "pattern", "balance", "cycle", "loop", "end",
}


@register_module("custom_steps")
@dataclass
class CustomStepsModule:
    """Verbatim ``StepIntent`` dicts, kept in order."""

    steps: list[dict] = field(default_factory=list)
    source_module_type: str = ""

    @classmethod
    def from_params(cls, params: dict) -> CustomStepsModule:
        known = {k: v for k, v in params.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    @classmethod
    def from_steps(
        cls,
        steps: list[StepIntent],
        *,
        source_module_type: str = "",
    ) -> CustomStepsModule:
        return cls(
            steps=[step.to_dict() for step in steps],
            source_module_type=source_module_type,
        )

    def validate(self, cell: CellProfile) -> list[str]:
        errors: list[str] = []
        if not self.steps:
            return ["steps must not be empty"]
        for index, raw in enumerate(self.steps, start=1):
            if not isinstance(raw, dict):
                errors.append(f"step {index} must be an object")
                continue
            step_type = raw.get("step_type")
            if step_type not in _VALID_STEP_TYPES:
                errors.append(f"step {index} has unknown step_type {step_type!r}")
            if step_type == "end" and index != len(self.steps):
                errors.append(f"step {index}: END is only allowed as the final step")
        return errors

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        return [StepIntent.from_dict(dict(raw)) for raw in self.steps]

    def step_count(self) -> int:
        return len(self.steps)

    def as_params(self) -> dict[str, Any]:
        return {"steps": list(self.steps), "source_module_type": self.source_module_type}


__all__ = ["CustomStepsModule"]
