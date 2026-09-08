"""The C-rates this lab actually types, as one-tap choices.

Free-text entry is kept — `C/3`, `1.5C`, `0.33` all parse — but the same handful
of values comes up every day, and typing `0.333` for what the protocol calls C/3
is both slower and a rounding error nobody meant to introduce.

Each preset says where it is used, so the list reads as the lab's own vocabulary
rather than a row of numbers. `usage` is what the UI shows beside the chip.
"""

from __future__ import annotations

from dataclasses import dataclass

from .defaults import (
    C_THIRD,
    CYCLE_DEFAULT_C_RATE,
    FORMATION_C_RATE,
)


@dataclass(frozen=True, slots=True)
class CRatePreset:
    value: float
    label: str
    usage: str

    def current_mA(self, nominal_capacity_mAh: float) -> float:
        return self.value * nominal_capacity_mAh


C_RATE_PRESETS: tuple[CRatePreset, ...] = (
    CRatePreset(FORMATION_C_RATE, "0.1C", "화성 · 초기 용량 확인"),
    CRatePreset(C_THIRD, "C/3", "RPT 기준 방전 · 용량 측정"),
    CRatePreset(CYCLE_DEFAULT_C_RATE, "0.5C", "표준 수명 사이클"),
    CRatePreset(1.0, "1C", "DC-IR 펄스 · 기준 충방전"),
    CRatePreset(1.5, "1.5C", "DC-IR 펄스 · 급속충전 하단"),
    CRatePreset(2.0, "2C", "DC-IR 펄스 · 급속충전"),
    CRatePreset(3.0, "3C", "급속충전 단계"),
    CRatePreset(4.0, "4C", "급속충전 1단 (Set2)"),
)


def presets_within(max_c_rate: float | None) -> tuple[CRatePreset, ...]:
    """Presets the equipment can actually deliver for this cell.

    A chip that would trip the current limit is worse than no chip: it invites a
    click that preflight then rejects. ``max_c_rate`` is the binding limit —
    the smaller of the cell limit and the unit rating — or ``None`` when it is
    not known yet, in which case everything is offered.
    """
    if max_c_rate is None or max_c_rate <= 0:
        return C_RATE_PRESETS
    return tuple(preset for preset in C_RATE_PRESETS if preset.value <= max_c_rate)


__all__ = ["C_RATE_PRESETS", "CRatePreset", "presets_within"]
