"""Project-boundary state checks that do not belong to export preflight.

These issues describe experimental entry-state assumptions.  They deliberately
do not claim that a schedule is equipment-ready and do not add preparation
steps on the user's behalf.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import math
from typing import Literal

from ..ir.project import ModuleNode
from .soc_ladder import CHARGE_TO_FULL, UNCONFIRMED_ENTRY, USER_CONFIRMED_START_SOC


@dataclass(frozen=True, slots=True)
class ModuleBoundaryIssue:
    code: str
    message: str
    module_id: str
    severity: Literal["warning", "error"]


@dataclass(frozen=True, slots=True)
class _FlatModule:
    node: ModuleNode
    report_module_id: str


def _flatten_modules(
    modules: Iterable[ModuleNode],
    *,
    report_module_id: str | None = None,
) -> list[_FlatModule]:
    flattened: list[_FlatModule] = []
    for module in modules:
        owner = report_module_id or module.id
        if module.module_type != "sequence":
            flattened.append(_FlatModule(module, owner))
            continue
        children = module.params.get("children", [])
        if not isinstance(children, list):
            continue
        child_nodes = [
            ModuleNode(child["id"], child["module_type"], child.get("params", {}))
            for child in children
            if isinstance(child, dict)
            and isinstance(child.get("id"), str)
            and isinstance(child.get("module_type"), str)
            and isinstance(child.get("params", {}), dict)
        ]
        # Nested groups are rejected by SequenceModule; do not recurse through
        # invalid input before the composer can report that validation error.
        flattened.extend(_FlatModule(child, owner) for child in child_nodes if child.module_type != "sequence")
        repeat = module.params.get("repeat_count", 1)
        if isinstance(repeat, int) and not isinstance(repeat, bool) and repeat > 1:
            # Two passes suffice to expose the last-child -> first-child state
            # transition without materializing thousands of repeated boxes.
            flattened.extend(_FlatModule(child, owner) for child in child_nodes if child.module_type != "sequence")
    return flattened


def module_boundary_issues(modules: Iterable[ModuleNode]) -> list[ModuleBoundaryIssue]:
    """Return explicit state assumptions at module entry boundaries.

    Contract: the function is pure, preserves module order, and returns objects
    with ``code``, ``message``, ``module_id``, and ``severity``.  It neither
    mutates modules nor inserts a charge/preparation step.
    """
    issues: list[ModuleBoundaryIssue] = []
    prior_known_state: Literal["discharged_to_v_min"] | None = None
    prior_module_type = ""
    for item in _flatten_modules(modules):
        module = item.node
        if module.module_type == "rpt" and not module.params.get("include_dcir_pulses", True):
            # A voltage-terminated continuous discharge does not use SOC inputs.
            # Do not gate it on the hidden start_soc/soc_fractions fields.
            prior_known_state = "discharged_to_v_min"
            prior_module_type = "rpt"
            continue
        is_new_hppc_soc_mode = (
            module.module_type == "hppc"
            and module.params.get("variant") in {"discharge_soc_pulse", "charge_soc_pulse"}
        )
        if module.module_type not in {"rpt", "dcir"} and not is_new_hppc_soc_mode:
            if module.module_type in {"cycle_life", "formation", "insitu_cycle"}:
                prior_known_state = "discharged_to_v_min"
                prior_module_type = module.module_type
            elif module.module_type != "rest":
                prior_known_state = None
                prior_module_type = ""
            continue
        policy = str(module.params.get("preparation_policy", UNCONFIRMED_ENTRY))
        start_soc = module.params.get("start_soc", 1.0)
        if (
            prior_known_state == "discharged_to_v_min"
            and policy != CHARGE_TO_FULL
            and isinstance(start_soc, (int, float))
            and not isinstance(start_soc, bool)
            and math.isfinite(start_soc)
            and float(start_soc) > 0.0
        ):
            issues.append(
                ModuleBoundaryIssue(
                    code="ENTRY_SOC_CHAIN_CONFLICT",
                    message=(
                        f"직전 {prior_module_type} 모듈은 방전을 하한 전압에서 끝내며, "
                        f"이 {module.module_type} 모듈이 선언한 시작 SOC "
                        f"{float(start_soc):.0%}를 만들어 주는 충전 단계가 없습니다. "
                        "시작 SOC 확인만으로 이 연결 충돌은 해소되지 않습니다."
                    ),
                    module_id=item.report_module_id,
                    severity="error",
                )
            )
        if policy == UNCONFIRMED_ENTRY:
            start_text = (
                f"{float(start_soc) * 100:g}%"
                if isinstance(start_soc, (int, float)) and not isinstance(start_soc, bool)
                and math.isfinite(start_soc) else "입력 확인 필요"
            )
            issues.append(
                ModuleBoundaryIssue(
                    code="ENTRY_SOC_UNCONFIRMED",
                    message=(
                        f"시작 SOC {start_text}는 계산 가정입니다. 실제 시작 잔량을 "
                        "직접 확인하거나 완충·휴지 후 시작을 선택하세요. 준비 충전은 "
                        "자동으로 추가되지 않습니다."
                    ),
                    module_id=item.report_module_id,
                    severity="warning",
                )
            )
        elif policy not in {USER_CONFIRMED_START_SOC, CHARGE_TO_FULL}:
            issues.append(
                ModuleBoundaryIssue(
                    code="ENTRY_PREPARATION_POLICY_INVALID",
                    message=(
                        f"지원하지 않는 준비 정책 {policy!r}입니다. 준비 충전은 "
                        "사용자가 charge_to_full을 명시적으로 선택하거나 별도 "
                        "준비 모듈로 구성해야 합니다."
                    ),
                    module_id=item.report_module_id,
                    severity="error",
                )
            )
        if is_new_hppc_soc_mode:
            issues.append(
                ModuleBoundaryIssue(
                    code="HPPC_SOC_PULSE_REOPEN_ONLY",
                    message=(
                        "이 HPPC 단일 극성 SOC 펄스 레시피는 소프트웨어 동작만 "
                        "확인된 신규 후보이며 CTSPro 재열기 및 장비 검증 전까지 "
                        "실행 검증된 표준 HPPC로 간주할 수 없습니다."
                    ),
                    module_id=item.report_module_id,
                    severity="warning",
                )
            )
        # Capacity-cutoff and pulse semantics do not prove an exact outgoing SOC
        # at a project boundary, so do not propagate one to the next module.
        prior_known_state = None
        prior_module_type = ""
    return issues


__all__ = ["ModuleBoundaryIssue", "module_boundary_issues"]
