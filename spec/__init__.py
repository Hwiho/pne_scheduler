"""Parameter contract: units, ParameterSpec tables, and the form model."""

from .form import (
    FormField,
    FormSection,
    ModuleForm,
    apply_field_edit,
    build_module_form,
    resolve_params,
)
from .module_params import (
    MODULE_PARAMETER_SPECS,
    default_params,
    parameter_specs,
    spec_coverage_gaps,
    spec_for,
    visible_parameter_specs,
)
from .parameter import (
    Choice,
    FieldIssue,
    ParameterSpec,
    ValueView,
    describe_value,
    format_value,
    parse_value,
    validate_value,
)
from .units import UnitParseError

__all__ = [
    "Choice",
    "FieldIssue",
    "FormField",
    "FormSection",
    "MODULE_PARAMETER_SPECS",
    "ModuleForm",
    "ParameterSpec",
    "UnitParseError",
    "ValueView",
    "apply_field_edit",
    "build_module_form",
    "default_params",
    "describe_value",
    "format_value",
    "parameter_specs",
    "parse_value",
    "resolve_params",
    "spec_coverage_gaps",
    "spec_for",
    "validate_value",
    "visible_parameter_specs",
]
