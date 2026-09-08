"""Answer the question the lab actually asks: how much fits in the time I have?

Cycle counts are chosen backwards.  Nobody decides to run 173 cycles; they decide
the cell has to come off the cycler before a review, a shipment, or a holiday, and
then work out what fits.  Doing that by hand means editing the loop count, reading
the estimate, and editing again.

`cycles_within` does the search instead.  It asks the real estimator for each
candidate — the same one the summary shows — so a campaign's RPT blocks, rests and
CV tapers are all counted, not approximated by a per-cycle multiplication.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..spec import units

# A campaign of a few thousand cycles is already beyond any realistic bench
# booking; the ceiling exists so a mistyped budget cannot spin forever.
MAX_SEARCH_CYCLES = 20_000


@dataclass(frozen=True, slots=True)
class CycleBudget:
    total_cycles: int = 0
    seconds: float = 0.0
    budget_seconds: float = 0.0
    exact: bool = False
    notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors and self.total_cycles > 0

    @property
    def headroom_seconds(self) -> float:
        return self.budget_seconds - self.seconds

    def as_text(self) -> str:
        if self.errors:
            return " ".join(self.errors)
        if not self.total_cycles:
            return "주어진 기간 안에는 한 사이클도 넣을 수 없습니다."
        return (
            f"{units.format_duration_ko(self.budget_seconds)} 안에 "
            f"{self.total_cycles} 사이클 · 예상 {units.format_duration_ko(self.seconds)}"
            f" (여유 {units.format_duration_ko(self.headroom_seconds)})"
        )


def cycles_within(
    budget_seconds: float,
    estimate_seconds: Callable[[int], float | None],
    *,
    step: int = 1,
    max_cycles: int = MAX_SEARCH_CYCLES,
) -> CycleBudget:
    """Largest cycle count whose estimated run fits inside ``budget_seconds``.

    ``estimate_seconds`` maps a cycle count to its predicted duration, or to
    ``None`` when the schedule cannot be estimated at all.  ``step`` keeps the
    answer on a usable grid — a campaign measuring every 50 cycles wants 150, not
    147 — and the search only ever returns a count it actually evaluated.
    """
    errors: list[str] = []
    if budget_seconds <= 0:
        errors.append("기간은 0보다 커야 합니다.")
    if step < 1:
        errors.append("사이클 단위는 1 이상이어야 합니다.")
    if max_cycles < 1:
        errors.append("최대 사이클 수는 1 이상이어야 합니다.")
    if errors:
        return CycleBudget(budget_seconds=max(budget_seconds, 0.0), errors=tuple(errors))

    # Grow geometrically to bracket the answer, then bisect on the grid. The
    # estimator is the expensive part, so this keeps the number of calls in the
    # tens even for a several-thousand-cycle budget.
    def duration(count: int) -> float | None:
        return estimate_seconds(count)

    first = duration(step)
    if first is None:
        return CycleBudget(
            budget_seconds=budget_seconds,
            errors=("이 스케줄은 예상 시간을 계산할 수 없어 역산할 수 없습니다.",),
        )
    if first > budget_seconds:
        return CycleBudget(
            budget_seconds=budget_seconds,
            seconds=first,
            notes=(
                f"{step} 사이클만으로도 {units.format_duration_ko(first)} 가 걸려 "
                "주어진 기간을 넘습니다.",
            ),
        )

    low, low_seconds = step, first
    high = step * 2
    while high <= max_cycles:
        seconds = duration(high)
        if seconds is None or seconds > budget_seconds:
            break
        low, low_seconds = high, seconds
        high *= 2
    else:
        high = max_cycles + step

    # Bisect between the last count that fit and the first that did not.
    lo_grid, hi_grid = low // step, min(high, max_cycles + step) // step
    while lo_grid + 1 < hi_grid:
        mid_grid = (lo_grid + hi_grid) // 2
        seconds = duration(mid_grid * step)
        if seconds is not None and seconds <= budget_seconds:
            lo_grid, low_seconds = mid_grid, seconds
        else:
            hi_grid = mid_grid

    total = lo_grid * step
    notes = [
        f"{units.format_duration_ko(budget_seconds)} 예산에 "
        f"{total} 사이클이 들어갑니다."
    ]
    if step > 1:
        notes.append(f"{step} 사이클 단위로 맞췄습니다.")
    if total >= max_cycles:
        notes.append(f"탐색 상한 {max_cycles} 사이클에 도달했습니다.")

    return CycleBudget(
        total_cycles=total,
        seconds=low_seconds,
        budget_seconds=budget_seconds,
        notes=tuple(notes),
        warnings=(
            "예상 시간은 CV 감쇠와 전압 종료 조건을 근사한 값입니다. "
            "실제 소요 시간은 셀 상태에 따라 달라집니다.",
        ),
    )


__all__ = ["MAX_SEARCH_CYCLES", "CycleBudget", "cycles_within"]
