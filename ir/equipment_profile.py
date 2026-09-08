"""Which cycler this schedule is for — carried in the project, not guessed.

A ``.schproj`` that does not say which PNE unit it targets cannot be checked
against a real current rating or a real SCH layout, so every safety answer it
gives is provisional.  This makes the target explicit and persists it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ..schema.equipment_registry import (
    get_dominant_layout_for_unit,
    get_unit_equipment_profile,
)
from ..schema.equipment import normalize_pne_unit


@dataclass(frozen=True, slots=True)
class EquipmentProfile:
    """Target cycler: unit, current rating, CTSPro build, and SCH layout."""

    unit: str
    max_current_mA: float | None = None
    rating_label: str | None = None
    ctspro_build: str | None = None
    ctspro_build_source: str | None = None
    sch_file_version: str | None = None
    sch_payload_offset: int | None = None
    sch_step_size: int | None = None
    source: str = "manual"
    layout_confirmed: bool = False
    notes: str = ""

    @property
    def layout_key(self) -> str | None:
        if self.sch_file_version is None or self.sch_step_size is None:
            return None
        return f"{self.sch_file_version}/{self.sch_step_size}"

    @property
    def is_complete(self) -> bool:
        """True when the profile can back an equipment-facing decision."""
        return bool(self.unit and self.max_current_mA and self.layout_key)

    def missing_fields(self) -> tuple[str, ...]:
        missing: list[str] = []
        if not self.unit:
            missing.append("장비 번호")
        if not self.max_current_mA:
            missing.append("최대 전류")
        if not self.layout_key:
            missing.append("SCH layout")
        if not self.ctspro_build:
            missing.append("CTSPro 버전")
        return tuple(missing)

    def describe(self) -> str:
        parts = [self.unit or "장비 미지정"]
        if self.max_current_mA:
            parts.append(f"최대 {self.max_current_mA:g} mA")
        if self.ctspro_build:
            parts.append(f"CTSPro {self.ctspro_build}")
        if self.layout_key:
            parts.append(f"layout {self.layout_key}")
        return " · ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EquipmentProfile:
        known = {key: data[key] for key in cls.__dataclass_fields__ if key in data}
        return cls(**known)

    @classmethod
    def from_unit(cls, unit: str) -> EquipmentProfile:
        """Build a profile from the shipped registry; unknown units stay blank."""
        canonical = normalize_pne_unit(unit) or unit.strip().upper()
        registry = get_unit_equipment_profile(canonical)
        if registry is None:
            return cls(unit=canonical, source="manual", notes="레지스트리에 없는 장비입니다.")
        layout = get_dominant_layout_for_unit(canonical)
        confirmed = bool(registry.layouts_confirmed)
        return cls(
            unit=registry.unit,
            max_current_mA=float(registry.rating.rating_mA) if registry.rating else None,
            rating_label=registry.rating.rating if registry.rating else None,
            ctspro_build=registry.ctspro_build,
            ctspro_build_source=registry.ctspro_build_source,
            sch_file_version=layout.file_version if layout else None,
            sch_payload_offset=layout.payload_offset if layout else None,
            sch_step_size=layout.step_size if layout else None,
            source="registry",
            layout_confirmed=confirmed,
        )


def known_units() -> tuple[str, ...]:
    from ..schema.equipment_registry import load_equipment_registry

    return tuple(sorted(load_equipment_registry().get("units", {})))


def effective_current_limit_mA(
    cell_max_current_mA: float | None,
    equipment: EquipmentProfile | None,
) -> float | None:
    """The binding limit: the smaller of the cell's and the cycler's."""
    limits = [
        value
        for value in (
            cell_max_current_mA,
            equipment.max_current_mA if equipment else None,
        )
        if value
    ]
    return min(limits) if limits else None


__all__ = [
    "EquipmentProfile",
    "effective_current_limit_mA",
    "known_units",
]
