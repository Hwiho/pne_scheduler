"""Keep QC's fast-charge lists consistent when only the C-rates are changed.

``QcModule`` carries three parallel lists — rate, voltage limit, and time — and
requires them to stay the same length.  Typing a new rate list on its own is the
easy mistake: the module still validates, still exports, and still runs, but the
times are the ones measured at the *old* rates, so every segment now delivers a
different amount of charge than the protocol intends.  Nothing catches that,
because a plausible number in the right field looks exactly like a correct one.

The rule here is charge conservation on the constant-current portion: a segment
at ``C`` for ``t`` seconds passes ``C x t`` ampere-seconds of nominal capacity, so
halving the rate doubles the time to deliver the same charge.

What this does **not** model, and says so in the returned warnings: the segments
are CCCV, and once the voltage limit is reached the taper delivers charge at a
falling current that depends on cell impedance.  The corpus times were measured
on real cells; these are derived, and the module's own catalog limitation —
set-specific voltage and time values require user reopen review — still applies.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FastChargePlan:
    rates_c: tuple[float, ...] = ()
    voltages_v: tuple[float, ...] = ()
    times_s: tuple[float, ...] = ()
    notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors and bool(self.rates_c)

    def as_params(self) -> dict[str, list[float]]:
        """The three module fields, ready to merge into a module's params."""
        return {
            "fast_rates_c": list(self.rates_c),
            "fast_voltages_v": list(self.voltages_v),
            "fast_times_s": list(self.times_s),
        }


def _rate_text(rate: float) -> str:
    return f"{rate:.2f}".rstrip("0").rstrip(".") + "C"


def fast_charge_for_rates(
    new_rates_c: Sequence[float],
    *,
    rates_c: Sequence[float],
    voltages_v: Sequence[float],
    times_s: Sequence[float],
) -> FastChargePlan:
    """Rebuild the voltage and time lists to match ``new_rates_c``.

    Segments that already exist keep their measured voltage limit and get the
    time that preserves their charge.  Segments beyond the current list are
    modelled on the last one — same charge, same voltage limit — because three
    corpus voltages are too few to read a trend from, and repeating the last
    measured limit invents less than extrapolating one.
    """
    errors: list[str] = []
    if not new_rates_c:
        errors.append("급속충전 단계를 하나 이상 지정하세요.")
    if any(rate <= 0 for rate in new_rates_c):
        errors.append("급속충전 전류는 0보다 커야 합니다.")
    if not rates_c or not voltages_v or not times_s:
        errors.append("기준이 될 기존 단계 값이 없습니다.")
    elif len({len(rates_c), len(voltages_v), len(times_s)}) != 1:
        errors.append("기존 전류·전압·시간 목록의 길이가 서로 다릅니다.")
    elif any(rate <= 0 for rate in rates_c):
        errors.append("기존 급속충전 전류에 0 이하가 있습니다.")
    if errors:
        return FastChargePlan(errors=tuple(errors))

    scaled_times: list[float] = []
    scaled_voltages: list[float] = []
    changed: list[str] = []
    extended = 0

    for index, rate in enumerate(new_rates_c):
        source = index if index < len(rates_c) else len(rates_c) - 1
        if index >= len(rates_c):
            extended += 1
        old_rate = float(rates_c[source])
        old_time = float(times_s[source])
        # Charge conservation: C_old x t_old == C_new x t_new.
        new_time = old_time * old_rate / float(rate)
        scaled_times.append(round(new_time, 1))
        scaled_voltages.append(float(voltages_v[source]))
        if index < len(rates_c) and abs(old_rate - float(rate)) > 1e-9:
            changed.append(
                f"{index + 1}단 {_rate_text(old_rate)} → {_rate_text(rate)}: "
                f"{old_time:g}초 → {round(new_time, 1):g}초"
            )

    notes: list[str] = []
    if changed:
        notes.extend(changed)
    dropped = len(rates_c) - len(new_rates_c)
    if dropped > 0:
        notes.append(f"단계 {dropped}개를 줄였습니다.")
    if extended:
        notes.append(
            f"단계 {extended}개를 추가했습니다. 추가된 단계는 마지막 단계와 같은 "
            "전하량·전압 한계를 따릅니다."
        )
    if not notes:
        notes.append("전류가 그대로여서 시간과 전압도 바뀌지 않았습니다.")

    warnings = [
        "시간은 정전류 구간의 전하량 보존(C × t 일정)으로 계산한 값입니다. "
        "각 단계는 CCCV 라서 전압 한계 도달 후 감쇠 구간이 있고, 그 구간은 "
        "셀 임피던스에 따라 달라지므로 모델에 반영되어 있지 않습니다.",
        "전압 한계는 코퍼스 측정값을 그대로 옮긴 것이며 새 전류에서 재측정된 값이 "
        "아닙니다. CTSPro 재열기 확인 전에는 검증되지 않은 값으로 두십시오.",
    ]
    if extended:
        warnings.append(
            "추가된 단계의 전압 한계는 마지막 측정값을 반복한 것입니다. "
            "실제 목표 전압은 직접 확인해 입력하십시오."
        )

    return FastChargePlan(
        rates_c=tuple(float(rate) for rate in new_rates_c),
        voltages_v=tuple(scaled_voltages),
        times_s=tuple(scaled_times),
        notes=tuple(notes),
        warnings=tuple(warnings),
    )


__all__ = ["FastChargePlan", "fast_charge_for_rates"]
