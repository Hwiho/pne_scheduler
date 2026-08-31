"""Approximate schedule duration from version-independent StepIntent values."""

from __future__ import annotations

from dataclasses import dataclass

from ..ir.step_intent import StepIntent


@dataclass(frozen=True, slots=True)
class StepDurationEstimate:
    step_index: int
    seconds: float | None
    basis: str
    approximate: bool


@dataclass(frozen=True, slots=True)
class DurationEstimate:
    estimated_seconds: float
    exact_seconds: float
    approximate_seconds: float
    unknown_step_count: int
    steps: tuple[StepDurationEstimate, ...]
    warnings: tuple[str, ...] = ()

    @property
    def is_complete(self) -> bool:
        return self.unknown_step_count == 0

    @property
    def is_exact(self) -> bool:
        return self.is_complete and self.approximate_seconds == 0


def estimate_step_duration(
    step: StepIntent,
    *,
    step_index: int,
) -> StepDurationEstimate:
    if step.step_type in {"cycle", "loop", "end"}:
        return StepDurationEstimate(step_index, 0.0, "control step", False)

    if step.end_time_s is not None and step.end_time_s >= 0:
        has_competing_condition = any(
            value is not None
            for value in (
                step.end_voltage_v,
                step.end_capacity_fraction,
                step.cv_cutoff_c_rate,
            )
        )
        return StepDurationEstimate(
            step_index,
            float(step.end_time_s),
            "configured end time",
            has_competing_condition,
        )

    if (
        step.step_type in {"charge", "discharge"}
        and step.c_rate is not None
        and step.c_rate > 0
    ):
        fraction = (
            float(step.end_capacity_fraction)
            if step.end_capacity_fraction is not None
            else 1.0
        )
        if fraction < 0:
            return StepDurationEstimate(
                step_index,
                None,
                "negative capacity fraction",
                True,
            )
        return StepDurationEstimate(
            step_index,
            3600.0 * fraction / float(step.c_rate),
            "capacity fraction / C-rate"
            if step.end_capacity_fraction is not None
            else "nominal 100% capacity / C-rate",
            True,
        )

    return StepDurationEstimate(
        step_index,
        None,
        "no time or C-rate duration model",
        True,
    )


def estimate_steps_duration(steps: list[StepIntent]) -> DurationEstimate:
    estimates = tuple(
        estimate_step_duration(step, step_index=index)
        for index, step in enumerate(steps, start=1)
    )
    exact = sum(
        estimate.seconds or 0.0
        for estimate in estimates
        if not estimate.approximate
    )
    approximate = sum(
        estimate.seconds or 0.0
        for estimate in estimates
        if estimate.approximate
    )
    unknown = sum(estimate.seconds is None for estimate in estimates)
    warnings: list[str] = []

    for index, step in enumerate(steps):
        if step.step_type != "loop" or step.loop_count is None:
            continue
        target = step.loop_goto_step
        if target is None or target < 1 or target > index:
            warnings.append(
                f"Step {index + 1}: loop target is missing or outside the preceding body."
            )
            unknown += 1
            continue
        repeats = max(int(step.loop_count) - 1, 0)
        body = estimates[target - 1 : index]
        exact += repeats * sum(
            estimate.seconds or 0.0
            for estimate in body
            if not estimate.approximate
        )
        approximate += repeats * sum(
            estimate.seconds or 0.0
            for estimate in body
            if estimate.approximate
        )
        unknown += repeats * sum(estimate.seconds is None for estimate in body)
        if repeats:
            warnings.append(
                f"Step {index + 1}: loop count {step.loop_count} is interpreted "
                "as total body executions."
            )

    if any(
        step.mode == "CCCV" and step.end_time_s is None
        for step in steps
    ):
        warnings.append(
            "CCCV estimates include nominal CC capacity time but exclude unknown CV taper."
        )
    if any(
        estimate.approximate and estimate.seconds is not None
        for estimate in estimates
    ):
        warnings.append(
            "C-rate estimates assume nominal usable capacity and exclude equipment overhead."
        )

    return DurationEstimate(
        estimated_seconds=exact + approximate,
        exact_seconds=exact,
        approximate_seconds=approximate,
        unknown_step_count=unknown,
        steps=estimates,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def combine_duration_estimates(
    estimates: list[DurationEstimate],
) -> DurationEstimate:
    steps: list[StepDurationEstimate] = []
    warnings: list[str] = []
    offset = 0
    for estimate in estimates:
        steps.extend(
            StepDurationEstimate(
                step_index=item.step_index + offset,
                seconds=item.seconds,
                basis=item.basis,
                approximate=item.approximate,
            )
            for item in estimate.steps
        )
        offset += len(estimate.steps)
        warnings.extend(estimate.warnings)
    return DurationEstimate(
        estimated_seconds=sum(item.estimated_seconds for item in estimates),
        exact_seconds=sum(item.exact_seconds for item in estimates),
        approximate_seconds=sum(item.approximate_seconds for item in estimates),
        unknown_step_count=sum(item.unknown_step_count for item in estimates),
        steps=tuple(steps),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def format_duration(seconds: float) -> str:
    total = max(0, round(seconds))
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    if minutes or hours or days:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)
