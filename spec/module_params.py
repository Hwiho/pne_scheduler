"""Per-module ``ParameterSpec`` tables — the single source of form metadata.

Every field a user can edit is declared here once, with its Korean name, unit,
allowed and recommended range, why the default is what it is, which steps it
moves, and how far it has been verified.  ``tests/test_parameter_specs.py``
asserts this table covers every dataclass field of every user-visible module,
so a new module parameter cannot silently reach the UI as a bare JSON key.
"""

from __future__ import annotations

from typing import Any

from ..modules.base import get_module_class
from ..modules.catalog import MODULE_CATALOG, visible_module_types
from .parameter import Choice, ParameterSpec

# ------------------------------------------------------------------ helpers

G_METHOD = "실험 방식"
G_CHARGE = "충전 조건"
G_DISCHARGE = "방전 조건"
G_REST = "휴지 · 대기"
G_REPEAT = "반복"
G_REFERENCE = "측정 기준"
G_LIMIT = "안전 한계"
G_LEGACY = "레거시 (구버전 파일 호환)"


def _rest(
    key: str,
    label: str,
    default: float,
    *,
    group: str = G_REST,
    help: str = "",
    basis: str = "",
    affects: str = "",
    advanced: bool = False,
    maximum: float = 604800.0,
    recommended_max: float | None = 7200.0,
) -> ParameterSpec:
    return ParameterSpec(
        key=key,
        label=label,
        kind="duration_s",
        group=group,
        label_en=key,
        default=default,
        minimum=0.0,
        maximum=maximum,
        recommended_max=recommended_max,
        help=help or "전압이 안정될 때까지 기다리는 개방회로 휴지 시간입니다.",
        basis=basis,
        affects=affects,
        verification="software-checked",
        advanced=advanced,
    )


def _c_rate(
    key: str,
    label: str,
    default: float,
    *,
    group: str,
    help: str = "",
    basis: str = "",
    affects: str = "",
    recommended_min: float | None = 0.05,
    recommended_max: float | None = 2.5,
    maximum: float = 30.0,
    risk: str = "normal",
    advanced: bool = False,
    visible_when: tuple[tuple[str, tuple[str, ...]], ...] = (),
) -> ParameterSpec:
    return ParameterSpec(
        key=key,
        label=label,
        kind="c_rate",
        group=group,
        label_en=key,
        default=default,
        minimum=0.0,
        maximum=maximum,
        recommended_min=recommended_min,
        recommended_max=recommended_max,
        help=help,
        basis=basis or "실제 전류 = C-rate × 셀 공칭 용량.",
        affects=affects,
        risk=risk,  # type: ignore[arg-type]
        verification="software-checked",
        advanced=advanced,
        visible_when=visible_when,
    )


def _count(
    key: str,
    label: str,
    default: int,
    *,
    group: str = G_REPEAT,
    maximum: int = 10000,
    recommended_max: int | None = None,
    help: str = "",
    affects: str = "",
) -> ParameterSpec:
    return ParameterSpec(
        key=key,
        label=label,
        kind="count",
        group=group,
        label_en=key,
        default=default,
        minimum=1,
        maximum=maximum,
        recommended_max=recommended_max,
        help=help,
        affects=affects,
        verification="software-checked",
    )


def _full_rest(
    key: str, label: str, default: float, basis: str, affects: str, recommended_max: float
) -> ParameterSpec:
    """A rest that only exists in a module's ``full`` variant."""
    base = _rest(
        key, label, default, basis=basis, affects=affects, recommended_max=recommended_max
    )
    return ParameterSpec(
        **{
            **{f: getattr(base, f) for f in base.__dataclass_fields__},
            "visible_when": (("variant", ("full",)),),
        }
    )


def _variant(*choices: Choice, default: str) -> ParameterSpec:
    return ParameterSpec(
        key="variant",
        label="실험 형태",
        kind="choice",
        group=G_METHOD,
        label_en="variant",
        default=default,
        choices=choices,
        help="같은 실험의 어떤 형태를 만들지 고릅니다. 선택에 따라 아래 입력 항목이 바뀝니다.",
        basis="modules/catalog.py 의 variant 목록",
        affects="전체 스텝 구성이 바뀝니다.",
        risk="caution",
    )


