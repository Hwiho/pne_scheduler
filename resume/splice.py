"""Build a resumed .sch by splicing from checkpoint step."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

from ..io.sch_binary import (
    SchBinaryDocument,
    SchBinaryStep,
    patch_loop_count,
    read_loop_info,
    read_sch_binary,
    renumber_steps,
    write_sch_binary,
)
from ..schema.enums import SCH_STEP_TYPE_END, SCH_STEP_TYPE_LOOP
from .checkpoint import ExperimentCheckpoint, detect_checkpoint


@dataclass
class ResumePlan:
    source_sch: Path
    checkpoint: ExperimentCheckpoint
    resume_sch_step: int
    original_step_count: int
    resumed_step_count: int
    remaining_loop_count: int | None
    warnings: list[str] = field(default_factory=list)

    @property
    def splice_summary(self) -> str:
        return (
            f"steps {self.resume_sch_step}–{self.original_step_count} "
            f"→ {self.resumed_step_count} steps"
        )


@dataclass
class ResumeResult:
    plan: ResumePlan
    output_path: Path
    document: SchBinaryDocument


def build_resume_plan(
    sch_path: str | Path,
    data_path: str | Path,
    *,
    resume_sch_step: int | None = None,
    remaining_loop_count: int | None = None,
) -> ResumePlan:
    sch = Path(sch_path)
    checkpoint = detect_checkpoint(data_path, source_sch=sch)
    doc = read_sch_binary(sch)

    if checkpoint.is_finished and resume_sch_step is None:
        raise ValueError("Experiment appears finished (END step reached).")

    start_step = resume_sch_step or checkpoint.resume_sch_step
    if start_step < 1 or start_step > doc.step_count:
        raise ValueError(f"resume step {start_step} out of range (1..{doc.step_count})")

    warnings = list(checkpoint.warnings)
    remaining = remaining_loop_count
    if remaining is None and checkpoint.completed_loop_iterations is not None:
        loop_step, original_loops = _find_loop_step(doc.steps)
        if loop_step is not None and original_loops is not None:
            remaining = max(0, original_loops - checkpoint.completed_loop_iterations)
            if remaining != original_loops:
                warnings.append(
                    f"auto loop adjust: {original_loops} → {remaining} remaining "
                    f"({checkpoint.completed_loop_iterations} completed)"
                )

    return ResumePlan(
        source_sch=sch,
        checkpoint=checkpoint,
        resume_sch_step=start_step,
        original_step_count=doc.step_count,
        resumed_step_count=0,
        remaining_loop_count=remaining,
        warnings=warnings,
    )


def splice_resume_schedule(
    sch_path: str | Path,
    data_path: str | Path,
    output_path: str | Path,
    *,
    resume_sch_step: int | None = None,
    remaining_loop_count: int | None = None,
) -> ResumeResult:
    plan = build_resume_plan(
        sch_path,
        data_path,
        resume_sch_step=resume_sch_step,
        remaining_loop_count=remaining_loop_count,
    )
    doc = read_sch_binary(plan.source_sch)

    selected = [s for s in doc.steps if s.step_no >= plan.resume_sch_step and not s.is_end]
    if not selected:
        raise ValueError(f"No steps to resume from step {plan.resume_sch_step}")

    if plan.remaining_loop_count is not None:
        selected = _apply_remaining_loops(selected, plan.remaining_loop_count)

    selected = renumber_steps(selected)
    end_record = _make_end_step(len(selected) + 1, doc.step_size, template=selected[-1].record)
    selected.append(end_record)

    resumed = SchBinaryDocument(
        path=doc.path,
        sch_version=doc.sch_version,
        payload_offset=doc.payload_offset,
        step_size=doc.step_size,
        header=doc.header,
        steps=tuple(selected),
    )

    out = Path(output_path)
    write_sch_binary(resumed, out)

    plan.resumed_step_count = len(selected)
    return ResumeResult(plan=plan, output_path=out, document=resumed)


def _find_loop_step(steps: tuple[SchBinaryStep, ...]) -> tuple[SchBinaryStep | None, int | None]:
    for step in reversed(steps):
        if step.step_type_code == int(SCH_STEP_TYPE_LOOP):
            _, count = read_loop_info(step)
            return step, count
    return None, None


def _apply_remaining_loops(steps: list[SchBinaryStep], remaining: int) -> list[SchBinaryStep]:
    patched: list[SchBinaryStep] = []
    for step in steps:
        if step.step_type_code == int(SCH_STEP_TYPE_LOOP):
            patched.append(patch_loop_count(step, remaining))
        else:
            patched.append(step)
    return patched


def _make_end_step(step_no: int, step_size: int, *, template: bytes) -> SchBinaryStep:
    record = bytearray(template)
    if len(record) < step_size:
        record.extend(b"\x00" * (step_size - len(record)))
    record = record[:step_size]
    struct.pack_into("<i", record, 0, step_no)
    struct.pack_into("<i", record, 8, int(SCH_STEP_TYPE_END))
    return SchBinaryStep(step_no=step_no, step_type_code=int(SCH_STEP_TYPE_END), record=bytes(record))
