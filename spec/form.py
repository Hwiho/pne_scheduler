"""Structured form model: ParameterSpec + current values → renderable fields.

The Tk workspace renders whatever this returns; it never decides on its own
which fields exist, what unit they use, or whether they are visible for the
selected variant.  Keeping that here means the CLI, tests, and any future UI
show a user exactly the same form.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..ir.cell_profile import CellProfile
from ..modules.base import get_module_class
from ..modules.catalog import get_module_spec
from . import units
from .derived import DerivedValue, module_derived_values
from .module_params import parameter_specs, spec_for, visible_parameter_specs
from .parameter import (
    FieldIssue,
    ParameterSpec,
    ValueView,
    describe_value,
    parse_value,
    validate_value,
)


@dataclass(frozen=True, slots=True)
class FormField:
    spec: ParameterSpec
    value: Any
    view: ValueView
    issues: tuple[FieldIssue, ...] = ()

    @property
    def key(self) -> str:
        return self.spec.key

    @property
    def has_error(self) -> bool:
        return any(issue.is_error for issue in self.issues)

    @property
    def label(self) -> str:
        return self.spec.label

    def detail_lines(self) -> tuple[str, ...]:
        lines: list[str] = []
        if self.spec.help:
            lines.append(self.spec.help)
        if self.view.detail:
            lines.append(f"→ {self.view.detail}")
        if self.spec.range_text():
            lines.append(self.spec.range_text())
        if self.spec.basis:
            lines.append(f"근거: {self.spec.basis}")
        if self.spec.affects:
            lines.append(f"영향: {self.spec.affects}")
        for note in self.view.notes:
            lines.append(note)
        for issue in self.issues:
            lines.append(("오류: " if issue.is_error else "경고: ") + issue.message)
        return tuple(lines)


@dataclass(frozen=True, slots=True)
class FormSection:
    title: str
    fields: tuple[FormField, ...] = ()


@dataclass(frozen=True, slots=True)
class ModuleForm:
    module_type: str
    title: str
    trust_status: str
    sections: tuple[FormSection, ...] = ()
    limitations: tuple[str, ...] = ()
    hidden_keys: tuple[str, ...] = field(default=())
    derived: tuple[DerivedValue, ...] = field(default=())

    @property
    def fields(self) -> tuple[FormField, ...]:
        return tuple(f for section in self.sections for f in section.fields)

    def field_for(self, key: str) -> FormField | None:
        return next((f for f in self.fields if f.key == key), None)

    @property
    def has_errors(self) -> bool:
        return any(f.has_error for f in self.fields)


def build_module_form(
    module_type: str,
    params: dict[str, Any],
    *,
    cell: CellProfile | None = None,
    current_limit_mA: float | None = None,
    include_advanced: bool = True,
) -> ModuleForm:
    """Group the visible parameters of one module into renderable sections."""
    module_spec = get_module_spec(module_type)
    resolved = resolve_params(module_type, params)
    visible = visible_parameter_specs(
        module_type, resolved, include_advanced=include_advanced
    )
    hidden = tuple(
        spec.key for spec in parameter_specs(module_type) if spec not in visible
    )

    sections: list[FormSection] = []
    for spec in visible:
        value = resolved.get(spec.key, spec.default)
        form_field = FormField(
            spec=spec,
            value=value,
            view=describe_value(
                spec, value, cell=cell, current_limit_mA=current_limit_mA
            ),
            issues=validate_value(
                spec, value, cell=cell, current_limit_mA=current_limit_mA
            ),
        )
        for position, section in enumerate(sections):
            if section.title == spec.group:
                sections[position] = FormSection(
                    spec.group, section.fields + (form_field,)
                )
                break
        else:
            sections.append(FormSection(spec.group, (form_field,)))

    derived: tuple[DerivedValue, ...] = ()
    if cell is not None:
        derived = module_derived_values(
            module_type, resolved, cell=cell, current_limit_mA=current_limit_mA
        )

    return ModuleForm(
        module_type=module_type,
        title=module_spec.title if module_spec else module_type,
        trust_status=module_spec.trust_status if module_spec else "prototype",
        sections=tuple(sections),
        limitations=module_spec.limitations if module_spec else (),
        hidden_keys=hidden,
        derived=derived,
    )


def resolve_params(module_type: str, params: dict[str, Any]) -> dict[str, Any]:
    """Fill unset parameters from the module dataclass defaults."""
    cls = get_module_class(module_type)
    if cls is None:
        return dict(params)
    instance = cls.from_params(dict(params))
    return {name: getattr(instance, name) for name in cls.__dataclass_fields__}


def apply_field_edit(
    module_type: str,
    params: dict[str, Any],
    key: str,
    text: Any,
) -> dict[str, Any]:
    """Return updated params with ``key`` parsed from user text.

    Raises ``units.UnitParseError`` when the text cannot be read; the caller
    shows that message next to the field instead of dropping the edit.
    """
    spec = spec_for(module_type, key)
    if spec is None:
        raise units.UnitParseError(f"알 수 없는 입력 항목입니다: {key}")
    updated = resolve_params(module_type, params)
    updated[key] = parse_value(spec, text)
    return updated


def form_issues(form: ModuleForm) -> tuple[FieldIssue, ...]:
    return tuple(issue for f in form.fields for issue in f.issues)


__all__ = [
    "DerivedValue",
    "FormField",
    "FormSection",
    "ModuleForm",
    "apply_field_edit",
    "build_module_form",
    "form_issues",
    "resolve_params",
]
