"""Experiment module protocol and registry."""

from __future__ import annotations

from typing import Protocol

from ..ir.cell_profile import CellProfile
from ..ir.project import ModuleNode
from ..ir.step_intent import StepIntent


class ExperimentModule(Protocol):
    module_type: str

    def validate(self, cell: CellProfile) -> list[str]: ...

    def expand(self, cell: CellProfile) -> list[StepIntent]: ...


_MODULE_REGISTRY: dict[str, type] = {}


def register_module(module_type: str):
    def decorator(cls):
        _MODULE_REGISTRY[module_type] = cls
        cls.module_type = module_type
        return cls

    return decorator


def expand_module(node: ModuleNode, cell: CellProfile) -> list[StepIntent]:
    cls = _MODULE_REGISTRY.get(node.module_type)
    if cls is None:
        raise ValueError(f"Unknown module type: {node.module_type}")
    instance = cls.from_params(node.params)
    errors = instance.validate(cell)
    if errors:
        raise ValueError(f"Module {node.id} invalid: {'; '.join(errors)}")
    return instance.expand(cell)


def list_module_types() -> tuple[str, ...]:
    return tuple(sorted(_MODULE_REGISTRY.keys()))


def get_module_class(module_type: str) -> type | None:
    return _MODULE_REGISTRY.get(module_type)


from . import capacheck, cycle_life, dcir, formation, hppc, insitu_cycle, qpeed, rest, rpt  # noqa: E402,F401

__all__ = [
    "ExperimentModule",
    "expand_module",
    "get_module_class",
    "list_module_types",
    "register_module",
]
