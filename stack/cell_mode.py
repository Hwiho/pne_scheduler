"""Mono vs multi (stack) cell mode inference."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

_MULTI_PATTERN = re.compile(
    r"multi|멀티|stack\s*cell|stackcell|bicell|양면|2multi|8M2U|\d+M\d+U",
    re.IGNORECASE,
)
_MONO_PATTERN = re.compile(
    r"mono|모노|monocell|1M1U|단면",
    re.IGNORECASE,
)
_MU_PATTERN = re.compile(r"(?P<m>\d+)\s*M\s*(?P<u>\d+)\s*U", re.IGNORECASE)


class CellMode(StrEnum):
    MONO = "mono"
    MULTI = "multi"


@dataclass(frozen=True, slots=True)
class CellModeInference:
    mode: CellMode
    n_sheets_m: int
    n_unit_stack_u: int
    reaction_cells_k: int
    confidence: float
    source: str
    detail: str

    @property
    def is_mono(self) -> bool:
        return self.mode == CellMode.MONO


def reaction_cells_k(*, mode: CellMode, n_sheets_m: int = 1, n_unit_stack_u: int = 1) -> int:
    """K = M × U — count of bipolar (양면) electrode units in xMyU notation."""
    if mode == CellMode.MONO:
        return 1
    return max(1, n_sheets_m) * max(1, n_unit_stack_u)


def infer_cell_mode_from_filename(filename: str) -> CellModeInference:
    name = filename

    mu = _MU_PATTERN.search(name)
    if mu:
        m_val = int(mu.group("m"))
        u_val = int(mu.group("u"))
        mode = CellMode.MULTI if m_val > 1 or u_val > 1 else CellMode.MONO
        k = reaction_cells_k(mode=mode, n_sheets_m=m_val, n_unit_stack_u=u_val)
        return CellModeInference(
            mode=mode,
            n_sheets_m=m_val,
            n_unit_stack_u=u_val,
            reaction_cells_k=k,
            confidence=0.95,
            source="filename",
            detail=f"parsed {m_val}M{u_val}U → K={k} (M×U 양면전극)",
        )

    if _MULTI_PATTERN.search(name):
        k = reaction_cells_k(mode=CellMode.MULTI)
        return CellModeInference(
            mode=CellMode.MULTI,
            n_sheets_m=1,
            n_unit_stack_u=1,
            reaction_cells_k=k,
            confidence=0.8,
            source="filename",
            detail="multi/stack keyword",
        )

    if _MONO_PATTERN.search(name):
        k = reaction_cells_k(mode=CellMode.MONO)
        return CellModeInference(
            mode=CellMode.MONO,
            n_sheets_m=1,
            n_unit_stack_u=1,
            reaction_cells_k=k,
            confidence=0.85,
            source="filename",
            detail="mono keyword",
        )

    # Lab SJ1300 / bimodal schedules without explicit mode → assume mono first.
    k = reaction_cells_k(mode=CellMode.MONO)
    return CellModeInference(
        mode=CellMode.MONO,
        n_sheets_m=1,
        n_unit_stack_u=1,
        reaction_cells_k=k,
        confidence=0.5,
        source="default",
        detail="default mono (no multi keyword)",
    )
