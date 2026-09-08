"""Compose module fragments into one safe, numbered schedule intent list."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Iterable

from .step_intent import StepIntent

if TYPE_CHECKING:
    from .cell_profile import CellProfile
    from .project import ModuleNode


def compose_module_steps(
    modules: Iterable[ModuleNode],
    cell: CellProfile,
    *,
    append_end: bool = True,
) -> list[StepIntent]:
    """Flatten ordered module fragments and resolve local LOOP references.

    Module implementations historically returned a mixture of fragments and
    complete schedules.  This boundary normalizes both forms: a trailing END
    is removed from every fragment, embedded END steps are rejected, and raw
    ``loop_goto_step`` values are interpreted as 1-based *fragment-local*
    positions.  New modules should prefer ``ref_id``/``loop_target_ref``.
    """
    from ..modules import expand_module

    composed: list[StepIntent] = []
    for node in modules:
        fragment = list(expand_module(node, cell))
        end_positions = [
            index for index, step in enumerate(fragment) if step.step_type == "end"
        ]
        if end_positions and end_positions != [len(fragment) - 1]:
            raise ValueError(
                f"Module {node.id} contains multiple or non-final END steps; "
                "modules may emit at most one trailing END"
            )
        if end_positions:
            fragment.pop()

        fragment_start = len(composed) + 1
        refs: dict[str, int] = {}
        for local_index, step in enumerate(fragment, start=1):
            if step.ref_id is None:
                continue
            if step.ref_id in refs:
                raise ValueError(
                    f"Module {node.id} contains duplicate step ref {step.ref_id!r}"
                )
            refs[step.ref_id] = fragment_start + local_index - 1

        for local_index, step in enumerate(fragment, start=1):
            resolved = step
            if step.step_type == "loop":
                target = step.loop_goto_step
                if step.loop_target_ref is not None:
                    if target is not None:
                        raise ValueError(
                            f"Module {node.id} LOOP {local_index} defines both "
                            "loop_goto_step and loop_target_ref"
                        )
                    target = refs.get(step.loop_target_ref)
                    if target is None:
                        raise ValueError(
                            f"Module {node.id} LOOP {local_index} references unknown "
                            f"step ref {step.loop_target_ref!r}"
                        )
                elif target is not None:
                    if target < 1 or target >= local_index:
                        raise ValueError(
                            f"Module {node.id} LOOP {local_index} target {target} "
                            "must reference an earlier step in the same module"
                        )
                    target = fragment_start + target - 1

                if target is None or step.loop_count is None or step.loop_count < 1:
                    raise ValueError(
                        f"Module {node.id} LOOP {local_index} requires a target and "
                        "loop_count >= 1"
                    )
                resolved = replace(
                    step,
                    loop_goto_step=target,
                    loop_target_ref=None,
                )
            composed.append(resolved)

    if append_end:
        composed.append(StepIntent(step_type="end", label="schedule end"))
    return composed


__all__ = ["compose_module_steps"]
