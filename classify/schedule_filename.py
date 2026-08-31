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
}

_QPEED_PATTERN = re.compile(r"qpeed", re.IGNORECASE)
_QPEED_SOC_SETTING_PATTERN = re.compile(r"soc[_\s-]*setting", re.IGNORECASE)

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


def classify_schedule_filename(path: str | Path) -> ScheduleFilenameMatch:
    """Infer schedule experiment type from a `.sch` filename."""
    resolved = Path(path)
    name = resolved.name

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
        )

    return ScheduleFilenameMatch(
        path=resolved,
        category=ScheduleCategory.UNKNOWN,
        matched_rule="none",
        suggested_module="unknown",
    )


def classify_schedule_paths(paths: list[str | Path]) -> list[ScheduleFilenameMatch]:
    return [classify_schedule_filename(path) for path in paths]
