"""Classify PNE .sch files from filename patterns."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ScheduleCategory(StrEnum):
    CAPACHECK = "capacheck"
    FORMATION = "formation"
    CYCLE_LIFE = "cycle_life"
    INSITU_CYCLE = "insitu_cycle"
    RPT = "rpt"
    QPEED = "qpeed"
    HPPC = "hppc"
    UNKNOWN = "unknown"


class ProtocolVariant(StrEnum):
    """Filename-level sub-type within an experiment family."""

    NONE = "none"
    DERATING = "derating"  # capacheck protocol alias
    INSITU = "insitu"  # cycle without RPT


class QpeedVariant(StrEnum):
    """Sub-type within the QPEED experiment family."""

    FULL = "full"
    SOC_SETTING = "soc_setting"


CATEGORY_TO_MODULE: dict[ScheduleCategory, str] = {
    ScheduleCategory.CAPACHECK: "capacheck",
    ScheduleCategory.FORMATION: "formation",
    ScheduleCategory.CYCLE_LIFE: "cycle_life",
    ScheduleCategory.INSITU_CYCLE: "insitu_cycle",
    ScheduleCategory.RPT: "rpt",
    ScheduleCategory.QPEED: "qpeed",
    ScheduleCategory.HPPC: "hppc",
}

_QPEED_PATTERN = re.compile(r"qpeed", re.IGNORECASE)
_QPEED_SOC_SETTING_PATTERN = re.compile(r"soc[_\s-]*setting", re.IGNORECASE)
# SOC50 / SOC_30 / SOC 80, but not SOC_setting (no digits).
_SOC_PERCENT_PATTERN = re.compile(r"soc\s*[_-]?\s*(\d{1,3})(?!\s*setting)", re.IGNORECASE)

_RULES: tuple[tuple[str, re.Pattern[str], ScheduleCategory], ...] = (
    (
        "capacheck_keyword",
        re.compile(r"capacheck", re.IGNORECASE),
        ScheduleCategory.CAPACHECK,
    ),
    (
        "derating_keyword",
        re.compile(r"derating", re.IGNORECASE),
        ScheduleCategory.CAPACHECK,
    ),
    (
        "capa_01c_keyword",
        re.compile(r"0\.1\s*c\s*capa", re.IGNORECASE),
        ScheduleCategory.CAPACHECK,
    ),
    (
        "qpeed_keyword",
        _QPEED_PATTERN,
        ScheduleCategory.QPEED,
    ),
    (
        "hppc_keyword",
        re.compile(r"hppc", re.IGNORECASE),
        ScheduleCategory.HPPC,
    ),
    (
        "formation_fm",
        re.compile(r"(?:^|[_\s-])fm(?:$|[_\s.-])|formation|c1\s*%", re.IGNORECASE),
        ScheduleCategory.FORMATION,
    ),
    (
        "rpt_keyword",
        re.compile(r"rpt", re.IGNORECASE),
        ScheduleCategory.RPT,
    ),
    (
        "insitu_cycle_keyword",
        re.compile(r"insitu|in[\s-]?situ", re.IGNORECASE),
        ScheduleCategory.INSITU_CYCLE,
    ),
    (
        "cycle_life_keyword",
        re.compile(r"\bcycle\b|0\.5\s*c\s*cycle|\d+\s*℃\s*cycle", re.IGNORECASE),
        ScheduleCategory.CYCLE_LIFE,
    ),
)


@dataclass(frozen=True, slots=True)
class ScheduleFilenameMatch:
    path: Path
    category: ScheduleCategory
    matched_rule: str
    suggested_module: str
    qpeed_variant: QpeedVariant | None = None
    protocol_variant: ProtocolVariant = ProtocolVariant.NONE
    filename_soc_percents: tuple[int, ...] = ()

    @property
    def is_qpeed_soc_setting(self) -> bool:
        return (
            self.category == ScheduleCategory.QPEED
            and self.qpeed_variant == QpeedVariant.SOC_SETTING
        )


def _qpeed_variant_from_name(name: str) -> QpeedVariant:
    if _QPEED_SOC_SETTING_PATTERN.search(name):
        return QpeedVariant.SOC_SETTING
    return QpeedVariant.FULL


def _protocol_variant_from_name(name: str, category: ScheduleCategory) -> ProtocolVariant:
    if category == ScheduleCategory.CAPACHECK and re.search(r"derating", name, re.IGNORECASE):
        return ProtocolVariant.DERATING
    if category == ScheduleCategory.INSITU_CYCLE:
        return ProtocolVariant.INSITU
    if category == ScheduleCategory.CYCLE_LIFE and re.search(
        r"insitu|in[\s-]?situ", name, re.IGNORECASE
    ):
        return ProtocolVariant.INSITU
    return ProtocolVariant.NONE


def extract_filename_soc_percents(name: str) -> tuple[int, ...]:
    """Return SOC percentages encoded in a filename, if any.

    ``SOC_setting`` is a QPEED sub-protocol name, not a percentage, and is ignored.
    """
    percents: list[int] = []
    for match in _SOC_PERCENT_PATTERN.finditer(name):
        value = int(match.group(1))
        if 0 <= value <= 100:
            percents.append(value)
    return tuple(percents)


def classify_schedule_filename(path: str | Path) -> ScheduleFilenameMatch:
    """Infer schedule experiment type from a `.sch` filename."""
    resolved = Path(path)
    name = resolved.name
    soc_percents = extract_filename_soc_percents(name)

    for rule_name, pattern, category in _RULES:
        if not pattern.search(name):
            continue
        qpeed_variant = (
            _qpeed_variant_from_name(name) if category == ScheduleCategory.QPEED else None
        )
        return ScheduleFilenameMatch(
            path=resolved,
            category=category,
            matched_rule=rule_name,
            suggested_module=CATEGORY_TO_MODULE.get(category, "unknown"),
            qpeed_variant=qpeed_variant,
            protocol_variant=_protocol_variant_from_name(name, category),
            filename_soc_percents=soc_percents,
        )

    return ScheduleFilenameMatch(
        path=resolved,
        category=ScheduleCategory.UNKNOWN,
        matched_rule="none",
        suggested_module="unknown",
        filename_soc_percents=soc_percents,
    )


def classify_schedule_paths(paths: list[str | Path]) -> list[ScheduleFilenameMatch]:
    return [classify_schedule_filename(path) for path in paths]
