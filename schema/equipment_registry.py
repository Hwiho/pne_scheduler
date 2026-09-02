"""Per-PNE equipment registry: rating, CTS build, SCH layout profiles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .equipment import EquipmentRating, get_equipment_rating, normalize_pne_unit

REGISTRY_PATH = Path(__file__).resolve().parents[1] / "planning" / "EQUIPMENT_REGISTRY.json"


@dataclass(frozen=True, slots=True)
class SchLayoutProfile:
    file_version: str
    payload_offset: int
    step_size: int
    dominant: bool = False
    source: str = "observed"


@dataclass(frozen=True, slots=True)
class UnitEquipmentProfile:
    unit: str
    corpus_zip: str | None
    corpus_zip_allowed_for_analysis: bool
    rating: EquipmentRating | None
    ctspro_build: str | None
    ctspro_build_source: str | None
    layouts_observed: tuple[SchLayoutProfile, ...]
    layouts_confirmed: tuple[SchLayoutProfile, ...]
    writer_layout_key: str | None


def _parse_layout_rows(rows: list[dict] | None, source: str) -> tuple[SchLayoutProfile, ...]:
    out: list[SchLayoutProfile] = []
    for row in rows or []:
        out.append(
            SchLayoutProfile(
                file_version=row["file_version"],
                payload_offset=int(row["payload_offset"]),
                step_size=int(row["step_size"]),
                dominant=bool(row.get("dominant", False)),
                source=source,
            )
        )
    return tuple(out)


@lru_cache(maxsize=1)
def load_equipment_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def get_unit_equipment_profile(unit: str) -> UnitEquipmentProfile | None:
    doc = load_equipment_registry()
    canonical = normalize_pne_unit(unit)
    if canonical is None:
        return None
    row = doc.get("units", {}).get(canonical)
    if row is None:
        return None
    return UnitEquipmentProfile(
        unit=canonical,
        corpus_zip=row.get("corpus_zip"),
        corpus_zip_allowed_for_analysis=bool(row.get("corpus_zip_allowed_for_analysis", False)),
        rating=get_equipment_rating(canonical),
        ctspro_build=row.get("ctspro_build"),
        ctspro_build_source=row.get("ctspro_build_source"),
        layouts_observed=_parse_layout_rows(row.get("sch_layouts_observed"), "unit_zip_corpus"),
        layouts_confirmed=_parse_layout_rows(row.get("sch_layouts_confirmed"), "golden_confirmed"),
        writer_layout_key=row.get("writer_layout_key"),
    )


def layout_profile_key(profile: SchLayoutProfile) -> str:
    return f"{profile.file_version}/{profile.step_size}"


def get_dominant_layout_for_unit(unit: str) -> SchLayoutProfile | None:
    profile = get_unit_equipment_profile(unit)
    if profile is None:
        return None
    for layout in profile.layouts_confirmed:
        return layout
    for layout in profile.layouts_observed:
        if layout.dominant:
            return layout
    if profile.layouts_observed:
        return profile.layouts_observed[0]
    return None
