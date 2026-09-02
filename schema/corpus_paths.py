"""Resolve PNE##.zip corpus archive paths (repo example/ vs lab PC c:\\)."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ZIP_DIR = PACKAGE_ROOT / "example" / "corpus_zips"

# Lab PC default drop location (override with PNE_CORPUS_ZIP_DIR)
LAB_ZIP_ROOT = Path(os.environ.get("PNE_CORPUS_ZIP_DIR", "c:/"))


def corpus_zip_path(unit: str) -> Path:
    """Return path to PNE##.zip; prefers in-repo example/corpus_zips."""
    canonical = unit.upper()
    if not canonical.startswith("PNE"):
        canonical = f"PNE{canonical.lstrip('PNE')}"
    name = f"{canonical}.zip"
    in_repo = CORPUS_ZIP_DIR / name
    if in_repo.is_file():
        return in_repo
    on_lab = LAB_ZIP_ROOT / name
    if on_lab.is_file():
        return on_lab
    return in_repo


def default_corpus_zip_map(units: list[str] | None = None) -> dict[str, Path]:
    """Build unit → zip path map for all known corpus units."""
    if units is None:
        units = [
            "PNE01",
            "PNE02",
            "PNE03",
            "PNE04",
            "PNE05",
            "PNE06",
            "PNE07",
            "PNE08",
            "PNE09",
            "PNE22",
        ]
    return {u: corpus_zip_path(u) for u in units}
