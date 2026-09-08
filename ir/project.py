"""Schedule project IR (.schproj)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..schema import DEFAULT_SCH_VERSION
from .cell_profile import CellProfile
from .equipment_profile import EquipmentProfile
from .step_intent import StepIntent

SCHPROJ_SCHEMA_V1 = "pne_scheduler.schproj/v1"
SCHPROJ_SCHEMA_V2 = "pne_scheduler.schproj/v2"
SCHPROJ_SCHEMA = SCHPROJ_SCHEMA_V2
SUPPORTED_SCHPROJ_SCHEMAS = (SCHPROJ_SCHEMA_V1, SCHPROJ_SCHEMA_V2)


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
class ReviewState:
    """Where this schedule sits on the draft → equipment-approved ladder.

    Only a person can move these flags: the software can prove a file is
    self-consistent, never that CTSPro opened it or that the lab signed off.
    """

    ctspro_reviewed: bool = False
    ctspro_reviewer: str = ""
    ctspro_reviewed_at: str = ""
    reviewed_sha256: str = ""
    equipment_approved: bool = False
    equipment_approved_by: str = ""
    equipment_approved_at: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewState:
        known = {key: data[key] for key in cls.__dataclass_fields__ if key in data}
        return cls(**known)


@dataclass
class ScheduleProject:
    name: str
    cell_profile: CellProfile
    sch_version: int = DEFAULT_SCH_VERSION
    modules: list[ModuleNode] = field(default_factory=list)
    connections: list[ModuleConnection] = field(default_factory=list)
    schema: str = SCHPROJ_SCHEMA
    equipment: EquipmentProfile | None = None
    review: ReviewState = field(default_factory=ReviewState)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHPROJ_SCHEMA_V2,
            "name": self.name,
            "sch_version": self.sch_version,
            "cell_profile": self.cell_profile.to_dict(),
            "equipment": self.equipment.to_dict() if self.equipment else None,
            "modules": [m.to_dict() for m in self.modules],
            "connections": [c.to_dict() for c in self.connections],
            "review": self.review.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScheduleProject:
        equipment = data.get("equipment")
        review = data.get("review")
        return cls(
            name=data["name"],
            sch_version=int(data.get("sch_version", DEFAULT_SCH_VERSION)),
            cell_profile=CellProfile.from_dict(data["cell_profile"]),
            modules=[ModuleNode.from_dict(m) for m in data.get("modules", [])],
            connections=[ModuleConnection.from_dict(c) for c in data.get("connections", [])],
            schema=SCHPROJ_SCHEMA_V2,
            equipment=EquipmentProfile.from_dict(equipment) if equipment else None,
            review=ReviewState.from_dict(review) if review else ReviewState(),
        )

    def copy(self) -> ScheduleProject:
        return ScheduleProject.from_dict(self.to_dict())

    def save(self, path: Path) -> None:
        """Write the project. Always allowed — export is what safety gates."""
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> ScheduleProject:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def expand_steps(self) -> list[StepIntent]:
        """Compose the module graph into a safe, terminal schedule."""
        from .composer import compose_module_steps

        ordered = _topological_module_order(self.modules, self.connections)
        return compose_module_steps(ordered, self.cell_profile)


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
