"""Bimodal stack L-level definitions and inference from filename / sch fields."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

# Calibrated from QPEED fixture: fVref≈24.196 @ L4.3, fVref≈36.293 @ L6.5
FVREF_VOLTS_PER_L = 5.627

# Dominant 1C-scale current (mA) observed at L4.3 reference schedules
BASE_1C_CURRENT_MA_L43 = 21_600.0

# Mono cells without explicit L label in filename are almost always L5.0 in practice.
DEFAULT_MONO_L_VALUE = 5.0

REFERENCE_L_LEVELS: tuple[float, ...] = (4.3, 5.0, 5.5, 6.0, 6.5, 7.5)


class InferenceSource(str, Enum):
    FILENAME = "filename"
    FVREF = "fvref"
    CURRENT = "current"
    COMBINED = "combined"
    DEFAULT_MONO = "default_mono"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class StackLevelGuess:
    l_value: float
    label: str
    confidence: float
    source: InferenceSource
    detail: str = ""

    @property
    def nominal_capacity_mAh(self) -> float:
        return nominal_capacity_mAh_at_l(self.l_value)


@dataclass(frozen=True, slots=True)
class StackLevelInference:
    primary: StackLevelGuess
    filename_guess: StackLevelGuess | None
    fvref_guess: StackLevelGuess | None
    current_guess: StackLevelGuess | None


_L_EXPLICIT = re.compile(r"L[\s._-]*(\d(?:\.\d+)?)", re.IGNORECASE)


def l_label(l_value: float) -> str:
    text = f"{l_value:.2f}".rstrip("0").rstrip(".")
    return f"L{text}"


def nominal_capacity_mAh_at_l(l_value: float) -> float:
    """Scale reference capacity linearly with L level (C-rate model)."""
    return BASE_1C_CURRENT_MA_L43 * (l_value / 4.3)


def c_rate_from_current(current_mA: float, l_value: float) -> float | None:
    if current_mA <= 0:
        return None
    capacity = nominal_capacity_mAh_at_l(l_value)
    if capacity <= 0:
        return None
    return current_mA / capacity


def nearest_reference_l(value: float) -> float:
    return min(REFERENCE_L_LEVELS, key=lambda level: abs(level - value))


def default_mono_l_guess() -> StackLevelGuess:
    return StackLevelGuess(
        l_value=DEFAULT_MONO_L_VALUE,
        label=l_label(DEFAULT_MONO_L_VALUE),
        confidence=0.7,
        source=InferenceSource.DEFAULT_MONO,
        detail="mono default L5.0 (no explicit L in filename)",
    )


def l_from_fvref(f_vref: float, *, min_vref: float = 15.0) -> StackLevelGuess | None:
    if f_vref < min_vref:
        return None
    raw = f_vref / FVREF_VOLTS_PER_L
    nearest = nearest_reference_l(raw)
    error = abs(raw - nearest)
    confidence = max(0.2, 1.0 - error / 1.5)
    return StackLevelGuess(
        l_value=nearest,
        label=l_label(nearest),
        confidence=confidence,
        source=InferenceSource.FVREF,
        detail=f"fVref={f_vref:.3f}V → raw L≈{raw:.2f}",
    )


def infer_l_from_filename(filename: str) -> StackLevelGuess | None:
    """Infer L only from explicit L labels (e.g. L5.0, L.4.36).

    Silicon combo codes such as 6040 / 6535 / 7030 are NOT L-level markers.
    """
    match = _L_EXPLICIT.search(filename)
    if not match:
        return None

    value = float(match.group(1))
    nearest = nearest_reference_l(value)
    return StackLevelGuess(
        l_value=nearest,
        label=l_label(nearest),
        confidence=0.95 if abs(value - nearest) < 0.05 else 0.75,
        source=InferenceSource.FILENAME,
        detail=f"explicit {match.group(0)}",
    )


def infer_l_from_currents(currents_mA: list[float]) -> StackLevelGuess | None:
    positives = sorted({round(c, 1) for c in currents_mA if c >= 100.0}, reverse=True)
    if not positives:
        return None

    # Use the largest CCCV/CC-scale current as 1C anchor candidate.
    anchor = positives[0]
    raw_l = 4.3 * anchor / BASE_1C_CURRENT_MA_L43
    nearest = nearest_reference_l(raw_l)
    ratio_error = abs(anchor - expected_1c_current_mA(nearest)) / max(anchor, 1.0)
    confidence = max(0.25, 1.0 - ratio_error)
    return StackLevelGuess(
        l_value=nearest,
        label=l_label(nearest),
        confidence=confidence,
        source=InferenceSource.CURRENT,
        detail=f"I_ref≈{anchor:.0f}mA → raw L≈{raw_l:.2f}",
    )


def expected_1c_current_mA(l_value: float) -> float:
    return BASE_1C_CURRENT_MA_L43 * (l_value / 4.3)


def infer_stack_level(
    filename: str,
    step_f_vrefs: list[float],
    step_currents_mA: list[float],
    *,
    is_mono: bool = True,
) -> StackLevelInference:
    filename_guess = infer_l_from_filename(filename)

    active_vrefs = [v for v in step_f_vrefs if v >= 15.0]
    fvref_guess = None
    if active_vrefs:
        active_vrefs.sort()
        median_vref = active_vrefs[len(active_vrefs) // 2]
        fvref_guess = l_from_fvref(median_vref)

    current_guess = infer_l_from_currents(step_currents_mA)

    if filename_guess is not None and filename_guess.confidence >= 0.8:
        primary = StackLevelGuess(
            l_value=filename_guess.l_value,
            label=filename_guess.label,
            confidence=filename_guess.confidence,
            source=InferenceSource.COMBINED,
            detail=_combined_detail(filename_guess, fvref_guess, current_guess),
        )
        return StackLevelInference(
            primary=primary,
            filename_guess=filename_guess,
            fvref_guess=fvref_guess,
            current_guess=current_guess,
        )

    if is_mono:
        if filename_guess is not None:
            primary = StackLevelGuess(
                l_value=filename_guess.l_value,
                label=filename_guess.label,
                confidence=filename_guess.confidence,
                source=InferenceSource.COMBINED,
                detail=_combined_detail(filename_guess, fvref_guess, current_guess),
            )
        else:
            primary = default_mono_l_guess()
        return StackLevelInference(
            primary=primary,
            filename_guess=filename_guess,
            fvref_guess=fvref_guess,
            current_guess=current_guess,
        )

    candidates = [g for g in (filename_guess, fvref_guess, current_guess) if g is not None]
    if not candidates:
        primary = StackLevelGuess(
            l_value=DEFAULT_MONO_L_VALUE,
            label=l_label(DEFAULT_MONO_L_VALUE),
            confidence=0.2,
            source=InferenceSource.UNKNOWN,
            detail="default L5.0 (no signals)",
        )
        return StackLevelInference(
            primary=primary,
            filename_guess=filename_guess,
            fvref_guess=fvref_guess,
            current_guess=current_guess,
        )

    score_by_l: dict[float, float] = {}
    detail_parts: list[str] = []
    for guess in candidates:
        weight = 1.0
        if guess is filename_guess and guess.confidence >= 0.8:
            weight = 1.5
        score_by_l[guess.l_value] = score_by_l.get(guess.l_value, 0.0) + guess.confidence * weight
        detail_parts.append(f"{guess.source.value}:{guess.label}({guess.confidence:.2f})")

    best_l = max(score_by_l, key=score_by_l.get)
    best_score = score_by_l[best_l]
    primary = StackLevelGuess(
        l_value=best_l,
        label=l_label(best_l),
        confidence=min(0.99, best_score / max(len(candidates), 1)),
        source=InferenceSource.COMBINED,
        detail="; ".join(detail_parts),
    )
    return StackLevelInference(
        primary=primary,
        filename_guess=filename_guess,
        fvref_guess=fvref_guess,
        current_guess=current_guess,
    )


def _combined_detail(
    filename_guess: StackLevelGuess | None,
    fvref_guess: StackLevelGuess | None,
    current_guess: StackLevelGuess | None,
) -> str:
    parts: list[str] = []
    for guess in (filename_guess, fvref_guess, current_guess):
        if guess is not None:
            parts.append(f"{guess.source.value}:{guess.label}({guess.confidence:.2f})")
    return "; ".join(parts)
