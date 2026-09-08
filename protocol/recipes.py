"""Experiment goals — "what do you want to find out?" instead of module names.

A user picks a purpose in their own words; the catalog maps it to the module
type, variant, and starting parameters.  Everything here is a starting point,
not a lock: the parameters land in the project and stay editable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..modules.catalog import get_module_spec


@dataclass(frozen=True, slots=True)
class ExperimentGoal:
    goal_id: str
    title: str
    question: str
    outcome: str
    module_type: str
    params: dict[str, Any] = field(default_factory=dict)
    keywords: tuple[str, ...] = ()
    note: str = ""

    @property
    def trust_status(self) -> str:
        spec = get_module_spec(self.module_type)
        return spec.trust_status if spec else "prototype"

    @property
    def category(self) -> str:
        spec = get_module_spec(self.module_type)
        return spec.category if spec else "기타"

    def search_text(self) -> str:
        return " ".join(
            [self.title, self.question, self.outcome, self.module_type, *self.keywords]
        ).lower()


EXPERIMENT_GOALS: tuple[ExperimentGoal, ...] = (
    ExperimentGoal(
        "formation",
        "화성 (Formation)",
        "새로 만든 셀을 처음 활성화하고 싶다",
        "SEI 형성과 초기 용량",
        "formation",
        {"cycle_count": 3},
        ("화성", "formation", "fm", "초기", "활성화"),
        "저율(0.1C) 충방전을 반복해 셀을 안정화합니다.",
    ),
    ExperimentGoal(
        "capacity_check",
        "초기 용량 확인 (Capacity check)",
        "이 셀의 실제 용량이 얼마인지 알고 싶다",
        "0.1C 및 C/3 기준 방전 용량",
        "capacheck",
        {},
        ("용량", "capacheck", "capa", "derating", "디레이팅"),
        "0.1C 확인 후 C/3 로 측정합니다. 더블 C/3 가 필요하면 측정 사이클을 2로 올리세요.",
    ),
    ExperimentGoal(
        "cycle_life",
        "수명 평가 (Cycle life)",
        "몇 사이클까지 용량을 유지하는지 보고 싶다",
        "사이클 수 대비 용량 유지율",
        "cycle_life",
        {"loop_count": 100},
        ("수명", "cycle", "사이클", "life", "퇴화"),
        "기본 0.5C 충방전. 반복 횟수가 전체 실험 기간을 결정합니다.",
    ),
    ExperimentGoal(
        "insitu_cycle",
        "In-situ 수명 (측정 삽입 없음)",
        "측정 블록 없이 사이클만 돌리고 싶다",
        "중단 없는 연속 사이클 이력",
        "insitu_cycle",
        {"loop_count": 100},
        ("insitu", "인시츄", "연속", "cycle"),
        "RPT 삽입 없이 반복만 수행합니다.",
    ),
    ExperimentGoal(
        "rpt",
        "주기 성능 점검 (RPT)",
        "수명 중간중간 성능이 얼마나 떨어졌는지 보고 싶다",
        "기준 용량과 SOC 별 DC 저항",
        "rpt",
        {},
        ("rpt", "성능", "점검", "reference", "dcir"),
        "C/3 기준 방전과 SOC 80/50/20 저항 펄스를 함께 수행합니다.",
    ),
    ExperimentGoal(
        "dcir",
        "내부 저항 측정 (DC-IR)",
        "특정 SOC 에서 저항만 재고 싶다",
        "SOC 별 DC 저항",
        "dcir",
        {},
        ("dcir", "저항", "resistance", "ir", "펄스"),
        "저항 계산 구간은 IR 에만 보관되며 SCH 로 기록되지 않습니다.",
    ),
    ExperimentGoal(
        "hppc_full",
        "HPPC 전 구간 (62 스텝)",
        "출력 특성을 전 구간에서 정밀하게 보고 싶다",
        "SOC 전 구간의 충·방전 출력 저항",
        "hppc",
        {"variant": "full"},
        ("hppc", "출력", "power", "펄스", "62"),
        "잠긴 골든 62스텝 형태를 그대로 재현합니다.",
    ),
    ExperimentGoal(
        "hppc_soc",
        "HPPC SOC 펄스 (구버전)",
        "지정한 SOC 몇 곳에서만 펄스를 넣고 싶다",
        "선택한 SOC 의 출력 저항",
        "hppc",
        {"variant": "legacy_soc_pulse"},
        ("hppc", "soc", "펄스", "legacy"),
    ),
    ExperimentGoal(
        "qpeed_full",
        "QPEED 고율 충전 평가 (167 스텝)",
        "얼마나 빠르게 충전할 수 있는지 단계적으로 보고 싶다",
        "충전율 단계별 수용 능력",
        "qpeed",
        {"variant": "full"},
        ("qpeed", "고율", "급속", "fast", "충전"),
        "1.5C 부터 1.5C 씩 올려 12단계를 수행합니다. 셀 용량에 따라 장비 정격을 넘길 수 있습니다.",
    ),
    ExperimentGoal(
        "qpeed_soc",
        "QPEED SOC 설정 (11 스텝)",
        "다음 실험 전에 SOC 만 맞춰 두고 싶다",
        "지정 전압/DOD 로 맞춘 SOC 상태",
        "qpeed",
        {"variant": "soc_setting"},
        ("qpeed", "soc", "설정", "준비"),
        "DOD 종료 조건은 아직 CTSPro 대조 검증 전입니다.",
    ),
    ExperimentGoal(
        "qc_cycle",
        "QC 급속충전 사이클",
        "다단 급속충전 프로파일을 사이클로 돌리고 싶다",
        "다단 급속충전 후 용량 거동",
        "qc",
        {"variant": "cycle"},
        ("qc", "급속", "다단", "fast charge"),
    ),
    ExperimentGoal(
        "qc_1n1q",
        "QC 1N1Q",
        "1N1Q 계열 급속충전을 만들고 싶다",
        "1N1Q 프로파일의 충전 거동",
        "qc",
        {"variant": "1n1q"},
        ("qc", "1n1q", "급속"),
    ),
    ExperimentGoal(
        "qc_1_charge",
        "QC 1 charge",
        "컨디셔닝 후 단일 급속충전만 평가하고 싶다",
        "단일 급속충전 프로파일의 수용 능력",
        "qc",
        {"variant": "1_charge"},
        ("qc", "1charge", "급속", "단일"),
    ),
    ExperimentGoal(
        "rest",
        "휴지 (Rest)",
        "실험 사이에 셀을 쉬게 하고 싶다",
        "개방회로 전압 안정화",
        "rest",
        {"duration_s": 600.0},
        ("휴지", "rest", "대기", "ocv"),
    ),
)

GOALS_BY_ID: dict[str, ExperimentGoal] = {goal.goal_id: goal for goal in EXPERIMENT_GOALS}


def list_goals() -> tuple[ExperimentGoal, ...]:
    return EXPERIMENT_GOALS


def get_goal(goal_id: str) -> ExperimentGoal | None:
    return GOALS_BY_ID.get(goal_id)


def search_goals(query: str) -> tuple[ExperimentGoal, ...]:
    """Match on Korean title, the plain-language question, or module name."""
    needle = query.strip().lower()
    if not needle:
        return EXPERIMENT_GOALS
    terms = [term for term in needle.split() if term]
    return tuple(
        goal
        for goal in EXPERIMENT_GOALS
        if all(term in goal.search_text() for term in terms)
    )


def goals_for_module(module_type: str) -> tuple[ExperimentGoal, ...]:
    return tuple(goal for goal in EXPERIMENT_GOALS if goal.module_type == module_type)


def validate_goal_catalog() -> tuple[str, ...]:
    """Every goal must name a real module and only set real parameters."""
    from ..modules.base import get_module_class

    issues: list[str] = []
    for goal in EXPERIMENT_GOALS:
        cls = get_module_class(goal.module_type)
        if cls is None:
            issues.append(f"{goal.goal_id}: unknown module type {goal.module_type!r}")
            continue
        unknown = sorted(set(goal.params) - set(cls.__dataclass_fields__))
        if unknown:
            issues.append(f"{goal.goal_id}: unknown parameters {', '.join(unknown)}")
        variant = goal.params.get("variant")
        spec = get_module_spec(goal.module_type)
        if variant and spec and spec.variants and variant not in spec.variants:
            issues.append(f"{goal.goal_id}: variant {variant!r} is not in the catalog")
    return tuple(issues)


__all__ = [
    "EXPERIMENT_GOALS",
    "ExperimentGoal",
    "get_goal",
    "goals_for_module",
    "list_goals",
    "search_goals",
    "validate_goal_catalog",
]
