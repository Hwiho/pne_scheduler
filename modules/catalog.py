"""User-facing module metadata shared by the UI and preflight validator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .primitive import PRIMITIVE_KINDS

TrustStatus = Literal[
    "prototype",
    "software-checked",
    "CTSPro-reopen-verified",
    "equipment-run-verified",
]


@dataclass(frozen=True, slots=True)
class ModuleSpec:
    module_type: str
    title: str
    category: str
    description: str
    trust_status: TrustStatus
    variants: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    internal_only: bool = False
    # Real, selectable modules that are hidden from the "add an experiment"
    # palette because they are only produced by an explicit user action.
    advanced_only: bool = False


MODULE_CATALOG: dict[str, ModuleSpec] = {
    "formation": ModuleSpec(
        "formation", "Formation", "conditioning", "Initial low-rate formation cycles.",
        "software-checked", limitations=("Corpus variants are not all parameterized yet.",),
    ),
    "rest": ModuleSpec(
        "rest", "Rest", "primitive", "Time-bounded open-circuit rest.",
        "software-checked",
    ),
    "cycle_life": ModuleSpec(
        "cycle_life", "Cycle life", "cycling", "Repeated CCCV/rest/discharge cycle.",
        "software-checked", limitations=("Checkpoint/RPT insertion is not modeled.",),
    ),
    "insitu_cycle": ModuleSpec(
        "insitu_cycle", "In-situ cycle", "cycling", "Cycle block without an RPT insert.",
        "software-checked",
    ),
    "capacheck": ModuleSpec(
        "capacheck", "Capacity check", "diagnostic", "0.1C then C/3 capacity check.",
        "software-checked", limitations=("Golden step order is family-checked only.",),
    ),
    "rpt": ModuleSpec(
        "rpt", "RPT", "diagnostic", "SOC ladder and DCIR pulse sequence.",
        "prototype", limitations=("Capacity cutoff and DCR window need controlled pairs.",),
    ),
    "dcir": ModuleSpec(
        "dcir", "DC-IR", "diagnostic", "SOC-adjusted DC resistance pulses.",
        "prototype", limitations=("DCR window is retained in IR but not written.",),
    ),
    "hppc": ModuleSpec(
        "hppc", "HPPC", "diagnostic", "62-step full-range or legacy SOC pulse ladder.",
        "software-checked", variants=("full", "legacy_soc_pulse"),
        limitations=("Full topology is reproduced; DOD and CC mode-limit display still require CTSPro review.",),
    ),
    "qpeed": ModuleSpec(
        "qpeed", "QPEED", "fast-charge", "QPEED-2 and SOC-setting candidates.",
        "software-checked", variants=("full", "soc_setting", "legacy_pulse"),
        limitations=("DOD/SOC semantics still need CTSPro controlled-pair verification.",),
    ),
    "qc": ModuleSpec(
        "qc", "QC charge", "fast-charge", "QC cycle, 1N1Q, and 1-charge candidates.",
        "software-checked", variants=("cycle", "1n1q", "1_charge"),
        limitations=("Set-specific voltage/time values require user reopen review.",),
    ),
    "primitive": ModuleSpec(
        "primitive", "단일 스텝", "primitive",
        "휴지·CC·CCCV·CV·OCV 를 한 스텝씩 놓습니다. 반복 횟수를 주면 그 스텝만 반복합니다.",
        "software-checked",
        variants=tuple(PRIMITIVE_KINDS),
        limitations=(
            "END 는 composer 가 소유하므로 팔레트에 없습니다.",
            "LOOP 은 자기 스텝을 반복하는 형태로만 제공됩니다 (모듈 밖을 가리킬 수 없습니다).",
        ),
    ),
    "custom_steps": ModuleSpec(
        "custom_steps", "직접 편집한 스텝", "advanced",
        "프리셋에서 분리해 개별 스텝을 직접 들고 있는 모듈.",
        "prototype", advanced_only=True,
        limitations=(
            "사용자가 직접 편집한 스텝이므로 골든 토폴로지 보장이 없습니다.",
            "장비 내보내기 전에 CTSPro 재검토가 반드시 필요합니다.",
        ),
    ),
    "smoke_rest_cc_end": ModuleSpec(
        "smoke_rest_cc_end", "Smoke test", "internal", "Gate C writer smoke fixture.",
        "software-checked", internal_only=True,
    ),
    "smoke_writer_probe": ModuleSpec(
        "smoke_writer_probe", "Writer probe", "internal", "Offset probe for lab validation.",
        "software-checked", internal_only=True,
    ),
}


def get_module_spec(module_type: str) -> ModuleSpec | None:
    return MODULE_CATALOG.get(module_type)


def palette_module_types() -> tuple[str, ...]:
    """Types offered when adding an experiment (no internal or detached-only)."""
    return tuple(
        module_type
        for module_type, spec in MODULE_CATALOG.items()
        if not spec.internal_only and not spec.advanced_only
    )


def visible_module_types() -> tuple[str, ...]:
    return tuple(
        module_type
        for module_type, spec in MODULE_CATALOG.items()
        if not spec.internal_only
    )


def validate_module_catalog(registered: tuple[str, ...]) -> tuple[str, ...]:
    registered_set = set(registered)
    catalog_set = set(MODULE_CATALOG)
    issues = [f"missing catalog entry: {name}" for name in sorted(registered_set - catalog_set)]
    issues.extend(
        f"catalog entry has no registered module: {name}"
        for name in sorted(catalog_set - registered_set)
    )
    return tuple(issues)
