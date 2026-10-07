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
        "formation", "Formation", "conditioning", "초기 저율 충·방전 컨디셔닝",
        "software-checked", limitations=("Corpus variants are not all parameterized yet.",),
    ),
    "rest": ModuleSpec(
        "rest", "Rest", "primitive", "전류 없이 지정 시간 휴지",
        "software-checked",
    ),
    "cycle_life": ModuleSpec(
        "cycle_life", "Cycle life", "cycling", "CCCV 충전·휴지·방전 반복",
        "software-checked", limitations=("Checkpoint/RPT insertion is not modeled.",),
    ),
    "insitu_cycle": ModuleSpec(
        "insitu_cycle", "In-situ cycle", "cycling", "RPT 없이 이어지는 사이클",
        "software-checked",
    ),
    "capacheck": ModuleSpec(
        "capacheck", "Capacity check", "diagnostic", "기준율에 따른 용량 확인",
        "software-checked", limitations=("Golden step order is family-checked only.",),
    ),
    "rpt": ModuleSpec(
        "rpt", "RPT", "diagnostic", "SOC 구간별 기준 방전·DC-IR",
        "prototype", limitations=("Capacity cutoff and DCR window need controlled pairs.",),
    ),
    "dcir": ModuleSpec(
        "dcir", "DC-IR", "diagnostic", "한 전류의 저항 측정 펄스",
        "prototype", limitations=("DCR window is retained in IR but not written.",),
    ),
    "hppc": ModuleSpec(
        "hppc", "HPPC", "diagnostic", "전 구간 또는 SOC별 펄스 평가",
        "software-checked", variants=(
            "full",
            "legacy_soc_pulse",
            "discharge_soc_pulse",
            "charge_soc_pulse",
        ),
        limitations=(
            "Full topology is reproduced; DOD and CC mode-limit display still require CTSPro review.",
            "Discharge-only and charge-only SOC pulse recipes are unverified and reopen-only.",
        ),
    ),
    "qpeed": ModuleSpec(
        "qpeed", "QPEED", "fast-charge", "단계별 고율 충전 레시피",
        "software-checked", variants=("full", "soc_setting", "legacy_pulse"),
        limitations=("DOD/SOC semantics still need CTSPro controlled-pair verification.",),
    ),
    "qc": ModuleSpec(
        "qc", "QC charge", "fast-charge", "QC 사이클·1N1Q·단일 충전",
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
    "sequence": ModuleSpec(
        "sequence", "반복 블록", "saved", "여러 모듈을 순서대로 묶어 재사용하고 반복합니다.",
        "prototype", advanced_only=True,
        limitations=("블록·중첩 LOOP 출력은 CTSPro 재열기 및 장비 검증 전까지 검토용입니다.",),
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