_SOC_LIST = dict(
    kind="fraction_list",
    group=G_REFERENCE,
    minimum=0.0,
    maximum=1.0,
    help="측정할 SOC 지점을 0–1 비율로 입력합니다. 예: 0.8, 0.5, 0.2",
    basis="직전 SOC 에서의 차이만큼 방전하여 SOC 를 맞춥니다.",
    verification="unverified",
)


# ------------------------------------------------------------------- tables

MODULE_PARAMETER_SPECS: dict[str, tuple[ParameterSpec, ...]] = {
    "formation": (
        _c_rate(
            "charge_c_rate", "화성 충전율", 0.1, group=G_CHARGE,
            help="SEI 를 안정적으로 형성하기 위한 저율 충전입니다.",
            basis="랩 기본값 0.1C (protocol/defaults.py FORMATION_C_RATE)",
            affects="각 사이클의 CCCV 충전 스텝",
            recommended_max=0.5,
        ),
        _c_rate(
            "discharge_c_rate", "화성 방전율", 0.1, group=G_DISCHARGE,
            basis="랩 기본값 0.1C", affects="각 사이클의 CC 방전 스텝",
            recommended_max=0.5,
        ),
        _rest("rest_s", "충·방전 사이 휴지", 600.0, affects="사이클마다 2개의 휴지 스텝"),
        _count(
            "cycle_count", "화성 사이클 수", 3, maximum=20, recommended_max=5,
            help="충전–휴지–방전–휴지 한 묶음을 몇 번 반복할지 정합니다.",
            affects="스텝 수 = 사이클 수 × 4",
        ),
    ),
    "rest": (
        _rest(
            "duration_s", "휴지 시간", 600.0,
            help="지정한 시간 동안 전류를 흘리지 않고 대기합니다.",
            affects="이 모듈의 단일 휴지 스텝",
            recommended_max=86400.0,
        ),
    ),
    "cycle_life": (
        _c_rate(
            "charge_c_rate", "충전율", 0.5, group=G_CHARGE,
            basis="수명 평가 기본값 0.5C (CYCLE_DEFAULT_C_RATE)",
            affects="반복 구간의 CCCV 충전 스텝",
        ),
        _c_rate(
            "discharge_c_rate", "방전율", 0.5, group=G_DISCHARGE,
            basis="수명 평가 기본값 0.5C", affects="반복 구간의 CC 방전 스텝",
        ),
        _rest("rest_s", "충·방전 사이 휴지", 300.0, affects="반복 구간의 휴지 2개"),
        _count(
            "loop_count", "반복 사이클 수", 100, maximum=5000, recommended_max=1000,
            help="LOOP 스텝이 몇 번 되돌아갈지 정합니다. 총 실험 시간을 좌우합니다.",
            affects="LOOP 스텝의 반복 횟수와 예상 소요 시간",
        ),
    ),
    "insitu_cycle": (
        _c_rate(
            "charge_c_rate", "충전율", 0.5, group=G_CHARGE,
            basis="In-situ 기본값 0.5C", affects="반복 구간의 CCCV 충전 스텝",
        ),
        _c_rate(
            "discharge_c_rate", "방전율", 0.5, group=G_DISCHARGE,
            basis="In-situ 기본값 0.5C", affects="반복 구간의 CC 방전 스텝",
        ),
        _rest("rest_s", "충·방전 사이 휴지", 300.0, affects="반복 구간의 휴지 2개"),
        _count(
            "loop_count", "반복 사이클 수", 100, maximum=5000, recommended_max=1000,
            affects="LOOP 반복 횟수", help="RPT 삽입 없이 반복만 수행합니다.",
        ),
    ),
    "capacheck": (
        _c_rate(
            "initial_c_rate", "초기 확인 충방전율", 0.1, group=G_CHARGE,
            basis="capacheck 랩 기본값 0.1C", affects="첫 번째 충방전 쌍",
            recommended_max=0.5,
        ),
        _c_rate(
            "measurement_c_rate", "용량 측정 충방전율", 1.0 / 3.0, group=G_REFERENCE,
            basis="용량 기준 측정 표준 C/3", affects="C/3 측정 사이클",
            recommended_max=1.0,
        ),
        _count(
            "measurement_cycles", "측정 사이클 수", 1, maximum=5, recommended_max=2,
            help="C/3 측정을 두 번 하려면 2 로 설정합니다 (더블 C/3).",
            affects="측정 사이클마다 4스텝 추가",
        ),
        _rest("rest_s", "구간 사이 휴지", 1800.0, affects="각 충방전 사이 휴지"),
        _count(
            "loop_count", "전체 반복 횟수", 1, maximum=100, recommended_max=3,
            help="LOOP 이 전체 확인 구간을 몇 번 반복할지 정합니다.",
            affects="LOOP 스텝",
        ),
    ),
    "rpt": (
        _c_rate(
            "reference_c_rate", "기준 방전율", 1.0 / 3.0, group=G_REFERENCE,
            basis="RPT 표준 C/3 방전", affects="SOC 조정 방전 스텝",
            recommended_max=1.0,
        ),
        ParameterSpec(
            "dcir_pulse_c_rates", "DC-IR 펄스 전류", "c_rate_list", G_REFERENCE,
            "dcir_pulse_c_rates",
            default=[1.5], minimum=0.0, maximum=30.0,
            recommended_min=0.05, recommended_max=2.5,
            help="SOC 지점마다 이 전류들로 차례로 펄스를 겁니다. "
                 "여러 개를 넣으면 (예: 1C, 1.5C, 2C) 전류별 저항을 한 번에 얻습니다.",
            basis="랩 표준 1.0–1.5C 펄스. 여러 rate 는 사용자가 지정합니다.",
            affects="각 SOC 지점의 펄스 스텝 수 (rate 개수 × 2 스텝)",
            verification="software-checked",
        ),
        ParameterSpec(
            "dcir_pulse_s", "DC-IR 펄스 길이", "duration_s", G_REFERENCE, "dcir_pulse_s",
            default=10.0, minimum=1.0, maximum=600.0, recommended_max=60.0,
            help="저항 계산에 쓰는 펄스 인가 시간입니다.",
            basis="랩 표준 10초 펄스",
            affects="각 SOC 지점의 펄스 스텝 길이",
            verification="software-checked",
        ),
        _rest("rest_s", "SOC 안정화 휴지", 1800.0, affects="SOC 조정 후 휴지"),
        ParameterSpec(
            "soc_fractions", "측정 SOC 지점", **_SOC_LIST,  # type: ignore[arg-type]
            label_en="soc_fractions", default=[0.8, 0.5, 0.2],
            affects="SOC 지점 수 × 4 스텝",
            risk="caution",
        ),
        ParameterSpec(
            "include_dcir_pulses", "DC-IR 펄스 포함", "bool", G_METHOD, "include_dcir_pulses",
            default=True,
            help="끄면 SOC 조정 방전만 남기고 저항 펄스는 생성하지 않습니다.",
            affects="펄스 스텝 생성 여부",
            verification="software-checked",
        ),
    ),
    "dcir": (
        ParameterSpec(
            "soc_fractions", "측정 SOC 지점", **_SOC_LIST,  # type: ignore[arg-type]
            label_en="soc_fractions", default=[0.8, 0.5, 0.2],
            affects="SOC 지점마다 방전·휴지·펄스 스텝", risk="caution",
        ),
        _c_rate(
            "pulse_c_rate", "펄스 전류", 1.5, group=G_REFERENCE,
            basis="랩 표준 1.0–1.5C 펄스", affects="각 SOC 의 펄스 스텝",
            recommended_max=1.5,
        ),
        ParameterSpec(
            "pulse_s", "펄스 길이", "duration_s", G_REFERENCE, "pulse_s",
            default=10.0, minimum=1.0, maximum=600.0, recommended_max=60.0,
            basis="랩 표준 10초", affects="펄스 스텝 길이",
            verification="software-checked",
        ),
        _rest("rest_s", "SOC 안정화 휴지", 1800.0, affects="SOC 조정 후 휴지"),
        ParameterSpec(
            "dcr_start_s", "저항 계산 시작 시점", "duration_s", G_REFERENCE, "dcr_start_s",
            default=1.0, minimum=0.0, maximum=600.0,
            help="펄스 시작 후 몇 초 지점을 저항 계산 시작점으로 볼지 지정합니다.",
            basis="Excel 사양과 Ensol 오프셋이 불일치하여 IR 에만 보관합니다.",
            affects="SCH 에는 기록되지 않습니다 (해석용).",
            risk="caution", verification="unverified", advanced=True,
        ),
        ParameterSpec(
            "dcr_end_s", "저항 계산 종료 시점", "duration_s", G_REFERENCE, "dcr_end_s",
            default=10.0, minimum=0.0, maximum=600.0,
            basis="Excel 사양과 Ensol 오프셋이 불일치하여 IR 에만 보관합니다.",
            affects="SCH 에는 기록되지 않습니다 (해석용).",
            risk="caution", verification="unverified", advanced=True,
        ),
    ),
    "hppc": (
        _variant(
            Choice("full", "전 구간 (62 스텝)", "잠긴 골든 62스텝 전 구간 HPPC 형태입니다."),
            Choice("legacy_soc_pulse", "SOC 펄스 (구버전)", "SOC 지점마다 충·방전 펄스를 넣는 단순 형태입니다."),
            default="legacy_soc_pulse",
        ),
        _c_rate(
            "full_capacity_c_rate", "용량 측정 충방전율", 0.1, group=G_REFERENCE,
            basis="골든 62스텝의 0.1C 용량 기준 구간", affects="용량 기준 충방전 스텝",
            recommended_max=0.5, visible_when=(("variant", ("full",)),),
        ),
        _c_rate(
            "reference_c_rate", "기준 충방전율", 1.0 / 3.0, group=G_REFERENCE,
            basis="골든 62스텝의 C/3 기준 구간", affects="기준 사이클 스텝",
            recommended_max=1.0, visible_when=(("variant", ("full",)),),
        ),
        _c_rate(
            "full_pulse_c_rate", "펄스 전류", 1.0, group=G_REFERENCE,
            basis="골든 62스텝의 1C 펄스", affects="30초 충·방전 펄스 스텝",
            recommended_max=2.0, visible_when=(("variant", ("full",)),),
        ),
        ParameterSpec(
            "full_time_limit_s", "스텝 시간 제한", "duration_s", G_LIMIT, "full_time_limit_s",
            default=57600.0, minimum=60.0, maximum=604800.0,
            visible_when=(("variant", ("full",)),),
            help="각 충방전 스텝이 종료 조건에 도달하지 못했을 때 강제로 끝나는 시간입니다.",
            basis="골든 파일 16시간 제한", affects="충·방전 스텝의 시간 종료 조건",
            risk="caution", verification="software-checked",
        ),
        _full_rest("full_rest_s", "기본 휴지", 1800.0, "골든 파일 30분", "전 구간 형태의 짧은 휴지", 7200.0),
        _full_rest("full_long_rest_s", "긴 휴지", 3600.0, "골든 파일 60분", "펄스 전후의 긴 휴지", 14400.0),
        ParameterSpec(
            "soc_fractions", "측정 SOC 지점", **_SOC_LIST,  # type: ignore[arg-type]
            label_en="soc_fractions", default=[0.9, 0.5, 0.1],
            visible_when=(("variant", ("legacy_soc_pulse",)),),
            affects="SOC 지점마다 4스텝", risk="caution",
        ),
        _c_rate(
            "pulse_c_rate", "펄스 전류 (구버전)", 1.0, group=G_LEGACY,
            affects="구버전 형태의 펄스 스텝", recommended_max=2.0,
            visible_when=(("variant", ("legacy_soc_pulse",)),),
        ),
        ParameterSpec(
            "pulse_s", "펄스 길이 (구버전)", "duration_s", G_LEGACY, "pulse_s",
            default=10.0, minimum=1.0, maximum=600.0,
            visible_when=(("variant", ("legacy_soc_pulse",)),),
            verification="software-checked",
        ),
        ParameterSpec(
            "rest_between_s", "펄스 사이 휴지 (구버전)", "duration_s", G_LEGACY, "rest_between_s",
            default=40.0, minimum=0.0, maximum=86400.0,
            visible_when=(("variant", ("legacy_soc_pulse",)),),
            verification="software-checked",
        ),
    ),
    "qpeed": (
        _variant(
            Choice("full", "QPEED-2 전체 (167 스텝)", "1.5C 부터 단계적으로 올리는 고율 충전 평가 전체입니다."),
            Choice("soc_setting", "SOC 설정만 (11 스텝)", "고율 구간 없이 SOC 를 맞추는 준비 스케줄입니다."),
            Choice("legacy_pulse", "구버전 펄스", "예전 .schproj 호환용 HPPC 형태 펄스입니다."),
            default="full",
        ),
        _c_rate(
            "condition_c_rate", "컨디셔닝 충방전율", 1.0, group=G_CHARGE,
            basis="골든 QPEED-2 컨디셔닝 1C", affects="컨디셔닝 충전·방전 스텝 전체",
            recommended_max=1.5,
        ),
        ParameterSpec(
            "soc_voltage_v", "SOC 설정 전압", "voltage_v", G_REFERENCE, "soc_voltage_v",
            default=3.318, minimum=2.0, maximum=5.0,
            help="이 전압까지 충전해 다음 고율 구간의 시작 SOC 를 맞춥니다.",
            basis="골든 QPEED-2 의 3.318 V",
            affects="컨디셔닝 마지막 충전 스텝의 종료 전압",
            risk="caution", verification="software-checked",
        ),
        _rest("initial_rest_s", "시작 휴지", 600.0, affects="첫 번째 휴지 스텝"),
        _rest("rest_s", "구간 사이 휴지", 1800.0, affects="컨디셔닝과 고율 블록의 휴지"),
        ParameterSpec(
            "short_rest_s", "고율 직후 짧은 휴지", "duration_s", G_REST, "short_rest_s",
            default=1.0, minimum=0.0, maximum=3600.0, recommended_max=60.0,
            help="고율 충전 직후 전압 회복을 보기 위한 1초 단위 휴지입니다.",
            basis="골든 파일의 1초 휴지", affects="각 고율 블록의 세 번째 스텝",
            verification="software-checked",
        ),
        ParameterSpec(
            "condition_time_limit_s", "컨디셔닝 시간 제한", "duration_s", G_LIMIT,
            "condition_time_limit_s", default=21600.0, minimum=60.0, maximum=604800.0,
            basis="골든 파일 6시간", affects="컨디셔닝 스텝의 시간 종료 조건",
            risk="caution", verification="software-checked",
        ),
        ParameterSpec(
            "high_rate_start_c", "고율 시작 충전율", "c_rate", G_CHARGE, "high_rate_start_c",
            default=1.5, minimum=0.0, maximum=30.0, recommended_max=6.0,
            visible_when=(("variant", ("full",)),),
            help="고율 평가의 첫 단계 충전율입니다.",
            basis="골든 QPEED-2 는 1.5C 에서 시작합니다.",
            affects="첫 번째 고율 블록의 충전 전류",
            risk="caution", verification="software-checked",
        ),
        ParameterSpec(
            "high_rate_step_c", "고율 증가 간격", "c_rate", G_CHARGE, "high_rate_step_c",
            default=1.5, minimum=0.0, maximum=30.0, recommended_max=6.0,
            visible_when=(("variant", ("full",)),),
            help="블록마다 충전율을 이만큼 올립니다.",
            basis="골든 QPEED-2 는 1.5C 씩 올려 18C 까지 갑니다.",
            affects="각 고율 블록의 충전 전류",
            risk="caution", verification="software-checked",
        ),
        ParameterSpec(
            "high_rate_levels", "고율 단계 수", "count", G_CHARGE, "high_rate_levels",
            default=12, minimum=1, maximum=40, recommended_max=12,
            visible_when=(("variant", ("full",)),),
            help="고율 블록을 몇 단계 만들지 정합니다. 최고 충전율 = 시작 + 간격 × (단계 − 1).",
            basis="골든 QPEED-2 는 12 단계 = 167 스텝입니다.",
            affects="스텝 수 = 10 + 단계 × 13 + 1",
            risk="caution", verification="software-checked",
        ),
        ParameterSpec(
            "high_rate_time_limit_s", "고율 스텝 시간 제한", "duration_s", G_LIMIT,
            "high_rate_time_limit_s", default=57600.0, minimum=60.0, maximum=604800.0,
            visible_when=(("variant", ("full",)),),
            basis="골든 파일 16시간", affects="고율 충전 스텝의 시간 종료 조건",
            risk="caution", verification="software-checked",
        ),
        _c_rate(
            "cv_cutoff_c_rate", "CV 종료 전류", 0.3, group=G_CHARGE,
            help="정전압 구간에서 전류가 이 값까지 떨어지면 충전을 끝냅니다.",
            basis="골든 QPEED-2 의 0.3C 컷오프",
            affects="CCCV 충전 스텝의 종료 조건",
            recommended_max=1.0,
        ),
        ParameterSpec(
            "soc_dod_percent", "SOC 설정 DOD", "percent", G_REFERENCE, "soc_dod_percent",
            default=10.0, minimum=0.0, maximum=100.0,
            visible_when=(("variant", ("soc_setting",)),),
            help="용량 기준 대비 몇 % 를 채우고 멈출지 지정합니다.",
            basis="골든 SOC 설정 후보의 10%",
            affects="SOC 설정 충전 스텝의 DOD 종료 조건",
            risk="critical", verification="unverified",
        ),
        ParameterSpec(
            "high_rate_dod_percent", "고율 종료 DOD", "percent", G_REFERENCE,
            "high_rate_dod_percent", default=1.0, minimum=0.0, maximum=100.0,
            visible_when=(("variant", ("full",)),),
            help="고율 충전을 용량 기준 대비 몇 % 지점에서 끝낼지 지정합니다.",
            basis="골든 QPEED-2 의 1%",
            affects="각 고율 충전 스텝의 DOD 종료 조건",
            risk="critical", verification="unverified",
        ),
        ParameterSpec(
            "soc_fractions", "측정 SOC 지점 (구버전)", **_SOC_LIST,  # type: ignore[arg-type]
            label_en="soc_fractions", default=[0.5],
            visible_when=(("variant", ("legacy_pulse",)),),
            advanced=True,
        ),
        _c_rate(
            "pulse_c_rate", "펄스 전류 (구버전)", 1.0, group=G_LEGACY,
            advanced=True, recommended_max=2.0,
            visible_when=(("variant", ("legacy_pulse",)),),
        ),
        ParameterSpec(
            "pulse_s", "펄스 길이 (구버전)", "duration_s", G_LEGACY, "pulse_s",
            default=10.0, minimum=1.0, maximum=600.0,
            visible_when=(("variant", ("legacy_pulse",)),),
            verification="software-checked", advanced=True,
        ),
        ParameterSpec(
            "rest_between_s", "펄스 사이 휴지 (구버전)", "duration_s", G_LEGACY, "rest_between_s",
            default=40.0, minimum=0.0, maximum=86400.0,
            visible_when=(("variant", ("legacy_pulse",)),),
            verification="software-checked", advanced=True,
        ),
    ),
    "qc": (
        _variant(
            Choice("cycle", "QC 사이클 (17–18 스텝)", "컨디셔닝 후 다단 급속충전을 한 사이클 수행합니다."),
            Choice("1n1q", "1N1Q (17–18 스텝)", "QC 사이클과 같은 형태의 1N1Q 계열입니다."),
            Choice("1_charge", "1 charge (24–26 스텝)", "컨디셔닝 2회와 90% 용량 기준 충전을 포함한 형태입니다."),
            default="cycle",
        ),
        _c_rate(
            "conditioning_c_rate", "컨디셔닝 충방전율", 2.0 / 3.0, group=G_CHARGE,
            basis="Set2 계열 컨디셔닝 2C/3", affects="컨디셔닝 충전·방전 스텝",
            recommended_max=1.5,
        ),
        _c_rate(
            "discharge_c_rate", "방전율", 1.0, group=G_DISCHARGE,
            basis="Set2 계열 1C 방전", affects="방전 스텝",
            recommended_max=2.0,
        ),
        _rest("rest_s", "구간 사이 휴지", 1800.0, affects="충·방전 사이 휴지"),
        _rest(
            "long_rest_s", "긴 휴지", 7200.0, affects="1 charge 형태의 시작·종료 휴지",
            recommended_max=28800.0,
        ),
        ParameterSpec(
            "initial_voltage_v", "1단 목표 전압", "voltage_v", G_CHARGE, "initial_voltage_v",
            default=3.448, minimum=2.0, maximum=5.0,
            help="급속충전 첫 구간에서 도달할 전압입니다.",
            basis="Set2 코퍼스의 3.448 V",
            affects="급속충전 첫 스텝의 전압 한계",
            risk="caution", verification="software-checked",
        ),
        ParameterSpec(
            "fast_rates_c", "급속충전 단계별 전류", "c_rate_list", G_CHARGE, "fast_rates_c",
            default=[4.0, 3.0, 2.0], minimum=0.0, maximum=30.0, recommended_max=6.0,
            help="단계마다 적용할 충전율입니다. 전압·시간 목록과 개수가 같아야 합니다.",
            basis="Set2 3단 구성 (4C, 3C, 2C). 앞에 5C 를 추가하면 Set4 18스텝 형태가 됩니다.",
            affects="급속충전 스텝 수와 전류",
            risk="critical", verification="software-checked",
        ),
        ParameterSpec(
            "fast_voltages_v", "급속충전 단계별 전압", "voltage_list", G_CHARGE, "fast_voltages_v",
            default=[3.918, 4.008, 4.006], minimum=2.0, maximum=5.0,
            help="각 급속충전 단계의 전압 한계입니다.",
            basis="Set2 코퍼스 관측값. 전류를 바꿔도 이 값은 재측정된 것이 아니므로 "
                  "CTSPro 재열기 확인 전에는 검증되지 않은 값입니다.",
            affects="급속충전 스텝의 전압 한계",
            risk="critical", verification="software-checked",
        ),
        ParameterSpec(
            "fast_times_s", "급속충전 단계별 시간", "duration_list", G_CHARGE, "fast_times_s",
            default=[534.0, 524.0, 290.0], minimum=0.0, maximum=86400.0,
            help="각 급속충전 단계의 시간 종료 조건입니다. 전류를 바꾸면 이 값도 함께 "
                 "바꿔야 같은 전하량이 들어갑니다 (C × t 일정).",
            basis="Set2 코퍼스 관측값. 전류를 바꿔 다시 계산한 값은 정전류 구간 근사이며 "
                  "CV 감쇠 구간은 반영되지 않습니다.",
            affects="급속충전 스텝의 시간 종료 조건",
            risk="caution", verification="software-checked",
        ),
        ParameterSpec(
            "one_c_time_s", "1C 마무리 구간 시간", "duration_s", G_CHARGE, "one_c_time_s",
            default=751.0, minimum=0.0, maximum=86400.0,
            basis="Set2 코퍼스 관측값", affects="1C 시간 충전 스텝",
            verification="software-checked",
        ),
        ParameterSpec(
            "one_charge_final_time_s", "1 charge 최종 CV 시간", "duration_s", G_CHARGE,
            "one_charge_final_time_s", default=10800.0, minimum=0.0, maximum=604800.0,
            visible_when=(("variant", ("1_charge",)),),
            basis="1 charge 계열 3시간 CV", affects="1 charge 마지막 CV 스텝",
            verification="software-checked",
        ),
        _c_rate(
            "cv_cutoff_c_rate", "CV 종료 전류", 0.1, group=G_CHARGE,
            help="정전압 구간을 끝내는 전류 기준입니다.",
            basis="Set2 계열 0.1C", affects="CCCV 스텝의 종료 조건",
            recommended_max=1.0,
        ),
        ParameterSpec(
            "time_limit_s", "스텝 시간 제한", "duration_s", G_LIMIT, "time_limit_s",
            default=21600.0, minimum=60.0, maximum=604800.0,
            basis="Set2 계열 6시간 제한", affects="충·방전 스텝의 시간 종료 조건",
            risk="caution", verification="software-checked",
        ),
    ),
    "custom_steps": (
        ParameterSpec(
            "source_module_type", "원본 모듈", "text", G_METHOD, "source_module_type",
            default="",
            help="이 스텝 목록이 어느 모듈에서 분리되었는지 기록합니다.",
            affects="표시용이며 스케줄에는 영향이 없습니다.",
            verification="software-checked", advanced=True,
        ),
    ),
}


