"""Single command blocks — the steps a schedule is built from, one at a time.

The preset modules cover the experiments this lab runs; a primitive covers the
gap between them. Adding a settling rest before a measurement, or a single CC
discharge to reach a starting point, should not require detaching a preset and
inheriting its whole step list.

**Why there is no bare LOOP or END here.** The composer owns the final END and
rejects any other, and it resolves a LOOP's target as a position *inside its own
module* (`1 <= target < position`). A one-step LOOP has nowhere legal to point,
and a LOOP aimed past its own module would break the moment the procedure is
reordered. Repetition is therefore expressed as ``repeat_count`` on the step
itself, which emits the LOOP and its target together inside one fragment — the
only shape the contract allows.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from .base import register_module

# kind -> (step_type, mode, Korean title)
PRIMITIVE_KINDS: dict[str, tuple[str, str | None, str]] = {
    "rest": ("rest", None, "휴지 (Rest)"),
    "ocv": ("ocv", None, "개방전압 측정 (OCV)"),
    "cc_charge": ("charge", "CC", "정전류 충전 (CC)"),
    "cccv_charge": ("charge", "CCCV", "정전류·정전압 충전 (CCCV)"),
    "cv_charge": ("charge", "CV", "정전압 충전 (CV)"),
    "cc_discharge": ("discharge", "CC", "정전류 방전 (CC)"),
}

# Which fields each kind actually uses; the form hides the rest.
_USES_C_RATE = {"cc_charge", "cccv_charge", "cc_discharge"}
_USES_TARGET_VOLTAGE = {"cccv_charge", "cv_charge"}
_USES_CHARGE_CUTOFF = {"cc_charge"}
_USES_DISCHARGE_CUTOFF = {"cc_discharge"}
_USES_CV_CUTOFF = {"cccv_charge", "cv_charge"}
_USES_DURATION = {"rest", "ocv", "cv_charge"}


@register_module("primitive")
@dataclass
class PrimitiveModule:
    """One step, with an optional fragment-local repeat."""

    kind: str = "rest"
    c_rate: float = 0.5
    voltage_v: float = 4.2
    # A CC step stops at the far edge of the cell window, and which edge that is
    # depends on the direction — so the two cutoffs are separate fields rather
    # than one that means the opposite thing depending on `kind`.
    charge_end_voltage_v: float = 4.2
    discharge_end_voltage_v: float = 2.5
    cv_cutoff_c_rate: float = 0.05
    duration_s: float = 600.0
    repeat_count: int = 1

    @classmethod
    def from_params(cls, params: dict) -> PrimitiveModule:
        return cls(**{k: v for k, v in params.items() if k in cls.__dataclass_fields__})

    def title(self) -> str:
        return PRIMITIVE_KINDS.get(self.kind, (None, None, self.kind))[2]

    def validate(self, cell: CellProfile) -> list[str]:
        errors: list[str] = []
        if self.kind not in PRIMITIVE_KINDS:
            return [f"kind must be one of {', '.join(sorted(PRIMITIVE_KINDS))}"]
        if self.repeat_count < 1:
            errors.append("repeat_count must be >= 1")
        if self.kind in _USES_C_RATE and self.c_rate <= 0:
            errors.append("c_rate must be positive")
        if self.kind in _USES_DURATION and self.duration_s <= 0:
            errors.append("duration_s must be positive")
        if self.kind in _USES_TARGET_VOLTAGE and not (
            cell.v_min < self.voltage_v <= cell.v_max
        ):
            errors.append("voltage_v must be within the cell voltage window")
        if self.kind in _USES_CHARGE_CUTOFF and not (
            cell.v_min < self.charge_end_voltage_v <= cell.v_max
        ):
            errors.append("charge_end_voltage_v must be within the cell voltage window")
        if self.kind in _USES_DISCHARGE_CUTOFF and not (
            cell.v_min <= self.discharge_end_voltage_v < cell.v_max
        ):
            errors.append("discharge_end_voltage_v must be within the cell voltage window")
        return errors

    def build_step(self) -> StepIntent:
        """The single step this primitive stands for.

        Public because the step editor inserts steps through it: a step added
        inside a detached module and one added as its own module must be the
        same thing, and sharing this is how that stays true.
        """
        step_type, mode, title = PRIMITIVE_KINDS[self.kind]
        step = StepIntent(step_type=step_type, mode=mode, label=title)
        if self.kind in _USES_C_RATE:
            step.c_rate = self.c_rate
        if self.kind in _USES_TARGET_VOLTAGE:
            step.voltage_v = self.voltage_v
        if self.kind in _USES_CHARGE_CUTOFF:
            step.end_voltage_v = self.charge_end_voltage_v
        if self.kind in _USES_DISCHARGE_CUTOFF:
            step.end_voltage_v = self.discharge_end_voltage_v
        if self.kind in _USES_CV_CUTOFF:
            step.cv_cutoff_c_rate = self.cv_cutoff_c_rate
        if self.kind in _USES_DURATION:
            step.end_time_s = self.duration_s
        return step

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        step = self.build_step()
        if self.repeat_count <= 1:
            return [step]
        # The LOOP and the step it returns to live in the same fragment, so the
        # composer can resolve the target no matter where this module is moved.
        step.ref_id = "body"
        return [
            step,
            StepIntent(
                step_type="loop",
                label=f"{self.title()} {self.repeat_count}회 반복",
                loop_target_ref="body",
                loop_count=self.repeat_count,
            ),
        ]


__all__ = ["PRIMITIVE_KINDS", "PrimitiveModule"]
