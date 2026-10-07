"""Shared nominal-capacity accounting for discharge SOC ladders.

Rest steps change neither the nominal capacity already discharged nor the SOC
used for the next ladder interval.  A time-bounded discharge pulse consumes a
fraction ``C-rate * seconds / 3600`` of nominal capacity.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

UNCONFIRMED_ENTRY = "unconfirmed_entry"
USER_CONFIRMED_START_SOC = "user_confirmed_start_soc"
CHARGE_TO_FULL = "charge_to_full"
PREPARATION_POLICIES = frozenset(
    {UNCONFIRMED_ENTRY, USER_CONFIRMED_START_SOC, CHARGE_TO_FULL}
)


def is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def pulse_capacity_fraction(c_rate: float, duration_s: float) -> float:
    """Nominal-capacity fraction removed by one constant-current pulse."""
    return float(c_rate) * float(duration_s) / 3600.0


def ladder_capacity_fractions(
    *,
    start_soc: float,
    soc_fractions: Sequence[float],
    pulse_c_rates: Sequence[float],
    pulse_s: float,
) -> list[float]:
    """Return each SOC-setting discharge fraction, including earlier pulses."""
    remaining_soc = float(start_soc)
    pulse_fraction = sum(
        pulse_capacity_fraction(rate, pulse_s) for rate in pulse_c_rates
    )
    deltas: list[float] = []
    for target_soc in soc_fractions:
        target = float(target_soc)
        deltas.append(remaining_soc - target)
        remaining_soc = target - pulse_fraction
    return deltas


def validate_soc_ladder(
    *,
    start_soc: object,
    soc_fractions: Sequence[object],
    setting_c_rate: object,
    pulse_c_rates: Sequence[object],
    pulse_s: object,
    rest_s: object,
    preparation_policy: str,
    dcr_start_s: object | None = None,
    dcr_end_s: object | None = None,
) -> list[str]:
    """Validate values needed for physically consistent nominal SOC accounting."""
    errors: list[str] = []
    if preparation_policy not in PREPARATION_POLICIES:
        errors.append(
            "preparation_policy must be 'unconfirmed_entry', "
            "'user_confirmed_start_soc', or user-selected 'charge_to_full'"
        )
    if not is_finite_number(start_soc) or not 0.0 <= float(start_soc) <= 1.0:
        errors.append("start_soc must be finite and between 0 and 1")
    elif preparation_policy == CHARGE_TO_FULL and float(start_soc) != 1.0:
        errors.append("charge_to_full requires start_soc == 1")
    if not soc_fractions:
        errors.append("soc_fractions must not be empty")
    elif any(not is_finite_number(soc) for soc in soc_fractions):
        errors.append("SOC fractions must be finite")
    else:
        socs = [float(soc) for soc in soc_fractions]
        if any(not 0.0 <= soc <= 1.0 for soc in socs):
            errors.append("SOC fractions must be between 0 and 1")
        if any(later >= earlier for earlier, later in zip(socs, socs[1:])):
            errors.append("SOC fractions must be strictly descending")

    if not is_finite_number(setting_c_rate) or float(setting_c_rate) <= 0.0:
        errors.append("SOC-setting C-rate must be finite and positive")
    if any(not is_finite_number(rate) or float(rate) <= 0.0 for rate in pulse_c_rates):
        errors.append("DC-IR pulse C-rates must be positive finite numbers")
    if pulse_c_rates and (
        not is_finite_number(pulse_s) or float(pulse_s) <= 0.0
    ):
        errors.append("pulse duration must be finite and positive")
    if not is_finite_number(rest_s) or float(rest_s) <= 0.0:
        errors.append("rest duration must be finite and positive")

    if pulse_c_rates and dcr_start_s is not None and (
        not is_finite_number(dcr_start_s) or float(dcr_start_s) < 0.0
    ):
        errors.append("DCR start time must be finite and non-negative")
    if pulse_c_rates and dcr_end_s is not None and (
        not is_finite_number(dcr_end_s) or float(dcr_end_s) <= 0.0
    ):
        errors.append("DCR end time must be finite and positive")
    if (
        pulse_c_rates
        and is_finite_number(dcr_start_s)
        and is_finite_number(dcr_end_s)
        and float(dcr_start_s) >= float(dcr_end_s)
    ):
        errors.append("DCR interval must have start time before end time")
    if (
        pulse_c_rates
        and is_finite_number(dcr_end_s)
        and is_finite_number(pulse_s)
        and float(dcr_end_s) > float(pulse_s)
    ):
        errors.append("DCR interval must end within the pulse duration")

    pulse_values_are_usable = not pulse_c_rates or (
        is_finite_number(pulse_s) and float(pulse_s) > 0.0
    )
    values_are_usable = (
        is_finite_number(start_soc)
        and bool(soc_fractions)
        and all(is_finite_number(soc) for soc in soc_fractions)
        and all(is_finite_number(rate) and float(rate) > 0.0 for rate in pulse_c_rates)
        and pulse_values_are_usable
    )
    if values_are_usable:
        socs = [float(soc) for soc in soc_fractions]
        deltas = ladder_capacity_fractions(
            start_soc=float(start_soc),
            soc_fractions=socs,
            pulse_c_rates=[float(rate) for rate in pulse_c_rates],
            pulse_s=float(pulse_s) if pulse_c_rates else 0.0,
        )
        if any(delta <= 0.0 for delta in deltas):
            errors.append(
                "each SOC-setting interval must remain positive after prior pulse capacity"
            )
        consumed_per_level = sum(
            pulse_capacity_fraction(float(rate), float(pulse_s))
            for rate in pulse_c_rates
        )
        if pulse_c_rates and any(soc - consumed_per_level < 0.0 for soc in socs):
            errors.append("DC-IR pulses would consume capacity below 0% nominal SOC")
    return errors


__all__ = [
    "PREPARATION_POLICIES",
    "CHARGE_TO_FULL",
    "UNCONFIRMED_ENTRY",
    "USER_CONFIRMED_START_SOC",
    "is_finite_number",
    "ladder_capacity_fractions",
    "pulse_capacity_fraction",
    "validate_soc_ladder",
]
