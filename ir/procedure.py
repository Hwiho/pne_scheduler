"""The procedure: a linear list of phases, which is what the cycler runs.

The graph editor lets a user wire modules in arbitrary shapes, but a PNE
schedule is a straight line — the wiring only ever encodes an order.  This
module presents that order directly (phase 1, 2, 3 …), keeps the connections
consistent with it, and reports where each phase lands in the expanded step
list so a review can point at "step 41" and mean something.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..engine.duration import estimate_steps_duration
from .cell_profile import CellProfile
from .project import ModuleConnection, ModuleNode, ScheduleProject
from .step_intent import StepIntent


@dataclass(frozen=True, slots=True)
class PhaseView:
    """One module, placed on the timeline with its step range and duration."""

    position: int
    module_id: str
    module_type: str
    title: str
    subtitle: str
    step_count: int
    first_step: int
    last_step: int
    duration_seconds: float | None
    duration_exact: bool
    trust_status: str
    advanced: bool = False
    error: str = ""

    @property
    def step_range_text(self) -> str:
        if self.step_count <= 0:
            return "—"
        if self.first_step == self.last_step:
            return f"{self.first_step}"
        return f"{self.first_step}–{self.last_step}"


@dataclass(frozen=True, slots=True)
class ProcedureView:
    phases: tuple[PhaseView, ...]
    steps: tuple[StepIntent, ...]
    total_steps: int
    duration_seconds: float | None
    duration_exact: bool
    errors: tuple[str, ...] = ()

    @property
    def is_expandable(self) -> bool:
        return not self.errors

    def phase_for_step(self, step_number: int) -> PhaseView | None:
        for phase in self.phases:
            if phase.first_step <= step_number <= phase.last_step:
                return phase
        return None


def linear_order(project: ScheduleProject) -> list[ModuleNode]:
    """Modules in run order: the wiring when it is a valid chain, else list order."""
    if not project.connections:
        return list(project.modules)
    try:
        from .project import _topological_module_order

        return _topological_module_order(project.modules, project.connections)
    except ValueError:
        return list(project.modules)


def linearize(project: ScheduleProject) -> None:
    """Rewrite the wiring as one straight chain over the current list order.

    The module list is authoritative here: this is what runs after an add,
    a delete, or a reorder.  Use :func:`adopt_connection_order` instead when
    the *wiring* is the thing that should win, such as on load.
    """
    project.connections[:] = [
        ModuleConnection(source.id, target.id)
        for source, target in zip(project.modules, project.modules[1:])
    ]


def adopt_connection_order(project: ScheduleProject) -> bool:
    """Reorder the module list to match its wiring, then chain it.

    Returns True when the wiring was not already a straight chain in list
    order — the case where a graph-editor project is being normalized.
    """
    before = [node.id for node in project.modules]
    before_edges = [(edge.source_id, edge.target_id) for edge in project.connections]
    project.modules[:] = linear_order(project)
    linearize(project)
    after_edges = [(edge.source_id, edge.target_id) for edge in project.connections]
    return before != [node.id for node in project.modules] or before_edges != after_edges


def move_module(project: ScheduleProject, module_id: str, delta: int) -> bool:
    """Move a phase earlier (-1) or later (+1). Returns False at the ends."""
    adopt_connection_order(project)
    ids = [node.id for node in project.modules]
    if module_id not in ids:
        raise ValueError(f"Unknown module id: {module_id}")
    index = ids.index(module_id)
    target = index + delta
    if not 0 <= target < len(ids):
        return False
    modules = project.modules
    modules[index], modules[target] = modules[target], modules[index]
    linearize(project)
    return True


def reorder_modules(project: ScheduleProject, ordered_ids: list[str]) -> None:
    """Apply an explicit order (drag and drop); every module must appear once."""
    by_id = {node.id: node for node in project.modules}
    if sorted(ordered_ids) != sorted(by_id):
        raise ValueError("Reorder must list every module exactly once")
    project.modules[:] = [by_id[module_id] for module_id in ordered_ids]
    linearize(project)


def detach_module(project: ScheduleProject, module_id: str) -> ModuleNode:
    """Freeze a preset into editable steps, replacing it in place.

    The expanded fragment is stored verbatim, so the schedule this produces is
    byte-for-byte the schedule the preset produced — until the user edits it.
    """
    from ..modules.base import expand_module
    from ..modules.custom_steps import CustomStepsModule

    node = next((n for n in project.modules if n.id == module_id), None)
    if node is None:
        raise ValueError(f"Unknown module id: {module_id}")
    if node.module_type == "custom_steps":
        raise ValueError("이미 개별 스텝으로 분리된 모듈입니다.")

    steps = expand_module(node, project.cell_profile)
    detached = CustomStepsModule.from_steps(steps, source_module_type=node.module_type)
    replacement = ModuleNode(node.id, "custom_steps", detached.as_params())
    index = project.modules.index(node)
    project.modules[index] = replacement
    return replacement


def build_procedure(project: ScheduleProject) -> ProcedureView:
    """Expand every phase, place it on the step timeline, and total the time."""
    from ..modules.catalog import get_module_spec
    from .composer import compose_module_steps

    ordered = linear_order(project)
    cell: CellProfile = project.cell_profile
    phases: list[PhaseView] = []
    all_steps: list[StepIntent] = []
    errors: list[str] = []
    cursor = 1

    for position, node in enumerate(ordered, start=1):
        spec = get_module_spec(node.module_type)
        title = spec.title if spec else node.module_type
        try:
            # Compose the single module so its LOOP refs resolve; an unresolved
            # loop would otherwise make the phase look shorter than it runs.
            fragment = list(compose_module_steps([node], cell, append_end=False))
        except (TypeError, ValueError) as exc:
            errors.append(f"{node.id}: {exc}")
            phases.append(
                PhaseView(
                    position=position,
                    module_id=node.id,
                    module_type=node.module_type,
                    title=title,
                    subtitle="",
                    step_count=0,
                    first_step=0,
                    last_step=0,
                    duration_seconds=None,
                    duration_exact=False,
                    trust_status=spec.trust_status if spec else "prototype",
                    advanced=bool(spec and spec.advanced_only),
                    error=str(exc),
                )
            )
            continue

        if fragment and fragment[-1].step_type == "end":
            fragment = fragment[:-1]
        estimate = estimate_steps_duration(fragment)
        all_steps.extend(fragment)
        phases.append(
            PhaseView(
                position=position,
                module_id=node.id,
                module_type=node.module_type,
                title=title,
                subtitle=_phase_subtitle(node, cell),
                step_count=len(fragment),
                first_step=cursor,
                last_step=cursor + len(fragment) - 1 if fragment else cursor,
                duration_seconds=estimate.estimated_seconds,
                duration_exact=estimate.is_exact,
                trust_status=spec.trust_status if spec else "prototype",
                advanced=bool(spec and spec.advanced_only),
            )
        )
        cursor += len(fragment)

    # Per-module composition renumbers LOOP targets inside each fragment, so
    # the totals must come from one whole-project composition instead of the
    # concatenated fragments (whose loop targets are fragment-local).
    steps: tuple[StepIntent, ...] = ()
    duration_seconds: float | None = None
    duration_exact = False
    if not errors:
        try:
            composed = compose_module_steps(ordered, cell)
        except (TypeError, ValueError) as exc:
            errors.append(str(exc))
        else:
            steps = tuple(composed)
            total = estimate_steps_duration(list(composed))
            duration_seconds = total.estimated_seconds
            duration_exact = total.is_exact
    if not steps:
        steps = tuple(all_steps)

    return ProcedureView(
        phases=tuple(phases),
        steps=steps,
        total_steps=len(steps),
        duration_seconds=duration_seconds,
        duration_exact=duration_exact,
        errors=tuple(errors),
    )


def _phase_subtitle(node: ModuleNode, cell: CellProfile) -> str:
    from ..report.summary import module_headline

    try:
        return module_headline(node, cell)
    except Exception:  # pragma: no cover - display only
        return ""


def procedure_step_rows(view: ProcedureView) -> tuple[dict[str, Any], ...]:
    """Flat, read-only step table rows for the equipment detail view."""
    rows: list[dict[str, Any]] = []
    for number, step in enumerate(view.steps, start=1):
        phase = view.phase_for_step(number)
        rows.append(
            {
                "number": number,
                "phase": phase.title if phase else "",
                "phase_id": phase.module_id if phase else "",
                "step_type": step.step_type,
                "mode": step.mode or "",
                "label": step.label,
                "c_rate": step.c_rate,
                "voltage_v": step.voltage_v,
                "end_voltage_v": step.end_voltage_v,
                "end_time_s": step.end_time_s,
                "dod_percent": step.dod_percent,
                "loop_goto_step": step.loop_goto_step,
                "loop_count": step.loop_count,
            }
        )
    return tuple(rows)


__all__ = [
    "PhaseView",
    "ProcedureView",
    "adopt_connection_order",
    "build_procedure",
    "detach_module",
    "linear_order",
    "linearize",
    "move_module",
    "procedure_step_rows",
    "reorder_modules",
]
