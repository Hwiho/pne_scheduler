from __future__ import annotations

from dataclasses import dataclass, field

from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent
from .base import register_module


@register_module("hppc")
@dataclass
class HppcModule:
    variant: str = "legacy_soc_pulse"
    soc_fractions: list[float] = field(default_factory=lambda: [0.9, 0.5, 0.1])
    pulse_c_rate: float = 1.0
    pulse_s: float = 10.0
    rest_between_s: float = 40.0
    full_capacity_c_rate: float = 0.1
    reference_c_rate: float = 1.0 / 3.0
    full_pulse_c_rate: float = 1.0
    full_time_limit_s: float = 57600.0
    full_rest_s: float = 1800.0
    full_long_rest_s: float = 3600.0

    @classmethod
    def from_params(cls, params: dict) -> HppcModule:
        known = {k: v for k, v in params.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def validate(self, cell: CellProfile) -> list[str]:
        if self.variant not in {"full", "legacy_soc_pulse"}:
            return ["variant must be full or legacy_soc_pulse"]
        if not self.soc_fractions:
            return ["soc_fractions must not be empty"]
        return []

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        if self.variant == "full":
            return self._expand_full(cell)
        return self._expand_legacy()

    def _expand_legacy(self) -> list[StepIntent]:
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

    def _expand_full(self, cell: CellProfile) -> list[StepIntent]:
        """Reproduce the locked 62-step HPPC full-range topology.

        The 5.0 V charge and 2.2 V discharge values are mode limits observed in
        the fixture. Cell termination remains at 4.2/2.5 V and the PNE02 header
        safety block remains the authoritative cell window.
        """
        start = "hppc_start"
        phase_2 = "hppc_phase_2"

        def rest(seconds: float, *, ref_id: str | None = None, cap_ref: int | None = None) -> StepIntent:
            return StepIntent(
                step_type="rest",
                ref_id=ref_id,
                end_time_s=seconds,
                extra={"cap_ref_step": cap_ref} if cap_ref is not None else {},
            )

        def loop(
            target: str,
            count: int,
            *,
            ref_id: str | None = None,
        ) -> StepIntent:
            return StepIntent(
                step_type="loop",
                ref_id=ref_id,
                loop_target_ref=target,
                loop_count=count,
            )

        def cycle() -> StepIntent:
            return StepIntent(step_type="cycle", label="HPPC cycle marker")

        def cccv(rate: float) -> StepIntent:
            return StepIntent(
                step_type="charge",
                mode="CCCV",
                c_rate=rate,
                voltage_v=cell.v_max,
                cv_cutoff_c_rate=0.05,
                end_time_s=self.full_time_limit_s,
            )

        def discharge(
            rate: float,
            seconds: float,
            *,
            dod: float | None = None,
            cap_ref: int | None = None,
            vlim: float = 2.2,
        ) -> StepIntent:
            return StepIntent(
                step_type="discharge",
                mode="CC",
                c_rate=rate,
                voltage_v=vlim,
                end_voltage_v=cell.v_min,
                end_time_s=seconds,
                dod_percent=dod,
                extra={"cap_ref_step": cap_ref} if cap_ref is not None else {},
            )

        def charge_pulse(
            rate: float,
            seconds: float,
            *,
            dod: float | None = None,
            cap_ref: int | None = None,
        ) -> StepIntent:
            return StepIntent(
                step_type="charge",
                mode="CC",
                c_rate=rate,
                voltage_v=5.0,
                end_voltage_v=cell.v_max,
                end_time_s=seconds,
                dod_percent=dod,
                extra={"cap_ref_step": cap_ref} if cap_ref is not None else {},
            )

        c01 = self.full_capacity_c_rate
        c_ref = self.reference_c_rate
        c1 = self.full_pulse_c_rate
        limit = self.full_time_limit_s
        r = self.full_rest_s
        long_r = self.full_long_rest_s
        return [
            rest(10800.0, ref_id=start),                   # 1
            loop(start, 1), cycle(), cccv(c01), rest(r),  # 2–5
            discharge(c01, limit, vlim=2.0), rest(r),     # 6–7
            loop(start, 2, ref_id=phase_2),               # 8
            cycle(), cccv(c_ref), rest(r),                # 9–11
            discharge(c_ref, limit, vlim=2.0), rest(r),   # 12–13
            loop(start, 2), cycle(), cccv(c01),           # 14–16
            rest(long_r), loop(start, 1), cycle(),        # 17–19
            discharge(c1, 30.0), rest(r, cap_ref=0),      # 20–21
            charge_pulse(c01, limit, dod=100.0, cap_ref=21), rest(r),
            loop(start, 1), cycle(), rest(1.0),            # 24–26
            loop(start, 2), cycle(),                       # 27–28
            discharge(c01, limit, dod=10.0, cap_ref=7),   # 29
            rest(long_r), loop(start, 1), cycle(),         # 30–32
            discharge(c1, 30.0), rest(r, cap_ref=0),      # 33–34
            charge_pulse(c01, limit, dod=100.0, cap_ref=34),
            rest(long_r), loop(start, 1), cycle(),         # 36–38
            charge_pulse(c1, 30.0), rest(r),              # 39–40
            discharge(c01, limit, dod=100.0, cap_ref=40), rest(r),
            loop(start, 1), cycle(), rest(1.0),            # 43–45
            loop(phase_2, 1),                              # 46 -> step 8
            cycle(), rest(1.0), loop(start, 2), cycle(),  # 47–50
            discharge(c01, limit, dod=5.0, cap_ref=7),    # 51
            rest(long_r), charge_pulse(c1, 30.0),         # 52–53
            rest(r),                                      # 54
            discharge(c01, limit, dod=100.0, cap_ref=54), rest(r),
            loop(start, 1), cycle(),                       # 57–58
            discharge(c01, limit, vlim=2.0), rest(r),     # 59–60
            loop(start, 1), StepIntent(step_type="end"),  # 61–62
        ]
