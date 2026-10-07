"""QPEED protocol reconstructed from the locked lab schedules."""

from __future__ import annotations

from dataclasses import dataclass, field
import math

from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from .base import register_module
from .hppc import HppcModule


@register_module("qpeed")
@dataclass
class QpeedModule:
    """Generate the 167-step QPEED-2 or 11-step SOC-setting candidate.

    ``soc_fractions``/``pulse_*`` are retained for loading older ``.schproj``
    files. They are used only by the explicit ``legacy_pulse`` variant.
    """

    variant: str = "full"
    condition_c_rate: float = 1.0
    soc_voltage_v: float = 3.318
    initial_rest_s: float = 600.0
    rest_s: float = 1800.0
    condition_time_limit_s: float = 21600.0
    high_rate_start_c: float = 1.5
    high_rate_step_c: float = 1.5
    high_rate_levels: int = 12
    high_rate_time_limit_s: float = 57600.0
    short_rest_s: float = 1.0
    cv_cutoff_c_rate: float = 0.3
    soc_dod_percent: float = 10.0
    high_rate_dod_percent: float = 1.0
    soc_control: str = "voltage"
    start_soc_percent: float = 10.0
    soc_voltage_source: str = ""
    # Backward-compatible legacy pulse parameters.
    soc_fractions: list[float] = field(default_factory=lambda: [0.5])
    pulse_c_rate: float = 1.0
    pulse_s: float = 10.0
    rest_between_s: float = 40.0

    @classmethod
    def from_params(cls, params: dict) -> QpeedModule:
        known = {k: v for k, v in params.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def validate(self, cell: CellProfile) -> list[str]:
        errors: list[str] = []
        if self.variant not in {"full", "soc_setting", "legacy_pulse"}:
            errors.append("variant must be full, soc_setting, or legacy_pulse")
        if self.variant == "legacy_pulse" and not self.soc_fractions:
            errors.append("soc_fractions must not be empty")
        if self.variant == "legacy_pulse":
            return errors
        if self.soc_control not in {"voltage", "capacity"}:
            errors.append("soc_control must be voltage or capacity")
        def finite(value):
            return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        for name in ("condition_c_rate", "condition_time_limit_s", "cv_cutoff_c_rate"):
            value = getattr(self, name)
            if not finite(value) or value <= 0:
                errors.append(f"{name} must be finite and positive")
        for name in ("initial_rest_s", "rest_s"):
            value = getattr(self, name)
            if not finite(value) or value < 0:
                errors.append(f"{name} must be finite and nonnegative")
        if self.soc_control == "voltage":
            if not finite(self.soc_voltage_v) or not (cell.v_min < self.soc_voltage_v <= cell.v_max):
                errors.append("soc_voltage_v must be within the cell voltage window")
        if not finite(self.start_soc_percent) or not 0 < self.start_soc_percent < 100:
            errors.append("start_soc_percent must be between 0 and 100 (exclusive)")
        if self.variant == "full":
            if isinstance(self.high_rate_levels, bool) or not isinstance(self.high_rate_levels, int) or not 1 <= self.high_rate_levels <= 40:
                errors.append("high_rate_levels must be an integer between 1 and 40")
            for name in ("high_rate_start_c", "high_rate_time_limit_s", "high_rate_dod_percent"):
                value = getattr(self, name)
                if not finite(value) or value <= 0:
                    errors.append(f"{name} must be finite and positive")
            for name in ("high_rate_step_c", "short_rest_s"):
                value = getattr(self, name)
                if not finite(value) or value < 0:
                    errors.append(f"{name} must be finite and nonnegative")
            if finite(self.high_rate_dod_percent) and self.high_rate_dod_percent > 100:
                errors.append("high_rate_dod_percent must not exceed 100")
            if self.soc_control == "capacity" and finite(self.start_soc_percent) and finite(self.high_rate_dod_percent) and self.start_soc_percent + self.high_rate_dod_percent > 100:
                errors.append("시작 SOC + 고율 충전량(DOD)은 100%를 넘을 수 없습니다.")
        elif self.variant == "soc_setting" and (not finite(self.soc_dod_percent) or not 0 <= self.soc_dod_percent <= 100):
            errors.append("soc_dod_percent must be between 0 and 100")
        return errors

    def _soc_charge(self, cell: CellProfile, dod_percent=None) -> StepIntent:
        capacity_mode = self.soc_control == "capacity"
        return StepIntent(
            step_type="charge", mode="CC", label="QPEED SOC voltage setting" if not capacity_mode else f"QPEED nominal start SOC {self.start_soc_percent:g}% setting",
            c_rate=self.condition_c_rate, voltage_v=cell.v_max,
            end_voltage_v=cell.v_max if capacity_mode else self.soc_voltage_v,
            end_time_s=self.condition_time_limit_s,
            end_capacity_fraction=self.start_soc_percent / 100 if capacity_mode else None,
            dod_percent=None if capacity_mode else dod_percent,
            extra={"cap_ref_step": 7} if dod_percent is not None and not capacity_mode else {},
        )

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        if self.variant == "soc_setting":
            return self._conditioning(
                cell,
                dod_percent=self.soc_dod_percent,
                include_end=True,
            )
        if self.variant == "legacy_pulse":
            return HppcModule(
                soc_fractions=self.soc_fractions,
                pulse_c_rate=self.pulse_c_rate,
                pulse_s=self.pulse_s,
                rest_between_s=self.rest_between_s,
            ).expand(cell)
        return self._expand_full(cell)

    def _conditioning(
        self,
        cell: CellProfile,
        *,
        dod_percent: float | None,
        include_end: bool,
    ) -> list[StepIntent]:
        steps = [
            StepIntent(
                step_type="rest",
                label="QPEED conditioning start",
                ref_id="qpeed_start",
                end_time_s=self.initial_rest_s,
            ),
            StepIntent(
                step_type="discharge",
                mode="CC",
                label="QPEED conditioning discharge",
                c_rate=self.condition_c_rate,
                end_voltage_v=cell.v_min,
                end_time_s=self.condition_time_limit_s,
            ),
            StepIntent(step_type="rest", end_time_s=self.rest_s),
            StepIntent(
                step_type="charge",
                mode="CCCV",
                label="QPEED conditioning full charge",
                c_rate=self.condition_c_rate,
                voltage_v=cell.v_max,
                cv_cutoff_c_rate=self.cv_cutoff_c_rate,
                end_time_s=self.condition_time_limit_s,
            ),
            StepIntent(step_type="rest", end_time_s=self.rest_s),
            StepIntent(
                step_type="discharge",
                mode="CC",
                c_rate=self.condition_c_rate,
                end_voltage_v=cell.v_min,
                end_time_s=self.condition_time_limit_s,
            ),
            StepIntent(step_type="rest", end_time_s=self.rest_s),
            self._soc_charge(cell, dod_percent),
            StepIntent(step_type="rest", end_time_s=self.rest_s),
            StepIntent(
                step_type="loop",
                label="QPEED conditioning loop",
                loop_target_ref="qpeed_start",
                loop_count=1,
            ),
        ]
        if include_end:
            steps.append(StepIntent(step_type="end"))
        return steps

    def _expand_full(self, cell: CellProfile) -> list[StepIntent]:
        # Locked QPEED-2 shape: 10 conditioning records, twelve 13-record
        # high-rate blocks (1.5C..18C), then END = 167 records.
        steps = self._conditioning(cell, dod_percent=None, include_end=False)
        for index in range(self.high_rate_levels):
            rate = self.high_rate_start_c + index * self.high_rate_step_c
            block_ref = f"qpeed_block_{index + 1}"
            steps.extend(
                [
                    StepIntent(
                        step_type="cycle",
                        label=f"QPEED {rate:g}C marker",
                        ref_id=block_ref,
                    ),
                    StepIntent(
                        step_type="charge",
                        mode="CC",
                        label=f"QPEED {rate:g}C charge",
                        c_rate=rate,
                        voltage_v=cell.v_max + 0.1,
                        end_voltage_v=cell.v_max,
                        end_time_s=self.high_rate_time_limit_s,
                        dod_percent=self.high_rate_dod_percent if self.soc_control == "voltage" else None,
                        end_capacity_fraction=self.high_rate_dod_percent / 100 if self.soc_control == "capacity" else None,
                        extra={"cap_ref_step": 7} if self.soc_control == "voltage" else {},
                    ),
                    StepIntent(step_type="rest", end_time_s=self.short_rest_s),
                    StepIntent(step_type="rest", end_time_s=self.rest_s),
                    StepIntent(
                        step_type="discharge",
                        mode="CC",
                        c_rate=self.condition_c_rate,
                        end_voltage_v=cell.v_min,
                        end_time_s=self.condition_time_limit_s,
                    ),
                    StepIntent(step_type="rest", end_time_s=self.rest_s),
                    StepIntent(
                        step_type="charge",
                        mode="CCCV",
                        c_rate=self.condition_c_rate,
                        voltage_v=cell.v_max,
                        cv_cutoff_c_rate=self.cv_cutoff_c_rate,
                        end_time_s=self.condition_time_limit_s,
                    ),
                    StepIntent(step_type="rest", end_time_s=self.rest_s),
                    StepIntent(
                        step_type="discharge",
                        mode="CC",
                        c_rate=self.condition_c_rate,
                        end_voltage_v=cell.v_min,
                        end_time_s=self.condition_time_limit_s,
                    ),
                    StepIntent(step_type="rest", end_time_s=self.rest_s),
                    (self._soc_charge(cell) if self.soc_control == "capacity" else StepIntent(
                        step_type="charge", mode="CC", c_rate=self.condition_c_rate,
                        voltage_v=cell.v_max, end_voltage_v=self.soc_voltage_v,
                        end_time_s=self.condition_time_limit_s,
                    )),
                    StepIntent(step_type="rest", end_time_s=self.rest_s),
                    StepIntent(
                        step_type="loop",
                        loop_target_ref=block_ref,
                        loop_count=1,
                    ),
                ]
            )
        steps.append(StepIntent(step_type="end"))
        return steps
