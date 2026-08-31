"""Cell-level parameters shared across experiment modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class CellProfile:
    """Nominal cell parameters for C-rate and limit checks."""

    nominal_capacity_mAh: float
    v_max: float
    v_min: float
    max_current_mA: float | None = None
    formation_capacity_mAh: float | None = None

    def __post_init__(self) -> None:
        if self.nominal_capacity_mAh <= 0:
            raise ValueError("nominal_capacity_mAh must be positive")
        if self.v_max <= self.v_min:
            raise ValueError("v_max must be greater than v_min")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CellProfile:
        return cls(**data)
