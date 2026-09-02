"""Human-readable overview of a composed module-flow project.

This summarizes the work in a .schproj after recipes are assembled. It is not
an SCH binary explainer and is not equipment-ready.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ir.project import ScheduleProject
from ..ir.step_intent import StepIntent
from ..modules.base import get_module_class
from ..modules.composable import has_editable_recipe
from ..modules.presets import PRESETS_BY_KEY
from ..modules.recipe import format_c_rate, format_seconds


@dataclass(frozen=True, slots=True)
class ModuleOverview:
    module_id: str
    module_type: str
    preset: str
    title: str
    setup_lines: tuple[str, ...]
    repeat_lines: tuple[str, ...]
    repeat_count: int
    after_lines: tuple[str, ...]
    extra_lines: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProjectOverview:
    name: str
    cell_summary: str
    flow: tuple[str, ...]
    modules: tuple[ModuleOverview, ...]
    step_count: int
    highlights: tuple[str, ...]
    caveats: tuple[str, ...]

    def to_text(self) -> str:
        lines = [
            "What this schedule does",
            "=======================",
            f"Project: {self.name}",
            f"Cell: {self.cell_summary}",
            "",
            "Flow",
        ]
        if self.flow:
            lines.append("  " + " → ".join(self.flow))
        else:
            lines.append("  (no modules yet)")
        for module in self.modules:
            lines.append("")
            header = f"{module.module_id}  [{module.module_type}]"
            if module.preset:
                header += f"  preset {module.preset}"
            lines.append(header)
            if module.title:
                lines.append(f"  {module.title}")
            if module.setup_lines:
                lines.append("  Setup once")
                lines.extend(f"    {item}" for item in module.setup_lines)
            if module.repeat_lines:
                lines.append(f"  Repeat ×{module.repeat_count}")
                lines.extend(f"    {item}" for item in module.repeat_lines)
            if module.after_lines:
                lines.append("  After")
                lines.extend(f"    {item}" for item in module.after_lines)
            lines.extend(f"  {item}" for item in module.extra_lines)
        lines.append("")
        lines.append("Expanded pattern")
        lines.append(f"  {self.step_count} step intents")
        if self.highlights:
            lines.extend(f"  {item}" for item in self.highlights)
        lines.append("")
        lines.append("Caveats")
        lines.extend(f"  - {item}" for item in self.caveats)
        return "\n".join(lines) + "\n"


def compose_overview(project: ScheduleProject) -> ProjectOverview:
    cell = project.cell_profile
    cell_summary = (
        f"{cell.nominal_capacity_mAh:g} mAh, {cell.v_min:g}–{cell.v_max:g} V"
        + (f", max {cell.max_current_mA:g} mA" if cell.max_current_mA else "")
    )
    flow = _flow_ids(project)
    modules = tuple(_module_overview(project, module_id) for module_id in flow)
    steps = project.expand_steps() if project.modules else []
    return ProjectOverview(
        name=project.name,
        cell_summary=cell_summary,
        flow=flow,
        modules=modules,
        step_count=len(steps),
        highlights=_highlights(steps),
        caveats=(
            "This overview is for the composed module recipes, not a CTSPro file.",
            "SCH export is analysis-only and not equipment-ready.",
        ),
    )


def format_overview(overview: ProjectOverview) -> str:
    return overview.to_text()


def _flow_ids(project: ScheduleProject) -> tuple[str, ...]:
    return tuple(node.id for node in project.ordered_modules())


def _module_overview(project: ScheduleProject, module_id: str) -> ModuleOverview:
    node = next(item for item in project.modules if item.id == module_id)
    cls = get_module_class(node.module_type)
    if cls is None:
        return ModuleOverview(
            module_id=node.id,
            module_type=node.module_type,
            preset="",
            title="Unknown module type",
            setup_lines=(),
            repeat_lines=(),
            repeat_count=1,
            after_lines=(),
        )
    instance = cls.from_params(node.params)
    if has_editable_recipe(instance) and hasattr(instance, "recipe"):
        recipe = instance.recipe()
        spec = PRESETS_BY_KEY.get(recipe.preset)
        return ModuleOverview(
            module_id=node.id,
            module_type=node.module_type,
            preset=recipe.preset,
            title=spec.title if spec is not None else (
                "Custom recipe" if recipe.preset == "custom" else recipe.preset
            ),
            setup_lines=tuple(unit.summary() for unit in recipe.setup),
            repeat_lines=tuple(unit.summary() for unit in recipe.repeat),
            repeat_count=recipe.repeat_count,
            after_lines=tuple(unit.summary() for unit in recipe.after),
        )
    extras = _primitive_lines(instance, node.module_type)
    return ModuleOverview(
        module_id=node.id,
        module_type=node.module_type,
        preset="",
        title="",
        setup_lines=(),
        repeat_lines=(),
        repeat_count=1,
        after_lines=(),
        extra_lines=extras,
    )


def _primitive_lines(instance: object, module_type: str) -> tuple[str, ...]:
    if module_type == "charge":
        rate = getattr(instance, "c_rate", None)
        mode = getattr(instance, "mode", "CC")
        voltage = getattr(instance, "end_voltage_v", None)
        suffix = f" → {voltage:g} V" if voltage is not None else ""
        return (f"{format_c_rate(rate)} {mode}{suffix}".strip(),)
    if module_type == "discharge":
        rate = getattr(instance, "c_rate", None)
        voltage = getattr(instance, "end_voltage_v", None)
        if voltage is not None:
            return (f"{format_c_rate(rate)} DCHG → {voltage:g} V",)
        return (f"{format_c_rate(rate)} DCHG",)
    if module_type == "rest":
        return (f"REST {format_seconds(getattr(instance, 'duration_s', None))}",)
    params = [
        f"{key}={value}"
        for key, value in vars(instance).items()
        if key in {"charge_c_rate", "discharge_c_rate", "loop_count", "cycle_count", "rest_s"}
    ]
    return tuple(params) if params else (module_type,)


def _highlights(steps: list[StepIntent]) -> tuple[str, ...]:
    lines: list[str] = []
    loops = [step.loop_count for step in steps if step.step_type == "loop" and step.loop_count]
    if loops:
        lines.append("LOOP ×" + ", ×".join(str(count) for count in loops))
    voltages = sorted(
        {
            round(float(step.end_voltage_v), 3)
            for step in steps
            if step.end_voltage_v is not None
        }
        | {
            round(float(step.voltage_v), 3)
            for step in steps
            if step.voltage_v is not None
        }
    )
    if voltages:
        lines.append("Voltage setpoints: " + ", ".join(f"{value:g} V" for value in voltages))
    rates = sorted(
        {
            round(float(step.c_rate), 6)
            for step in steps
            if step.c_rate is not None
        }
    )
    if rates:
        lines.append("C-rates: " + ", ".join(format_c_rate(rate) for rate in rates))
    kinds = [step.step_type for step in steps]
    lines.append(
        "Step kinds: "
        + ", ".join(f"{kind}×{kinds.count(kind)}" for kind in dict.fromkeys(kinds))
    )
    return tuple(lines)
