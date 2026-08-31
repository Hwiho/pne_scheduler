"""C-rate presets, conversion, and snap-to-standard for lab schedules."""

from __future__ import annotations

from dataclasses import dataclass

from ..ir.cell_profile import CellProfile

# Lab-standard C-rates (mono / general experiments).
# Rates above FAST_CHARGE_MIN_C_RATE are mainly QPEED, QC cycle, etc.
FAST_CHARGE_MIN_C_RATE = 2.5

C_THIRD = 1.0 / 3.0
C_HALF = 0.5


@dataclass(frozen=True, slots=True)
class CratePreset:
    value: float
    label: str


STANDARD_C_RATE_PRESETS: tuple[CratePreset, ...] = (
    CratePreset(0.1, "0.1C"),
    CratePreset(0.2, "0.2C"),
    CratePreset(C_THIRD, "C/3"),
    CratePreset(C_HALF, "C/2"),
    CratePreset(1.0, "1C"),
    CratePreset(1.5, "1.5C"),
    CratePreset(2.0, "2C"),
    CratePreset(2.5, "2.5C"),
    CratePreset(3.0, "3C"),
    CratePreset(3.5, "3.5C"),
    CratePreset(4.0, "4C"),
    CratePreset(4.5, "4.5C"),
    CratePreset(5.0, "5C"),
    CratePreset(5.5, "5.5C"),
    CratePreset(6.0, "6C"),
)

# Backward-compatible export: (C-rate value, inverse factor for C/x labels)
COMMON_C_RATE_PRESETS: tuple[tuple[float, float], ...] = tuple(
    (p.value, (1.0 / p.value if p.value not in (C_THIRD, C_HALF) else (3.0 if p.value == C_THIRD else 2.0)))
    for p in STANDARD_C_RATE_PRESETS
)


@dataclass(frozen=True, slots=True)
class CrateSnapResult:
    raw_c_rate: float
    preset: CratePreset | None
    label: str
    is_fast_charge: bool

    @property
    def snapped_value(self) -> float | None:
        return self.preset.value if self.preset is not None else None


def is_fast_charge_c_rate(c_rate: float) -> bool:
    """True when C-rate exceeds routine mono/cycle range (>2.5C)."""
    return c_rate > FAST_CHARGE_MIN_C_RATE


def snap_c_rate(c_rate: float, *, rtol: float = 0.06) -> CrateSnapResult:
    """Map a measured C-rate to the nearest lab preset when within tolerance."""
    if c_rate <= 0:
        raise ValueError("c_rate must be positive")

    best: CratePreset | None = None
    best_err = float("inf")
    for preset in STANDARD_C_RATE_PRESETS:
        err = abs(c_rate - preset.value) / preset.value
        if err < best_err:
            best_err = err
            best = preset

    if best is not None and best_err <= rtol:
        return CrateSnapResult(
            raw_c_rate=c_rate,
            preset=best,
            label=best.label,
            is_fast_charge=is_fast_charge_c_rate(c_rate),
        )

    return CrateSnapResult(
        raw_c_rate=c_rate,
        preset=None,
        label=f"~{c_rate:.2f}C",
        is_fast_charge=is_fast_charge_c_rate(c_rate),
    )


def format_c_rate_label(c_rate: float) -> str:
    """Human-readable C-rate label, preferring standard preset names."""
    return snap_c_rate(c_rate).label


def preset_values() -> tuple[float, ...]:
    return tuple(p.value for p in STANDARD_C_RATE_PRESETS)


def current_mA_from_c_rate(c_rate: float, cell: CellProfile) -> float:
    """I_mA = C_rate × Q_nominal_mAh."""
    if c_rate <= 0:
        raise ValueError("c_rate must be positive")
    return c_rate * cell.nominal_capacity_mAh


def c_rate_from_current_mA(current_mA: float, cell: CellProfile) -> float:
    if current_mA <= 0:
        raise ValueError("current_mA must be positive")
    return current_mA / cell.nominal_capacity_mAh


def capacity_mAh_from_fraction(fraction: float, cell: CellProfile) -> float:
    if not 0.0 < fraction <= 1.0:
        raise ValueError("fraction must be in (0, 1]")
    return fraction * cell.nominal_capacity_mAh


def validate_current_within_limits(current_mA: float, cell: CellProfile) -> list[str]:
    warnings: list[str] = []
    if cell.max_current_mA is not None and current_mA > cell.max_current_mA:
        warnings.append(
            f"Current {current_mA:.1f} mA exceeds cell max_current_mA={cell.max_current_mA:.1f}"
        )
    return warnings
