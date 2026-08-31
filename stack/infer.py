"""Unified cell geometry inference: FP → mono/multi → L → C-rate context."""

from __future__ import annotations

from dataclasses import dataclass

from .capacity import CapacityContext, build_capacity_context
from .cell_mode import CellModeInference, infer_cell_mode_from_filename
from .footprint import FootprintSpec, footprint_from_code, infer_footprint_from_filename
from .levels import StackLevelInference, infer_stack_level


@dataclass(frozen=True, slots=True)
class CellGeometryInference:
    footprint: FootprintSpec
    cell_mode: CellModeInference
    stack_level: StackLevelInference
    capacity: CapacityContext

    @property
    def is_mono(self) -> bool:
        return self.cell_mode.is_mono


def infer_cell_geometry(
    filename: str,
    step_f_vrefs: list[float],
    step_currents_mA: list[float],
) -> CellGeometryInference:
    """Pipeline: footprint → mono/multi (default mono) → L-level → capacity/C-rate basis."""
    footprint = infer_footprint_from_filename(filename)
    if footprint is None:
        footprint = footprint_from_code("3350", source="default", confidence=0.3)

    cell_mode = infer_cell_mode_from_filename(filename)
    stack_level = infer_stack_level(
        filename,
        step_f_vrefs,
        step_currents_mA,
        is_mono=cell_mode.is_mono,
    )
    capacity = build_capacity_context(footprint, cell_mode, stack_level.primary)

    return CellGeometryInference(
        footprint=footprint,
        cell_mode=cell_mode,
        stack_level=stack_level,
        capacity=capacity,
    )
