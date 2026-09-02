"""Official PNE unit recommended max current ratings (user guideline)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RATINGS_PATH = Path(__file__).resolve().parents[1] / "planning" / "EQUIPMENT_CURRENT_RATINGS.json"

_UNIT_RE = re.compile(r"PNE\s*0*(\d+)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class EquipmentRating:
    unit: str
    rating: str
    rating_mA: int
    tier: str
    aliases: tuple[str, ...] = ()


def normalize_pne_unit(name: str) -> str | None:
    """Return canonical unit id like PNE02 from PNE2, pne 02, etc."""
    text = name.strip().upper().replace(" ", "")
    if text.startswith("PNE"):
        digits = text[3:].lstrip("0") or "0"
        if digits.isdigit():
            return f"PNE{int(digits):02d}"
    match = _UNIT_RE.search(name)
    if match:
        return f"PNE{int(match.group(1)):02d}"
    return None


@lru_cache(maxsize=1)
def load_equipment_ratings() -> dict:
    data = json.loads(RATINGS_PATH.read_text(encoding="utf-8"))
    alias_index: dict[str, str] = {}
    for unit, profile in data.get("by_unit", {}).items():
        for alias in profile.get("aliases", []):
            canonical = normalize_pne_unit(alias)
            if canonical:
                alias_index[canonical] = unit
            alias_index[alias.upper().replace(" ", "")] = unit
    data["_alias_index"] = alias_index
    return data


def get_equipment_rating(unit: str) -> EquipmentRating | None:
    doc = load_equipment_ratings()
    canonical = normalize_pne_unit(unit)
    if canonical is None:
        return None
    by_unit = doc.get("by_unit", {})
    profile = by_unit.get(canonical)
    if profile is None:
        alias_index = doc.get("_alias_index", {})
        mapped = alias_index.get(canonical) or alias_index.get(unit.upper().replace(" ", ""))
        if mapped:
            profile = by_unit.get(mapped)
            canonical = mapped
    if profile is None:
        return None
    return EquipmentRating(
        unit=canonical,
        rating=profile["rating"],
        rating_mA=int(profile["rating_mA"]),
        tier=profile["tier"],
        aliases=tuple(profile.get("aliases", [])),
    )


def rating_hint_for_unit(unit: str, corpus_max_mA: float | None = None) -> dict:
    from .equipment_registry import get_unit_equipment_profile

    official = get_equipment_rating(unit)
    equip = get_unit_equipment_profile(unit)
    if official:
        return {
            "inferred_from_corpus": None,
            "official_rating": official.rating,
            "official_rating_mA": official.rating_mA,
            "ctspro_build": equip.ctspro_build if equip else None,
            "ctspro_build_source": equip.ctspro_build_source if equip else None,
            "max_current_mA_seen": corpus_max_mA,
            "corpus_exceeds_official": bool(
                corpus_max_mA and corpus_max_mA > official.rating_mA * 1.01
            ),
            "confirmation": "user_guideline",
        }
    return {
        "inferred_from_corpus": "unlisted_in_guideline",
        "official_rating": None,
        "ctspro_build": equip.ctspro_build if equip else None,
        "ctspro_build_source": equip.ctspro_build_source if equip else None,
        "max_current_mA_seen": corpus_max_mA,
        "confirmation": "needs_user_or_lab_metadata",
    }
