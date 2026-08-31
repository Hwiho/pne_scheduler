"""Infer experiment protocol from parsed schedule steps and filename hints."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .defaults import (
    CAPACHECK_INITIAL_C_RATE,
    CAPACHECK_MEASUREMENT_C_RATE,
    CYCLE_DEFAULT_C_RATE,
    FORMATION_C_RATE,
    RPT_DCIR_PULSE_C_RATE_ALT,
    RPT_DCIR_PULSE_C_RATE_DEFAULT,
    RPT_DISCHARGE_C_RATE,
)

C_THIRD = 1.0 / 3.0


class InferredProtocol(StrEnum):
    FORMATION = "formation"
    CAPACHECK = "capacheck"
    DERATING = "derating"
    CYCLE_LIFE = "cycle_life"
    INSITU_CYCLE = "insitu_cycle"
    RPT = "rpt"
    QC = "qc"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ProtocolInference:
    protocol: InferredProtocol
    confidence: float
    detail: str
    expected_c_rates: tuple[str, ...] = ()


def _close(value: float | None, target: float, *, rtol: float = 0.12) -> bool:
    if value is None or value <= 0:
        return False
    return abs(value - target) / target <= rtol


def _active_c_rates(steps: list[object]) -> list[float]:
    rates: list[float] = []
    for step in steps:
        iref = getattr(step, "f_iref", 0.0)
        if iref <= 100:
            continue
        preset = getattr(step, "c_rate_preset", None)
        raw = getattr(step, "c_rate", None)
        rate = preset if preset is not None else raw
        if rate is not None and rate > 0:
            rates.append(rate)
    return rates


def _has_rpt_pattern(steps: list[object], rates: list[float]) -> bool:
    filename_hint = False
    has_c3 = any(_close(r, RPT_DISCHARGE_C_RATE) for r in rates)
    has_pulse = any(
        _close(r, RPT_DCIR_PULSE_C_RATE_DEFAULT) or _close(r, RPT_DCIR_PULSE_C_RATE_ALT)
        for r in rates
    )
    step_types = [getattr(s, "step_type", "") for s in steps]
    has_imp = any(t in ("IMPEDANCE", "IMP") for t in step_types)
    return has_c3 and (has_pulse or has_imp)


def infer_protocol_from_schedule(
    filename: str,
    steps: list[object],
    *,
    filename_category: str | None = None,
) -> ProtocolInference:
    """Infer lab protocol from C-rate fingerprints and filename."""
    name = filename.lower()
    rates = _active_c_rates(steps)

    if filename_category == "formation" or _filename_is_formation(name):
        return ProtocolInference(
            protocol=InferredProtocol.FORMATION,
            confidence=0.9,
            detail="FM / formation filename",
            expected_c_rates=("0.1C",),
        )

    if filename_category == "rpt" or "rpt" in name:
        return ProtocolInference(
            protocol=InferredProtocol.RPT,
            confidence=0.9,
            detail="RPT filename",
            expected_c_rates=("C/3", "1.0C", "1.5C"),
        )

    if "qc" in name and "cycle" not in name:
        return ProtocolInference(
            protocol=InferredProtocol.QC,
            confidence=0.85,
            detail="QC fast-charge filename",
            expected_c_rates=("1C", "C/3"),
        )

    if (
        filename_category in ("capacheck",)
        or "capacheck" in name
        or "derating" in name
        or "0.1c capa" in name
        or ("capa" in name and "0.1" in name)
    ):
        return ProtocolInference(
            protocol=InferredProtocol.CAPACHECK,
            confidence=0.85,
            detail="capacheck / derating filename",
            expected_c_rates=("0.1C", "C/3"),
        )

    if "insitu" in name or "in-situ" in name or "in situ" in name:
        return ProtocolInference(
            protocol=InferredProtocol.INSITU_CYCLE,
            confidence=0.85,
            detail="in-situ cycle (no RPT)",
            expected_c_rates=("0.5C",),
        )

    if not rates:
        if filename_category == "cycle_life" or "cycle" in name:
            return ProtocolInference(
                protocol=InferredProtocol.CYCLE_LIFE,
                confidence=0.6,
                detail="cycle filename, no current steps",
                expected_c_rates=("0.5C",),
            )
        return ProtocolInference(
            protocol=InferredProtocol.UNKNOWN,
            confidence=0.1,
            detail="no active C-rate steps",
        )

    has_01 = any(_close(r, FORMATION_C_RATE) for r in rates)
    has_c3 = any(_close(r, CAPACHECK_MEASUREMENT_C_RATE) for r in rates)
    has_05 = any(_close(r, CYCLE_DEFAULT_C_RATE) for r in rates)
    c3_count = sum(1 for r in rates if _close(r, CAPACHECK_MEASUREMENT_C_RATE))

    if _has_rpt_pattern(steps, rates):
        return ProtocolInference(
            protocol=InferredProtocol.RPT,
            confidence=0.8,
            detail="C/3 discharge + DC-IR pulse pattern",
            expected_c_rates=("C/3", "1.5C"),
        )

    if has_01 and has_c3:
        detail = "0.1C then C/3"
        if c3_count >= 2:
            detail += " (double C/3)"
        return ProtocolInference(
            protocol=InferredProtocol.CAPACHECK,
            confidence=0.8,
            detail=detail,
            expected_c_rates=("0.1C", "C/3"),
        )

    if has_05 and not _has_rpt_pattern(steps, rates):
        proto = InferredProtocol.CYCLE_LIFE
        detail = "dominant 0.5C cycle"
        if filename_category == "cycle_life" or "cycle" in name:
            proto = InferredProtocol.INSITU_CYCLE if "rpt" not in name else InferredProtocol.CYCLE_LIFE
            detail = "0.5C cycle" + (" (in-situ, no RPT)" if proto == InferredProtocol.INSITU_CYCLE else "")
        return ProtocolInference(
            protocol=proto,
            confidence=0.75,
            detail=detail,
            expected_c_rates=("0.5C",),
        )

    if has_01 and not has_c3 and not has_05:
        return ProtocolInference(
            protocol=InferredProtocol.FORMATION,
            confidence=0.7,
            detail="dominant 0.1C",
            expected_c_rates=("0.1C",),
        )

    if filename_category == "cycle_life" or "0.5c cycle" in name or "0.5c" in name:
        return ProtocolInference(
            protocol=InferredProtocol.CYCLE_LIFE,
            confidence=0.65,
            detail="cycle filename fallback",
            expected_c_rates=("0.5C",),
        )

    return ProtocolInference(
        protocol=InferredProtocol.UNKNOWN,
        confidence=0.3,
        detail="no matching protocol fingerprint",
    )


def _filename_is_formation(name: str) -> bool:
    import re

    return bool(
        re.search(r"(?:^|[_\s-])fm(?:$|[_\s.-])|formation|c1\s*%", name, re.IGNORECASE)
    )
