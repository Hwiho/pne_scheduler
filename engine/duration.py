"""Approximate schedule duration from version-independent StepIntent values."""

from __future__ import annotations

from dataclasses import dataclass
import math

from ..ir.step_intent import StepIntent


@dataclass(frozen=True, slots=True)
class StepDurationEstimate:
    step_index: int
    seconds: float | None
    basis: str
    approximate: bool
    upper_bound_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class DurationEstimate:
    estimated_seconds: float
    exact_seconds: float
    approximate_seconds: float
    unknown_step_count: int
    steps: tuple[StepDurationEstimate, ...]
    warnings: tuple[str, ...] = ()
    upper_bound_seconds: float | None = None

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
        return StepDurationEstimate(step_index, 0.0, "control step", False, 0.0)

    time_limit = (
        float(step.end_time_s) if step.end_time_s is not None
        and math.isfinite(step.end_time_s) and step.end_time_s >= 0 else None
    )
    if time_limit is not None:
        has_competing_condition = any(
            value is not None
            for value in (
                step.end_voltage_v,
                step.end_capacity_fraction,
                step.cv_cutoff_c_rate,
                step.dod_percent,
            )
        )
        if not has_competing_condition:
            return StepDurationEstimate(step_index, time_limit, "configured end time", False, time_limit)

    if step.dod_percent is not None and step.end_capacity_fraction is None:
        return StepDurationEstimate(step_index, None, "DOD field semantics unverified; timeout is a ceiling", True, time_limit)
    if (step.step_type == "charge" and step.mode == "CC"
            and step.end_capacity_fraction is None and step.voltage_v is not None
            and step.end_voltage_v is not None and step.end_voltage_v < step.voltage_v):
        return StepDurationEstimate(step_index, None, "partial SOC voltage target has no calibrated charge quantity", True, time_limit)

    if (
        step.step_type in {"charge", "discharge"}
        and step.c_rate is not None
        and step.c_rate > 0
        and math.isfinite(step.c_rate)
    ):
        fraction = (
            float(step.end_capacity_fraction)
            if step.end_capacity_fraction is not None
            else 1.0
        )
        if not math.isfinite(fraction) or fraction < 0:
            return StepDurationEstimate(
                step_index,
                None,
                "negative capacity fraction",
                True,
                time_limit,
            )
        return StepDurationEstimate(
            step_index,
            min(3600.0 * fraction / float(step.c_rate), time_limit) if time_limit is not None else 3600.0 * fraction / float(step.c_rate),
            "capacity fraction / C-rate"
            if step.end_capacity_fraction is not None
            else "nominal 100% capacity / C-rate",
            True,
            time_limit,
        )

    return StepDurationEstimate(
        step_index,
        None,
        "no time or C-rate duration model",
        True,
        time_limit,
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
    # A group's outer LOOP includes the completed execution cost of inner
    # loops, not only the raw duration of their one-pass steps.
    exact_cost = [0.0 if item.approximate else (item.seconds or 0.0) for item in estimates]
    approximate_cost = [(item.seconds or 0.0) if item.approximate else 0.0 for item in estimates]
    unknown_cost = [int(item.seconds is None) for item in estimates]
    upper_cost = [item.upper_bound_seconds or 0.0 for item in estimates]
    unbounded_cost = [int(item.upper_bound_seconds is None) for item in estimates]

    for index, step in enumerate(steps):
        if step.step_type != "loop" or step.loop_count is None:
            continue
        target = step.loop_goto_step
        if target is None or target < 1 or target > index:
            warnings.append(
                f"Step {index + 1}: loop target is missing or outside the preceding body."
            )
            unknown += 1
            unbounded_cost[index] += 1
            continue
        repeats = max(int(step.loop_count) - 1, 0)
        exact_cost[index] = repeats * sum(exact_cost[target - 1:index])
        approximate_cost[index] = repeats * sum(approximate_cost[target - 1:index])
        unknown_cost[index] = repeats * sum(unknown_cost[target - 1:index])
        upper_cost[index] = repeats * sum(upper_cost[target - 1:index])
        unbounded_cost[index] = repeats * sum(unbounded_cost[target - 1:index])
        exact += exact_cost[index]
        approximate += approximate_cost[index]
        unknown += unknown_cost[index]
        if repeats:
            warnings.append(
                f"Step {index + 1}: loop count {step.loop_count} is interpreted "
                "as total body executions."
            )

    if any(
        step.mode == "CCCV"
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
    if unknown:
        warnings.append("Some step durations cannot be estimated from voltage/DOD alone; the displayed total is partial, not a complete runtime.")
    if any(item.upper_bound_seconds is not None and item.approximate for item in estimates):
        warnings.append("Configured safety timeouts are separate upper limits, not expected charging times.")

    return DurationEstimate(
        estimated_seconds=exact + approximate,
        exact_seconds=exact,
        approximate_seconds=approximate,
        unknown_step_count=unknown,
        steps=estimates,
        warnings=tuple(dict.fromkeys(warnings)),
        upper_bound_seconds=sum(upper_cost) if not any(unbounded_cost) else None,
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
                upper_bound_seconds=item.upper_bound_seconds,
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
        upper_bound_seconds=(sum(item.upper_bound_seconds or 0 for item in estimates)
                             if all(item.upper_bound_seconds is not None for item in estimates) else None),
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
