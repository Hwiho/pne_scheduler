"""Unit formatting and parsing for the structured parameter forms.

Every user-facing number in the workspace passes through this module, so a
value shown as ``1.5C`` in one panel and ``432 mA`` in another is always the
same stored float.  Parsers accept the shapes lab users actually type
(``C/3``, ``30분``, ``1h30m``) instead of forcing raw SI seconds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..engine.c_rate import format_c_rate_label

_C_RATE_DIVIDED = re.compile(r"^\s*[Cc]\s*/\s*([0-9]*\.?[0-9]+)\s*$")
_C_RATE_SUFFIX = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*[Cc]?\s*$")
_DURATION_TOKEN = re.compile(
    r"([0-9]*\.?[0-9]+)\s*(일|시간|분|초|d|day|days|h|hr|hour|hours|m|min|mins|s|sec|secs)?",
    re.IGNORECASE,
)
_DURATION_FACTORS: dict[str, float] = {
    "일": 86400.0, "d": 86400.0, "day": 86400.0, "days": 86400.0,
    "시간": 3600.0, "h": 3600.0, "hr": 3600.0, "hour": 3600.0, "hours": 3600.0,
    "분": 60.0, "m": 60.0, "min": 60.0, "mins": 60.0,
    "초": 1.0, "s": 1.0, "sec": 1.0, "secs": 1.0,
}


class UnitParseError(ValueError):
    """Raised when user text cannot be read as the expected unit."""


# ---------------------------------------------------------------- formatting


def format_c_rate(value: float) -> str:
    """``0.3333 -> 'C/3'``; falls back to the engine's snap-to-preset label.

    Zero and negative rates are not schedulable, but they do appear as range
    bounds and as half-typed input, so they format instead of raising.
    """
    number = float(value)
    if number <= 0:
        return f"{number:g}C"
    return format_c_rate_label(number)


def format_current_mA(value: float) -> str:
    if abs(value) >= 1000.0:
        return f"{value / 1000.0:.3g} A"
    if abs(value) >= 10.0:
        return f"{value:.4g} mA"
    return f"{value:.3g} mA"


def format_voltage(value: float) -> str:
    return f"{value:.3f} V"


def format_percent(value: float) -> str:
    text = f"{value:.4g}"
    return f"{text}%"


def format_fraction_as_soc(value: float) -> str:
    return f"SOC {value * 100:.0f}%"


def format_duration_ko(seconds: float) -> str:
    """Korean duration, coarsened to the two most significant units."""
    total = max(0, round(float(seconds)))
    if total == 0:
        return "0초"
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}일")
    if hours:
        parts.append(f"{hours}시간")
    if minutes:
        parts.append(f"{minutes}분")
    if secs:
        parts.append(f"{secs}초")
    return " ".join(parts[:2])


def format_duration_input(seconds: float) -> str:
    """Round-trippable duration text for an entry widget (never lossy)."""
    total = float(seconds)
    if total <= 0:
        return "0초"
    if total >= 3600 and total % 3600 == 0:
        return f"{int(total // 3600)}시간"
    if total >= 60 and total % 60 == 0:
        return f"{int(total // 60)}분"
    if total == int(total):
        return f"{int(total)}초"
    return f"{total:g}초"


def format_count(value: float) -> str:
    return f"{int(round(value)):,}"


# ------------------------------------------------------------------ parsing


def parse_c_rate(text: str) -> float:
    """Accept ``0.5``, ``0.5C``, ``C/3``, ``c / 3`` and return a float rate."""
    raw = str(text).strip()
    if not raw:
        raise UnitParseError("C-rate 값을 입력하세요.")
    divided = _C_RATE_DIVIDED.match(raw)
    if divided:
        denominator = float(divided.group(1))
        if denominator == 0:
            raise UnitParseError("C/0 은 사용할 수 없습니다.")
        return 1.0 / denominator
    suffix = _C_RATE_SUFFIX.match(raw)
    if suffix:
        return float(suffix.group(1))
    raise UnitParseError(f"C-rate 로 읽을 수 없습니다: {raw!r} (예: 0.5, C/3, 1.5C)")


def parse_duration_s(text: str) -> float:
    """Accept ``600``, ``600s``, ``30분``, ``1시간 30분``, ``1h30m``, ``2일``."""
    raw = str(text).strip()
    if not raw:
        raise UnitParseError("시간 값을 입력하세요.")
    compact = raw.replace(" ", "").replace(",", "")
    total = 0.0
    position = 0
    while position < len(compact):
        match = _DURATION_TOKEN.match(compact, position)
        if match is None or match.end() == position:
            raise UnitParseError(
                f"시간으로 읽을 수 없습니다: {raw!r} (예: 30분, 1시간 30분, 600)"
            )
        factor = _DURATION_FACTORS.get((match.group(2) or "s").lower())
        if factor is None:
            raise UnitParseError(f"시간 단위를 읽을 수 없습니다: {raw!r}")
        total += float(match.group(1)) * factor
        position = match.end()
    return total


def parse_number(text: str) -> float:
    raw = str(text).strip().replace(",", "")
    if not raw:
        raise UnitParseError("값을 입력하세요.")
    try:
        return float(raw)
    except ValueError as exc:  # pragma: no cover - message path
        raise UnitParseError(f"숫자로 읽을 수 없습니다: {raw!r}") from exc


def parse_voltage(text: str) -> float:
    return parse_number(str(text).strip().rstrip("VvＶ").strip())


def parse_percent(text: str) -> float:
    return parse_number(str(text).strip().rstrip("%％").strip())


def parse_bool(text: str | bool) -> bool:
    if isinstance(text, bool):
        return text
    normalized = str(text).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on", "예", "사용", "포함"}:
        return True
    if normalized in {"0", "false", "no", "n", "off", "아니오", "미사용", "제외"}:
        return False
    raise UnitParseError(f"예/아니오 값으로 읽을 수 없습니다: {text!r}")


def split_list(text: str) -> list[str]:
    raw = str(text).strip().strip("[]")
    if not raw:
        return []
    return [chunk.strip() for chunk in raw.replace(";", ",").split(",") if chunk.strip()]


# ------------------------------------------------------------ derived values


@dataclass(frozen=True, slots=True)
class CurrentView:
    """A C-rate and its absolute current side by side, with headroom."""

    c_rate: float
    current_mA: float
    limit_mA: float | None = None

    @property
    def headroom_ratio(self) -> float | None:
        if not self.limit_mA:
            return None
        return self.current_mA / self.limit_mA

    @property
    def exceeds_limit(self) -> bool:
        ratio = self.headroom_ratio
        return ratio is not None and ratio > 1.0 + 1e-9

    def describe(self) -> str:
        text = f"{format_c_rate(self.c_rate)} = {format_current_mA(self.current_mA)}"
        ratio = self.headroom_ratio
        if ratio is None:
            return text
        return f"{text} · 장비 한계 {format_current_mA(self.limit_mA or 0)}의 {ratio * 100:.0f}%"


__all__ = [
    "CurrentView",
    "UnitParseError",
    "format_c_rate",
    "format_count",
    "format_current_mA",
    "format_duration_input",
    "format_duration_ko",
    "format_fraction_as_soc",
    "format_percent",
    "format_voltage",
    "parse_bool",
    "parse_c_rate",
    "parse_duration_s",
    "parse_number",
    "parse_percent",
    "parse_voltage",
    "split_list",
]