# Parameters edited somewhere other than the generated form.  ``custom_steps``
# holds raw step dicts that the procedure step table edits directly.
FORM_EXCLUDED_KEYS: frozenset[tuple[str, str]] = frozenset({("custom_steps", "steps")})


def parameter_specs(module_type: str) -> tuple[ParameterSpec, ...]:
    return MODULE_PARAMETER_SPECS.get(module_type, ())


def spec_for(module_type: str, key: str) -> ParameterSpec | None:
    for spec in parameter_specs(module_type):
        if spec.key == key:
            return spec
    return None


def visible_parameter_specs(
    module_type: str,
    params: dict[str, Any],
    *,
    include_advanced: bool = True,
) -> tuple[ParameterSpec, ...]:
    return tuple(
        spec
        for spec in parameter_specs(module_type)
        if spec.is_visible(params) and (include_advanced or not spec.advanced)
    )


def default_params(module_type: str) -> dict[str, Any]:
    """Dataclass defaults, which the spec table mirrors for display."""
    cls = get_module_class(module_type)
    if cls is None:
        return {}
    instance = cls.from_params({})
    return {
        field_name: getattr(instance, field_name)
        for field_name in cls.__dataclass_fields__
    }


def spec_coverage_gaps() -> tuple[str, ...]:
    """Report parameters with no spec and specs with no parameter.

    Also flags declared defaults that disagree with the module dataclass, so
    the form cannot advertise a default the engine will not actually use.
    """
    gaps: list[str] = []
    for module_type in visible_module_types():
        cls = get_module_class(module_type)
        if cls is None:
            gaps.append(f"{module_type}: registered module class is missing")
            continue
        declared = {spec.key: spec for spec in parameter_specs(module_type)}
        actual = set(cls.__dataclass_fields__)
        for key in sorted(actual - set(declared)):
            if (module_type, key) in FORM_EXCLUDED_KEYS:
                continue
            gaps.append(f"{module_type}.{key}: no ParameterSpec")
        for key in sorted(set(declared) - actual):
            gaps.append(f"{module_type}.{key}: ParameterSpec has no module field")
        defaults = default_params(module_type)
        for key, spec in declared.items():
            if key not in defaults or spec.default is None:
                continue
            expected = defaults[key]
            if isinstance(expected, float) and isinstance(spec.default, (int, float)):
                if abs(float(spec.default) - expected) > 1e-9:
                    gaps.append(f"{module_type}.{key}: spec default {spec.default} != {expected}")
            elif spec.default != expected:
                gaps.append(f"{module_type}.{key}: spec default {spec.default!r} != {expected!r}")
    return tuple(gaps)


def module_verification(module_type: str) -> str:
    spec = MODULE_CATALOG.get(module_type)
    return spec.trust_status if spec else "prototype"


__all__ = [
    "FORM_EXCLUDED_KEYS",
    "MODULE_PARAMETER_SPECS",
    "default_params",
    "module_verification",
    "parameter_specs",
    "spec_coverage_gaps",
    "spec_for",
    "visible_parameter_specs",
]
