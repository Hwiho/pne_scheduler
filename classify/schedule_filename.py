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
    RATE_TEST = "rate_test"
    SOC_SETTING = "soc_setting"
    DCIR = "dcir"
    GITT = "gitt"
    OCV = "ocv"
    EIS = "eis"
    STORAGE = "storage"
    SAFETY = "safety"
    QC = "qc"
    CHARGE = "charge"
    DISCHARGE = "discharge"
    REST = "rest"
    DOE = "doe"
    PLATING = "plating"
    UNKNOWN = "unknown"


class ProtocolVariant(StrEnum):
    """Filename-level sub-type within an experiment family."""

    NONE = "none"
    DERATING = "derating"  # capacheck protocol alias
    INSITU = "insitu"  # cycle without RPT
    DRY = "dry"
    WET = "wet"


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
    ScheduleCategory.RATE_TEST: "rate_test",
    ScheduleCategory.SOC_SETTING: "soc_setting",
    ScheduleCategory.DCIR: "dcir",
    ScheduleCategory.GITT: "dcir",
    ScheduleCategory.OCV: "ocv",
    ScheduleCategory.EIS: "eis",
    ScheduleCategory.STORAGE: "storage",
    ScheduleCategory.SAFETY: "safety",
    ScheduleCategory.QC: "qpeed",
    ScheduleCategory.CHARGE: "charge",
    ScheduleCategory.DISCHARGE: "discharge",
    ScheduleCategory.REST: "rest",
    ScheduleCategory.DOE: "doe",
    ScheduleCategory.PLATING: "charge",
}

_QPEED_PATTERN = re.compile(r"qpeed", re.IGNORECASE)
_QPEED_SOC_SETTING_PATTERN = re.compile(r"soc[_\s-]*setting", re.IGNORECASE)
_HPPC_PATTERN = re.compile(r"hppc|pulse\s+test|pulse\s+heat", re.IGNORECASE)
_RATE_TEST_PATTERN = re.compile(
    r"rate[_\s-]?test|ratetest|mAh\s*rate|rate\+cycle|\brate\.sch|"
    r"(?:^|[\s_\[\]#])(?:\d+(?:\.\d+)?c\s*)?rate(?:[_\s.+]|$)|"
    r"ch_rate|soc_rate|_rate(?:_|\.|$)|"
    r"[\s_-](?:0?\.\d+|[0-9]{1,2})'?\s*C(?:\.sch|[-_]|$)",
    re.IGNORECASE,
)
_STANDALONE_SOC_SETTING_PATTERN = re.compile(
    r"soc[_\s-]*\d+[_\s-]*setting|soc\s*\d+\s*setting",
    re.IGNORECASE,
)
_CAPA_GENERIC_PATTERN = re.compile(
    r"capa_rate|capa[\s_-]soc|\bcapa\b|capcheck|capa[_\s-]*check|initial[_\s-]*check|init[_\s-]*check",
    re.IGNORECASE,
)
_GITT_PATTERN = re.compile(r"gitt|pitt", re.IGNORECASE)
_DCIR_PATTERN = re.compile(r"dcir|dcr", re.IGNORECASE)
_OCV_PATTERN = re.compile(r"(?<![a-z])ocv(?![a-z])", re.IGNORECASE)
_EIS_PATTERN = re.compile(r"(?<![a-z])eis(?![a-z])", re.IGNORECASE)
_STORAGE_PATTERN = re.compile(r"storage|soak|\baging\b|ageing", re.IGNORECASE)
_SAFETY_PATTERN = re.compile(r"safety", re.IGNORECASE)
_QC_PATTERN = re.compile(r"\bqc\b|qcharge|fast[\s_-]?charge", re.IGNORECASE)
_DISCHARGE_PATTERN = re.compile(r"discharge|_dchg\b|\bdchg\b|\bDCH\b", re.IGNORECASE)
_CHARGE_PATTERN = re.compile(
    r"charge|_chg\b|\bchg\b|_Ch\b|\bCH\s+for|\bCH\b(?=\s)",
    re.IGNORECASE,
)
_REST_PATTERN = re.compile(r"(?<![a-z])rest(?![a-z])|preheat|preheating", re.IGNORECASE)
_DOE_PATTERN = re.compile(
    r"불균일|donut|asympad|tape\s*x|nobottom|\btilt\b|cross\d+%",
    re.IGNORECASE,
)
_DRY_WET_PATTERN = re.compile(r"\bdry\b|\bwet\b", re.IGNORECASE)
_CYCLE_PATTERN = re.compile(
    r"cycle|2cycle|\d+cycle|\d+cyc\b|\bcyc\b|0\.5\s*c\s*cycle|\d+\s*℃\s*cycle|"
    r"swell|breathing|\bcont(?:\.sch|$|\s)|LT\d+C",
    re.IGNORECASE,
)
_CURRENT_DENSITY_PATTERN = re.compile(r"mA\s*/\s*cm|mAcm2|ma/cm", re.IGNORECASE)
# FM / formation / form (not capacheck). Compound names like Form_RPT stay RPT/rate/cycle.
_FORMATION_PATTERN = re.compile(
    r"(?:"
    r"(?:^|[_\s\[\(])fm(?:$|[_\s.\)\]-])"
    r"|(?:^|[_\s-])formation(?:$|[_\s.+\-()])"
    r"|포메이션"
    r"|c1\s*%"
    r"|\bcip\b"
    r"|(?:^|[_\s-])form(?!_rpt|_rate|_cycle|\+)(?:\.sch|\.{2}sch|_|$|\s)"
    r")",
    re.IGNORECASE,
)

