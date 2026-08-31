"""Footprint (FP) catalog — electrode size codes as width×height (mm)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .silicon_codes import is_silicon_combo_code

# Known footprints: code → (width_mm, height_mm, area_cm2)
# area_cm2 overrides auto-calc when design sheet value differs from W×H/100.
_KNOWN_FOOTPRINTS: dict[str, tuple[float, float, float | None]] = {
    "1818": (18.0, 18.0, 3.24),
    "3350": (33.0, 50.0, 16.5),
    "70150": (70.0, 150.0, 105.0),
    "70295": (70.0, 295.0, 206.5),
    "101295": (101.2, 95.0, 248.56),  # design ASSB footprint (preset 06)
}

_FP_TOKEN = re.compile(
    r"(?<![0-9])(?P<fp>1818|3350|70150|70295|101295)(?![0-9])"
)
_FP_GENERIC_5 = re.compile(r"(?<![0-9])(?P<w>\d{2})(?P<h>\d{3})(?![0-9])")
_FP_GENERIC_4 = re.compile(r"(?<![0-9])(?P<w>\d{2})(?P<h>\d{2})(?![0-9])")


@dataclass(frozen=True, slots=True)
class FootprintSpec:
    fp_id: str
    width_mm: float
    height_mm: float
    area_cm2: float
    source: str
    confidence: float

    @property
    def label(self) -> str:
        return f"FP{self.fp_id} ({self.width_mm:g}×{self.height_mm:g} mm, {self.area_cm2:.2f} cm²)"


def _area_cm2(width_mm: float, height_mm: float, override: float | None) -> float:
    if override is not None:
        return override
    return (width_mm * height_mm) / 100.0


def footprint_from_code(fp_id: str, *, source: str = "catalog", confidence: float = 0.95) -> FootprintSpec:
    if fp_id in _KNOWN_FOOTPRINTS:
        w, h, area_override = _KNOWN_FOOTPRINTS[fp_id]
        return FootprintSpec(
            fp_id=fp_id,
            width_mm=w,
            height_mm=h,
            area_cm2=_area_cm2(w, h, area_override),
            source=source,
            confidence=confidence,
        )
    # generic parse: treat as WW + HH(mm) for 4-digit codes
    if len(fp_id) == 4 and fp_id.isdigit() and not is_silicon_combo_code(fp_id):
        w = float(fp_id[:2])
        h = float(fp_id[2:])
        return FootprintSpec(
            fp_id=fp_id,
            width_mm=w,
            height_mm=h,
            area_cm2=_area_cm2(w, h, None),
            source=source,
            confidence=confidence * 0.7,
        )
    raise ValueError(f"Unknown footprint code: {fp_id}")


def infer_footprint_from_filename(filename: str) -> FootprintSpec | None:
    name = filename

    match = _FP_TOKEN.search(name)
    if match:
        return footprint_from_code(match.group("fp"), source="filename_token", confidence=0.95)

    # Avoid matching dates like 260511 — require leading underscore or start, or name prefix
    for pattern in (_FP_GENERIC_5, _FP_GENERIC_4):
        for match in pattern.finditer(name):
            token = match.group(0)
            # skip year-like 26xxxx fragments in project IDs when low confidence
            if token.startswith("26") and pattern is _FP_GENERIC_5:
                continue
            w = float(match.group("w"))
            h = float(match.group("h"))
            if w < 10 or h < 10:
                continue
            fp_id = token
            if is_silicon_combo_code(fp_id):
                continue
            if fp_id in _KNOWN_FOOTPRINTS:
                return footprint_from_code(fp_id, source="filename_generic", confidence=0.8)
            return FootprintSpec(
                fp_id=fp_id,
                width_mm=w,
                height_mm=h,
                area_cm2=_area_cm2(w, h, None),
                source="filename_generic",
                confidence=0.55,
            )

    # Leading token pattern: "임효진_3350_L.4.36..."
    leading = re.match(r"^[^_]+_(\d{4,6})_", name)
    if leading:
        code = leading.group(1)
        if is_silicon_combo_code(code):
            return None
        if code in _KNOWN_FOOTPRINTS:
            return footprint_from_code(code, source="filename_leading", confidence=0.9)
        if len(code) == 4:
            return footprint_from_code(code, source="filename_leading", confidence=0.75)

    return None


def list_known_footprint_ids() -> tuple[str, ...]:
    return tuple(_KNOWN_FOOTPRINTS.keys())
