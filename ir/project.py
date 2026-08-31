"""Schedule project IR (.schproj)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..schema import DEFAULT_SCH_VERSION
from .cell_profile import CellProfile
from .step_intent import StepIntent

SCHPROJ_SCHEMA = "pne_scheduler.schproj/v1"


@dataclass
class ModuleConnection:
    source_id: str
    target_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModuleConnection:
        return cls(**data)


@dataclass
class ModuleNode:
    id: str
    module_type: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModuleNode:
        return cls(**data)


@dataclass
class ScheduleProject:
    name: str
    cell_profile: CellProfile
    sch_version: int = DEFAULT_SCH_VERSION
    modules: list[ModuleNode] = field(default_factory=list)
    connections: list[ModuleConnection] = field(default_factory=list)
    schema: str = SCHPROJ_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "name": self.name,
            "sch_version": self.sch_version,
            "cell_profile": self.cell_profile.to_dict(),
            "modules": [m.to_dict() for m in self.modules],
            "connections": [c.to_dict() for c in self.connections],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScheduleProject:
        return cls(
            name=data["name"],
            sch_version=int(data.get("sch_version", DEFAULT_SCH_VERSION)),
            cell_profile=CellProfile.from_dict(data["cell_profile"]),
            modules=[ModuleNode.from_dict(m) for m in data.get("modules", [])],
            connections=[ModuleConnection.from_dict(c) for c in data.get("connections", [])],
            schema=data.get("schema", SCHPROJ_SCHEMA),
        )

    def save(self, path: Path) -> None:
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> ScheduleProject:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def expand_steps(self) -> list[StepIntent]:
        """Expand module graph to flat step intents (linear connections only for now)."""
        from ..modules import expand_module

        ordered = _topological_module_order(self.modules, self.connections)
        steps: list[StepIntent] = []
        for node in ordered:
            steps.extend(expand_module(node, self.cell_profile))
        return steps


def _topological_module_order(
    modules: list[ModuleNode],
    connections: list[ModuleConnection],
) -> list[ModuleNode]:
    if not connections:
        return list(modules)

    by_id = {m.id: m for m in modules}
    if len(by_id) != len(modules):
        raise ValueError("Module ids must be unique")
    incoming = {m.id: 0 for m in modules}
    adjacency: dict[str, list[str]] = {m.id: [] for m in modules}
    seen_edges: set[tuple[str, str]] = set()
    for edge in connections:
        if edge.source_id not in by_id or edge.target_id not in by_id:
            raise ValueError(
                "Module connection references an unknown module: "
                f"{edge.source_id} -> {edge.target_id}"
            )
        pair = (edge.source_id, edge.target_id)
        if pair in seen_edges:
            raise ValueError(
                f"Duplicate module connection: {edge.source_id} -> {edge.target_id}"
            )
        seen_edges.add(pair)
        adjacency[edge.source_id].append(edge.target_id)
        incoming[edge.target_id] += 1

    queue = [mid for mid, count in incoming.items() if count == 0]
    ordered_ids: list[str] = []
    while queue:
        current = queue.pop(0)
        ordered_ids.append(current)
        for nxt in adjacency.get(current, []):
            incoming[nxt] -= 1
            if incoming[nxt] == 0:
                queue.append(nxt)

    if len(ordered_ids) != len(modules):
        raise ValueError("Module graph has a cycle")
    return [by_id[mid] for mid in ordered_ids]