# First matching rule wins; keep specific families before broad keywords.
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
        "storage_keyword",
        _STORAGE_PATTERN,
        ScheduleCategory.STORAGE,
    ),
    (
        "capa_generic_keyword",
        _CAPA_GENERIC_PATTERN,
        ScheduleCategory.CAPACHECK,
    ),
    (
        "qpeed_keyword",
        _QPEED_PATTERN,
        ScheduleCategory.QPEED,
    ),
    (
        "hppc_keyword",
        _HPPC_PATTERN,
        ScheduleCategory.HPPC,
    ),
    (
        "soc_setting_keyword",
        _STANDALONE_SOC_SETTING_PATTERN,
        ScheduleCategory.SOC_SETTING,
    ),
    (
        "xrd_setup_keyword",
        re.compile(r"(?:^|[_\s-])xrd(?:[_\s-]|\.sch|$)", re.IGNORECASE),
        ScheduleCategory.SOC_SETTING,
    ),
    (
        "cyc_abbrev_keyword",
        re.compile(r"\d+cyc\b", re.IGNORECASE),
        ScheduleCategory.CYCLE_LIFE,
    ),
    (
        "rate_test_keyword",
        _RATE_TEST_PATTERN,
        ScheduleCategory.RATE_TEST,
    ),
    (
        "standalone_c_rate_keyword",
        re.compile(
            r"^[\d.]+'?\s*C(?:\.sch|\s|_|$)(?!.*(?:discharge|dchg|\bDCH\b))",
            re.IGNORECASE,
        ),
        ScheduleCategory.RATE_TEST,
    ),
    (
        "gitt_keyword",
        _GITT_PATTERN,
        ScheduleCategory.GITT,
    ),
    (
        "eis_keyword",
        _EIS_PATTERN,
        ScheduleCategory.EIS,
    ),
    (
        "ocv_keyword",
        _OCV_PATTERN,
        ScheduleCategory.OCV,
    ),
    (
        "qc_keyword",
        _QC_PATTERN,
        ScheduleCategory.QC,
    ),
    (
        "formation_keyword",
        _FORMATION_PATTERN,
        ScheduleCategory.FORMATION,
    ),
    (
        "rpt_keyword",
        re.compile(r"rpt", re.IGNORECASE),
        ScheduleCategory.RPT,
    ),
    (
        "dcir_keyword",
        _DCIR_PATTERN,
        ScheduleCategory.DCIR,
    ),
    (
        "xrm_discharge_keyword",
        re.compile(r"\bxrm\b", re.IGNORECASE),
        ScheduleCategory.DISCHARGE,
    ),
    (
        "discharge_keyword",
        _DISCHARGE_PATTERN,
        ScheduleCategory.DISCHARGE,
    ),
    (
        "plating_keyword",
        re.compile(r"plating|electrodep", re.IGNORECASE),
        ScheduleCategory.PLATING,
    ),
    (
        "current_density_keyword",
        _CURRENT_DENSITY_PATTERN,
        ScheduleCategory.CHARGE,
    ),
    (
        "charge_keyword",
        _CHARGE_PATTERN,
        ScheduleCategory.CHARGE,
    ),
    (
        "rest_keyword",
        _REST_PATTERN,
        ScheduleCategory.REST,
    ),
    (
        "safety_keyword",
        _SAFETY_PATTERN,
        ScheduleCategory.SAFETY,
    ),
    (
        "doe_keyword",
        _DOE_PATTERN,
        ScheduleCategory.DOE,
    ),
    (
        "insitu_cycle_keyword",
        re.compile(r"insitu|in[\s-]?situ", re.IGNORECASE),
        ScheduleCategory.INSITU_CYCLE,
    ),
    (
        "dry_wet_cycle_keyword",
        _DRY_WET_PATTERN,
        ScheduleCategory.CYCLE_LIFE,
    ),
    (
        "cycle_life_keyword",
        _CYCLE_PATTERN,
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
        return self.category == ScheduleCategory.SOC_SETTING or (
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
    if category in (ScheduleCategory.INSITU_CYCLE, ScheduleCategory.CYCLE_LIFE) and re.search(
        r"insitu|in[\s-]?situ", name, re.IGNORECASE
    ):
        return ProtocolVariant.INSITU
    if category == ScheduleCategory.CYCLE_LIFE:
        if re.search(r"\bdry\b", name, re.IGNORECASE):
            return ProtocolVariant.DRY
        if re.search(r"\bwet\b", name, re.IGNORECASE):
            return ProtocolVariant.WET
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
