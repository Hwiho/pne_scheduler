"""``ParameterSpec`` — the input contract shared by every form, CLI, and check.

A module parameter is not just a dataclass field with a float in it.  For a
lab user it has a Korean name, a unit, an allowed range, a recommended range,
a reason it has the value it has, a risk level, and a verification status that
says how far the value has been proven (software only, CTSPro reopen, or a
real equipment run).  All of that lives here so the UI never has to hardcode
it and the validator never has to guess.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from ..ir.cell_profile import CellProfile
from . import units

ParamKind = Literal[
    "c_rate",
    "current_mA",
    "voltage_v",
    "duration_s",
    "percent",
    "fraction",
    "count",
    "choice",
    "bool",
    "text",
    "c_rate_list",
    "voltage_list",
    "duration_list",
    "fraction_list",
]

Risk = Literal["normal", "caution", "critical"]
Verification = Literal[
    "software-checked",
    "CTSPro-reopen-verified",
    "equipment-run-verified",
    "unverified",
]

RISK_LABELS_KO: dict[str, str] = {
    "normal": "일반",
    "caution": "주의",
    "critical": "위험",
}

VERIFICATION_LABELS_KO: dict[str, str] = {
    "software-checked": "소프트웨어 검증",
    "CTSPro-reopen-verified": "CTSPro 확인 완료",
    "equipment-run-verified": "장비 실행 검증 완료",
    "unverified": "미검증",
}

_LIST_ELEMENT_KIND: dict[str, ParamKind] = {
    "c_rate_list": "c_rate",
    "voltage_list": "voltage_v",
    "duration_list": "duration_s",
    "fraction_list": "fraction",
}

_UNIT_LABELS: dict[str, str] = {
    "c_rate": "C",
    "current_mA": "mA",
    "voltage_v": "V",
    "duration_s": "시간",
    "percent": "%",
    "fraction": "비율 (0–1)",
    "count": "회",
}


@dataclass(frozen=True, slots=True)
class Choice:
    value: str
    label: str
    help: str = ""


@dataclass(frozen=True, slots=True)
class FieldIssue:
    severity: Literal["error", "warning"]
    message: str
    code: str = ""

    @property
    def is_error(self) -> bool:
        return self.severity == "error"


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    """One editable parameter, described well enough to render a form field."""

    key: str
    label: str
    kind: ParamKind
    group: str = "기본"
    label_en: str = ""
    default: Any = None
    minimum: float | None = None
    maximum: float | None = None
    recommended_min: float | None = None
    recommended_max: float | None = None
    choices: tuple[Choice, ...] = ()
    # ``(field, allowed values)`` — the field is only shown when the sibling
    # parameter currently holds one of those values.
    visible_when: tuple[tuple[str, tuple[str, ...]], ...] = ()
    help: str = ""
    basis: str = ""
    risk: Risk = "normal"
    affects: str = ""
    verification: Verification | None = None
    advanced: bool = False

    @property
    def is_list(self) -> bool:
        return self.kind in _LIST_ELEMENT_KIND

    @property
    def element_kind(self) -> ParamKind:
        return _LIST_ELEMENT_KIND.get(self.kind, self.kind)

    @property
    def unit_label(self) -> str:
        return _UNIT_LABELS.get(self.element_kind, "")

    @property
    def display_name(self) -> str:
        return self.label if not self.label_en else f"{self.label} ({self.label_en})"

    def is_visible(self, params: dict[str, Any]) -> bool:
        for sibling, allowed in self.visible_when:
            if str(params.get(sibling, "")) not in allowed:
                return False
        return True

    def range_text(self) -> str:
        """Korean 'allowed / recommended' hint shown under the input."""
        parts: list[str] = []
        if self.minimum is not None or self.maximum is not None:
            low = _format_scalar(self.element_kind, self.minimum) if self.minimum is not None else "제한 없음"
            high = _format_scalar(self.element_kind, self.maximum) if self.maximum is not None else "제한 없음"
            parts.append(f"허용 {low} ~ {high}")
        if self.recommended_min is not None or self.recommended_max is not None:
            low = _format_scalar(self.element_kind, self.recommended_min) if self.recommended_min is not None else "—"
            high = _format_scalar(self.element_kind, self.recommended_max) if self.recommended_max is not None else "—"
            parts.append(f"권장 {low} ~ {high}")
        if self.choices:
            parts.append(" / ".join(choice.label for choice in self.choices))
        return " · ".join(parts)

    def verification_label(self) -> str:
        if self.verification is None:
            return ""
        return VERIFICATION_LABELS_KO.get(self.verification, self.verification)

    def choice_label(self, value: Any) -> str:
        for choice in self.choices:
            if choice.value == str(value):
                return choice.label
        return str(value)

    def value_from_choice_label(self, label: str) -> str:
        for choice in self.choices:
            if choice.label == label:
                return choice.value
        return label


@dataclass(frozen=True, slots=True)
class ValueView:
    """How one parameter value is displayed: input text plus derived detail."""

    text: str
    detail: str = ""
    notes: tuple[str, ...] = field(default=())


def _format_scalar(kind: ParamKind, value: Any) -> str:
    if value is None:
        return ""
    if kind == "c_rate":
        return units.format_c_rate(float(value))
    if kind == "current_mA":
        return units.format_current_mA(float(value))
    if kind == "voltage_v":
        return units.format_voltage(float(value))
    if kind == "duration_s":
        return units.format_duration_input(float(value))
    if kind == "percent":
        return units.format_percent(float(value))
    if kind == "fraction":
        return f"{float(value):g}"
    if kind == "count":
        return units.format_count(float(value))
    if kind == "bool":
        return "예" if bool(value) else "아니오"
    return str(value)


def format_value(spec: ParameterSpec, value: Any) -> str:
    """Editable text for ``value`` in the shape the parser accepts back."""
    if spec.kind == "choice":
        return spec.choice_label(value)
    if spec.kind == "bool":
        return "예" if bool(value) else "아니오"
    if spec.is_list:
        items = list(value or [])
        return ", ".join(_format_scalar(spec.element_kind, item) for item in items)
    if value is None:
        return ""
    return _format_scalar(spec.kind, value)


def parse_value(spec: ParameterSpec, text: Any) -> Any:
    """Read user text back into the stored parameter type.

    Raises ``units.UnitParseError`` with a Korean message the form shows
    directly next to the field.
    """
    if spec.kind == "choice":
        value = spec.value_from_choice_label(str(text).strip())
        allowed = {choice.value for choice in spec.choices}
        if allowed and value not in allowed:
            raise units.UnitParseError(
                f"{spec.label}: 선택할 수 없는 값입니다 — {text!r}"
            )
        return value
    if spec.kind == "bool":
        return units.parse_bool(text)
    if spec.is_list:
        if isinstance(text, (list, tuple)):
            chunks = [str(item) for item in text]
        else:
            chunks = units.split_list(str(text))
        return [_parse_scalar(spec.element_kind, chunk) for chunk in chunks]
    return _parse_scalar(spec.kind, text)


def _parse_scalar(kind: ParamKind, text: Any) -> Any:
    if isinstance(text, bool):
        return text
    if isinstance(text, (int, float)) and kind != "count":
        return float(text)
    if kind == "c_rate":
        return units.parse_c_rate(text)
    if kind == "duration_s":
        return units.parse_duration_s(text)
    if kind == "voltage_v":
        return units.parse_voltage(text)
    if kind == "percent":
        return units.parse_percent(text)
    if kind == "count":
        return int(round(units.parse_number(text)))
    if kind == "text":
        return str(text)
    return units.parse_number(text)


def validate_value(
    spec: ParameterSpec,
    value: Any,
    *,
    cell: CellProfile | None = None,
    current_limit_mA: float | None = None,
) -> tuple[FieldIssue, ...]:
    """Range, choice, and safety-limit checks for a single parameter value."""
    issues: list[FieldIssue] = []
    if spec.kind == "choice":
        allowed = {choice.value for choice in spec.choices}
        if allowed and str(value) not in allowed:
            issues.append(FieldIssue("error", f"{spec.label}: 허용되지 않는 선택입니다.", "CHOICE"))
        return tuple(issues)
    if spec.kind == "bool":
        return ()

    items = list(value or []) if spec.is_list else [value]
    if spec.is_list and not items:
        issues.append(FieldIssue("error", f"{spec.label}: 최소 한 개의 값이 필요합니다.", "EMPTY_LIST"))
    for item in items:
        if item is None:
            continue
        try:
            numeric = float(item)
        except (TypeError, ValueError):
            issues.append(FieldIssue("error", f"{spec.label}: 숫자가 아닙니다.", "NOT_NUMBER"))
            continue
        if spec.minimum is not None and numeric < spec.minimum:
            issues.append(
                FieldIssue(
                    "error",
                    f"{spec.label}: {_format_scalar(spec.element_kind, numeric)} 은(는) "
                    f"허용 최소 {_format_scalar(spec.element_kind, spec.minimum)} 보다 작습니다.",
                    "BELOW_MIN",
                )
            )
        if spec.maximum is not None and numeric > spec.maximum:
            issues.append(
                FieldIssue(
                    "error",
                    f"{spec.label}: {_format_scalar(spec.element_kind, numeric)} 은(는) "
                    f"허용 최대 {_format_scalar(spec.element_kind, spec.maximum)} 를 넘습니다.",
                    "ABOVE_MAX",
                )
            )
        if spec.recommended_min is not None and numeric < spec.recommended_min:
            issues.append(
                FieldIssue(
                    "warning",
                    f"{spec.label}: 권장 범위보다 낮습니다 "
                    f"(권장 최소 {_format_scalar(spec.element_kind, spec.recommended_min)}).",
                    "BELOW_RECOMMENDED",
                )
            )
        if spec.recommended_max is not None and numeric > spec.recommended_max:
            issues.append(
                FieldIssue(
                    "warning",
                    f"{spec.label}: 권장 범위보다 높습니다 "
                    f"(권장 최대 {_format_scalar(spec.element_kind, spec.recommended_max)}).",
                    "ABOVE_RECOMMENDED",
                )
            )
        if cell is not None and spec.element_kind == "voltage_v":
            if not (cell.v_min <= numeric <= cell.v_max):
                issues.append(
                    FieldIssue(
                        "error",
                        f"{spec.label}: 셀 전압 창 {units.format_voltage(cell.v_min)}–"
                        f"{units.format_voltage(cell.v_max)} 밖입니다.",
                        "VOLTAGE_WINDOW",
                    )
                )
        if cell is not None and spec.element_kind == "c_rate" and numeric > 0:
            current = numeric * cell.nominal_capacity_mAh
            limit = current_limit_mA
            if limit and current > limit + 1e-6:
                issues.append(
                    FieldIssue(
                        "error",
                        f"{spec.label}: {units.format_c_rate(numeric)} 는 "
                        f"{units.format_current_mA(current)} 로 장비 한계 "
                        f"{units.format_current_mA(limit)} 를 넘습니다.",
                        "CURRENT_LIMIT",
                    )
                )
            elif limit and current > limit * 0.9:
                issues.append(
                    FieldIssue(
                        "warning",
                        f"{spec.label}: 장비 한계의 "
                        f"{current / limit * 100:.0f}% 를 사용합니다.",
                        "CURRENT_HEADROOM",
                    )
                )
    return tuple(issues)


def describe_value(
    spec: ParameterSpec,
    value: Any,
    *,
    cell: CellProfile | None = None,
    current_limit_mA: float | None = None,
) -> ValueView:
    """Input text plus the derived reading shown beside it (C-rate ↔ mA …)."""
    text = format_value(spec, value)
    notes: list[str] = []
    detail = ""

    if spec.element_kind == "c_rate" and cell is not None:
        rates = [float(item) for item in (value or [])] if spec.is_list else (
            [float(value)] if value is not None else []
        )
        views = [
            units.CurrentView(rate, rate * cell.nominal_capacity_mAh, current_limit_mA)
            for rate in rates
            if rate > 0
        ]
        if views:
            detail = " / ".join(view.describe() for view in views)
            if any(view.exceeds_limit for view in views):
                notes.append("장비 최대 전류를 초과합니다.")
    elif spec.element_kind == "duration_s" and value is not None:
        seconds = [float(item) for item in value] if spec.is_list else [float(value)]
        detail = " / ".join(units.format_duration_ko(item) for item in seconds)
    elif spec.element_kind == "fraction" and value is not None:
        fractions = [float(item) for item in value] if spec.is_list else [float(value)]
        detail = " / ".join(units.format_fraction_as_soc(item) for item in fractions)
    elif spec.kind == "choice":
        for choice in spec.choices:
            if choice.value == str(value) and choice.help:
                detail = choice.help
                break

    if spec.verification and spec.verification != "equipment-run-verified":
        notes.append(f"검증 상태: {spec.verification_label()}")
    return ValueView(text=text, detail=detail, notes=tuple(notes))


__all__ = [
    "Choice",
    "FieldIssue",
    "ParamKind",
    "ParameterSpec",
    "RISK_LABELS_KO",
    "Risk",
    "VERIFICATION_LABELS_KO",
    "ValueView",
    "Verification",
    "describe_value",
    "format_value",
    "parse_value",
    "validate_value",
]
