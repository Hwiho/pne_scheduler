"""Pure project-graph editing model used by the Tkinter flow editor."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

from ..ir.project import ModuleConnection, ModuleNode, ScheduleProject
from ..ir.step_intent import StepIntent
from ..modules.base import get_module_class, list_module_types
from ..modules.composable import apply_recipe, has_editable_recipe, summarize_instance
from ..modules.presets import presets_for
from ..modules.recipe import ModuleRecipe


@dataclass(frozen=True, slots=True)
class FlowValidation:
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.errors


class FlowProjectModel:
    """Mutate a ScheduleProject while enforcing the current linear-flow contract."""

    def __init__(self, project: ScheduleProject) -> None:
        self.project = project

    @property
    def module_types(self) -> tuple[str, ...]:
        return list_module_types()

    def add_module(
        self,
        module_type: str,
        *,
        module_id: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> ModuleNode:
        cls = get_module_class(module_type)
        if cls is None:
            raise ValueError(f"Unknown module type: {module_type}")
        identifier = module_id or self._next_id(module_type)
        if any(node.id == identifier for node in self.project.modules):
            raise ValueError(f"Duplicate module id: {identifier}")

        instance = cls.from_params(params or {})
        if not is_dataclass(instance):
            raise ValueError(f"Module {module_type} does not expose dataclass parameters")
        node = ModuleNode(identifier, module_type, asdict(instance))
        self.project.modules.append(node)
        return node

    def remove_module(self, module_id: str) -> None:
        if not any(node.id == module_id for node in self.project.modules):
            raise ValueError(f"Unknown module id: {module_id}")
        self.project.modules[:] = [
            node for node in self.project.modules if node.id != module_id
        ]
        self.project.connections[:] = [
            edge
            for edge in self.project.connections
            if edge.source_id != module_id and edge.target_id != module_id
        ]

    def update_params(self, module_id: str, params: dict[str, Any]) -> None:
        node = self.get_module(module_id)
        cls = get_module_class(node.module_type)
        if cls is None:
            raise ValueError(f"Unknown module type: {node.module_type}")
        unknown = sorted(set(params) - set(cls.__dataclass_fields__))
        if unknown:
            raise ValueError(f"Unknown parameter(s): {', '.join(unknown)}")
        instance = cls.from_params(params)
        errors = instance.validate(self.project.cell_profile)
        if errors:
            raise ValueError("; ".join(errors))
        node.params = asdict(instance)

    def connect(self, source_id: str, target_id: str) -> None:
        if source_id == target_id:
            raise ValueError("A module cannot connect to itself")
        self.get_module(source_id)
        self.get_module(target_id)
        edge = ModuleConnection(source_id, target_id)
        if edge in self.project.connections:
            raise ValueError(f"Connection already exists: {source_id} -> {target_id}")
        self.project.connections.append(edge)
        validation = self.validate()
        if validation.errors:
            self.project.connections.pop()
            raise ValueError("; ".join(validation.errors))

    def disconnect(self, source_id: str, target_id: str) -> None:
        original = len(self.project.connections)
        self.project.connections[:] = [
            edge
            for edge in self.project.connections
            if not (edge.source_id == source_id and edge.target_id == target_id)
        ]
        if len(self.project.connections) == original:
            raise ValueError(f"Connection does not exist: {source_id} -> {target_id}")

    def auto_connect(self) -> None:
        self.project.connections[:] = [
            ModuleConnection(source.id, target.id)
            for source, target in zip(
                self.project.modules,
                self.project.modules[1:],
            )
        ]

    def instantiate(self, module_id: str) -> Any:
        node = self.get_module(module_id)
        cls = get_module_class(node.module_type)
        if cls is None:
            raise ValueError(f"Unknown module type: {node.module_type}")
        return cls.from_params(node.params)

    def persist_instance(self, module_id: str, instance: Any) -> None:
        if not is_dataclass(instance):
            raise ValueError(f"Module {module_id} does not expose dataclass parameters")
        errors = instance.validate(self.project.cell_profile)
        if errors:
            raise ValueError("; ".join(errors))
        self.get_module(module_id).params = asdict(instance)

    def apply_preset(self, module_id: str, preset_key: str) -> None:
        instance = self.instantiate(module_id)
        if not hasattr(instance, "apply_preset"):
            raise ValueError(f"Module {module_id} does not support presets")
        instance.apply_preset(preset_key)
        self.persist_instance(module_id, instance)

    def set_recipe(self, module_id: str, recipe: ModuleRecipe) -> None:
        instance = self.instantiate(module_id)
        if not has_editable_recipe(instance):
            raise ValueError(f"Module {module_id} does not have an editable recipe")
        apply_recipe(instance, recipe)
        self.persist_instance(module_id, instance)

    def card_lines(self, module_id: str, *, limit: int = 8) -> list[str]:
        try:
            instance = self.instantiate(module_id)
        except (TypeError, ValueError):
            node = self.get_module(module_id)
            return [node.module_type]
        return summarize_instance(instance, limit=limit)

    def available_presets(self, module_id: str):
        node = self.get_module(module_id)
        return presets_for(node.module_type)

    def get_module(self, module_id: str) -> ModuleNode:
        node = next(
            (node for node in self.project.modules if node.id == module_id),
            None,
        )
        if node is None:
            raise ValueError(f"Unknown module id: {module_id}")
        return node

    def validate(self) -> FlowValidation:
        errors: list[str] = []
        warnings: list[str] = []
        ids = [node.id for node in self.project.modules]
        if len(ids) != len(set(ids)):
            errors.append("Module ids must be unique")
        known_ids = set(ids)

        incoming = {module_id: 0 for module_id in known_ids}
        outgoing = {module_id: 0 for module_id in known_ids}
        adjacency = {module_id: [] for module_id in known_ids}
        seen_edges: set[tuple[str, str]] = set()
        for edge in self.project.connections:
            pair = (edge.source_id, edge.target_id)
            if pair in seen_edges:
                errors.append(
                    f"Duplicate connection: {edge.source_id} -> {edge.target_id}"
                )
                continue
            seen_edges.add(pair)
            if edge.source_id not in known_ids or edge.target_id not in known_ids:
                errors.append(
                    f"Connection references an unknown module: "
                    f"{edge.source_id} -> {edge.target_id}"
                )
                continue
            if edge.source_id == edge.target_id:
                errors.append(f"Self connection: {edge.source_id}")
                continue
            outgoing[edge.source_id] += 1
            incoming[edge.target_id] += 1
            adjacency[edge.source_id].append(edge.target_id)

        for module_id in ids:
            if incoming[module_id] > 1:
                errors.append(f"Module {module_id} has more than one input")
            if outgoing[module_id] > 1:
                errors.append(f"Module {module_id} has more than one output")
        if not errors and self._has_cycle(adjacency, incoming):
            errors.append("Module graph contains a cycle")

        if len(ids) > 1 and len(seen_edges) < len(ids) - 1:
            warnings.append(
                "Flow is disconnected; preview uses stable module-list order "
                "for disconnected components."
            )
        for node in self.project.modules:
            if get_module_class(node.module_type) is None:
                errors.append(
                    f"Module {node.id} has unknown type {node.module_type!r}"
                )
        return FlowValidation(tuple(errors), tuple(warnings))

    def preview_steps(self) -> tuple[list[StepIntent], tuple[str, ...]]:
        validation = self.validate()
        if validation.errors:
            raise ValueError("; ".join(validation.errors))
        steps = self.project.expand_steps()
        warnings = list(validation.warnings)
        end_positions = [
            index for index, step in enumerate(steps) if step.step_type == "end"
        ]
        if end_positions and end_positions[-1] != len(steps) - 1:
            warnings.append("The expanded flow contains a non-final END step.")
        if len(end_positions) > 1:
            warnings.append("The expanded flow contains multiple END steps.")
        return steps, tuple(warnings)

    def _next_id(self, module_type: str) -> str:
        existing = {node.id for node in self.project.modules}
        index = 1
        while f"{module_type}_{index}" in existing:
            index += 1
        return f"{module_type}_{index}"

    @staticmethod
    def _has_cycle(
        adjacency: dict[str, list[str]],
        incoming: dict[str, int],
    ) -> bool:
        counts = dict(incoming)
        queue = [module_id for module_id, count in counts.items() if count == 0]
        visited = 0
        while queue:
            current = queue.pop(0)
            visited += 1
            for target in adjacency[current]:
                counts[target] -= 1
                if counts[target] == 0:
                    queue.append(target)
        return visited != len(counts)
