"""Lab corpus zip naming policy and unit zip validation."""

from __future__ import annotations

import re
from pathlib import Path

from .equipment import normalize_pne_unit

# Only PNE##.zip may attribute SCH binary stats to a cycler (user rule 2026-09-02).
UNIT_ZIP_FILENAME_RE = re.compile(r"^PNE\d+\.zip$", re.IGNORECASE)


def is_unit_numbered_zip(path: str | Path) -> bool:
    """True when archive filename is exactly PNE##.zip (case-insensitive)."""
    return bool(UNIT_ZIP_FILENAME_RE.match(Path(path).name))


def unit_id_from_zip(path: str | Path) -> str | None:
    """Extract canonical PNE## from a valid unit zip filename."""
    if not is_unit_numbered_zip(path):
        return None
    return normalize_pne_unit(Path(path).stem)


def validate_unit_corpus_zip(unit: str, zip_path: Path) -> str | None:
    """
    Return error message if zip cannot be used for per-cycler analysis.
    None means valid.
    """
    if not zip_path.is_file():
        return "missing"
    if not is_unit_numbered_zip(zip_path):
        return (
            f"zip must be named PNE##.zip for cycler analysis; got {zip_path.name!r}"
        )
    zip_unit = unit_id_from_zip(zip_path)
    expected = normalize_pne_unit(unit)
    if zip_unit is None or expected is None or zip_unit != expected:
        return f"zip unit {zip_unit!r} does not match requested unit {expected!r}"
    return None

