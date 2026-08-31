"""Nominal capacity and C-rate back-calculation from FP + L + mono/multi."""

from __future__ import annotations

from dataclasses import dataclass

from .cell_mode import CellModeInference
from .footprint import FootprintSpec
from .levels import StackLevelGuess

# Calibrated: 3350 mono @ L4.3 → 21600 mA ≈ 1C
REF_FP_ID = "3350"
REF_AREA_CM2 = 16.5
REF_L_VALUE = 4.3
REF_1C_CURRENT_MA = 21_600.0


@dataclass(frozen=True, slots=True)
class CapacityContext:
    footprint: FootprintSpec
    cell_mode: CellModeInference
    l_level: StackLevelGuess
    nominal_capacity_mAh: float
    expected_1c_current_mA: float
    detail: str


def nominal_capacity_mAh(
    *,
    footprint: FootprintSpec,
    cell_mode: CellModeInference,
    l_value: float,
) -> float:
    """Q_nom(mAh) from FP area, stack K, and L-level scaling."""
    area_scale = footprint.area_cm2 / REF_AREA_CM2
    l_scale = l_value / REF_L_VALUE
    stack_scale = float(cell_mode.reaction_cells_k)
    return REF_1C_CURRENT_MA * area_scale * l_scale * stack_scale


def expected_1c_current_mA(
    *,
    footprint: FootprintSpec,
    cell_mode: CellModeInference,
    l_value: float,
) -> float:
    return nominal_capacity_mAh(
        footprint=footprint,
        cell_mode=cell_mode,
        l_value=l_value,
    )


def c_rate_from_current(
    current_mA: float,
    *,
    footprint: FootprintSpec,
    cell_mode: CellModeInference,
    l_value: float,
) -> float | None:
    if current_mA <= 0:
        return None
    capacity = nominal_capacity_mAh(
        footprint=footprint,
        cell_mode=cell_mode,
        l_value=l_value,
    )
    if capacity <= 0:
        return None
    return current_mA / capacity


def build_capacity_context(
    footprint: FootprintSpec,
    cell_mode: CellModeInference,
    l_level: StackLevelGuess,
) -> CapacityContext:
    q = nominal_capacity_mAh(
        footprint=footprint,
        cell_mode=cell_mode,
        l_value=l_level.l_value,
    )
    i1c = q
    detail = (
        f"Q_nom={q:.0f}mAh from FP{footprint.fp_id} "
        f"({footprint.area_cm2:.2f}cm²), {cell_mode.mode.value} K={cell_mode.reaction_cells_k}, "
        f"{l_level.label}"
    )
    return CapacityContext(
        footprint=footprint,
        cell_mode=cell_mode,
        l_level=l_level,
        nominal_capacity_mAh=q,
        expected_1c_current_mA=i1c,
        detail=detail,
    )
