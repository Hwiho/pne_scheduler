"""Silicon anode/cathode combination codes in filenames — not footprint (loading) values.

Examples: 6040, 6535, 7030 describe Si blend ratios, not electrode size (1818, 3350, …).
L-level is usually explicit in filenames (e.g. L5.0, L.4.36).
"""

from __future__ import annotations

# Known 4-digit silicon-combination tokens observed in lab filenames.
SILICON_COMBO_CODES: frozenset[str] = frozenset(
    {
        "6030",
        "6040",
        "6043",
        "6055",
        "6530",
        "6535",
        "7030",
        "7055",
    }
)

# 4-digit tokens with these two-digit prefixes are Si-combo codes unless catalogued as FP.
_SILICON_COMBO_PREFIXES: frozenset[str] = frozenset({"60", "65", "70"})


def is_silicon_combo_code(token: str) -> bool:
    """Return True when a filename token is a silicon blend code, not a loading FP."""
    if token in SILICON_COMBO_CODES:
        return True
    if len(token) == 4 and token.isdigit() and token[:2] in _SILICON_COMBO_PREFIXES:
        return True
    return False
