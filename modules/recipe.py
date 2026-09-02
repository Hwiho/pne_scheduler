"""Charge / discharge / rest recipe units that live inside experiment modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Literal

from ..ir.cell_profile import CellProfile
from ..ir.step_intent import StepIntent

RecipeKind = Literal["charge", "discharge", "rest", "cycle", "loop", "end"]
RecipeMode = Literal["CCCV", "CC", "CV"]


@dataclass
class RecipeUnit:
    """One editable charge, discharge, rest, or control step."""

    kind: RecipeKind
    mode: RecipeMode | None = None
    c_rate: float | None = None
    end_voltage_v: float | None = None
    end_time_s: float | None = None
    end_capacity_fraction: float | None = None
    cv_cutoff_c_rate: float | None = None
    loop_count: int | None = None
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {key: value for key, value in data.items() if value not in (None, "")}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | RecipeUnit) -> RecipeUnit:
        if isinstance(data, RecipeUnit):
            return data
        known = {key: value for key, value in data.items() if key in cls.__dataclass_fields__}
        kind = known.get("kind")
        if kind not in {"charge", "discharge", "rest", "cycle", "loop", "end"}:
            raise ValueError(f"Unknown recipe unit kind: {kind!r}")
        return cls(**known)

    def summary(self) -> str:
        if self.kind == "rest":
            return f"REST {format_seconds(self.end_time_s)}" if self.end_time_s else "REST"
        if self.kind == "loop":
            count = self.loop_count if self.loop_count is not None else 1
            return f"LOOP ×{count}"
        if self.kind in {"cycle", "end"}:
            return self.kind.upper()
        rate = format_c_rate(self.c_rate) if self.c_rate is not None else ""
        mode = self.mode or "CC"
        verb = "CHG" if self.kind == "charge" else "DCHG"
        if mode == "CCCV":
            verb = "CCCV"
        end = ""
        if self.end_voltage_v is not None:
            end = f" → {self.end_voltage_v:g} V"
        elif self.end_time_s is not None:
            end = f" {format_seconds(self.end_time_s)}"
        elif self.end_capacity_fraction is not None:
            end = f" ΔSOC {self.end_capacity_fraction:.0%}"
        return f"{rate} {verb}{end}".strip()


@dataclass
class ModuleRecipe:
    """Setup once, then an optional repeating body, then trailing steps."""

    preset: str = "custom"
    setup: list[RecipeUnit] = field(default_factory=list)
    repeat: list[RecipeUnit] = field(default_factory=list)
    repeat_count: int = 1
    after: list[RecipeUnit] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "preset": self.preset,
            "setup": [unit.to_dict() for unit in self.setup],
            "repeat": [unit.to_dict() for unit in self.repeat],
            "repeat_count": self.repeat_count,
            "after": [unit.to_dict() for unit in self.after],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ModuleRecipe:
        payload = data or {}
        return cls(
            preset=str(payload.get("preset") or "custom"),
            setup=_units_from(payload.get("setup") or []),
            repeat=_units_from(payload.get("repeat") or []),
            repeat_count=int(payload.get("repeat_count") or 1),
            after=_units_from(payload.get("after") or []),
        )

    @property
    def is_empty(self) -> bool:
        return not (self.setup or self.repeat or self.after)

    def card_lines(self, *, limit: int = 10) -> list[str]:
        lines: list[str] = []
        if self.setup:
            lines.append("Setup")
            lines.extend(f"  {unit.summary()}" for unit in self.setup)
        if self.repeat:
            count = max(self.repeat_count, 1)
            lines.append(f"Repeat ×{count}")
            lines.extend(f"  {unit.summary()}" for unit in self.repeat)
        if self.after:
            lines.append("After")
            lines.extend(f"  {unit.summary()}" for unit in self.after)
        if len(lines) <= limit:
            return lines
        return [*lines[: limit - 1], f"  … {len(lines) - (limit - 1)} more"]

    def expand(self, cell: CellProfile) -> list[StepIntent]:
        steps: list[StepIntent] = []
        steps.extend(_expand_units(self.setup, cell))
        if self.repeat:
            body = _expand_units(self.repeat, cell)
            count = max(int(self.repeat_count), 1)
            if count == 1:
                steps.extend(body)
            else:
                marker_index = len(steps)
                steps.append(StepIntent(step_type="cycle", label="repeat marker"))
                steps.extend(body)
                steps.append(
                    StepIntent(
                        step_type="loop",
                        loop_goto_step=marker_index + 2,
                        loop_count=count,
                        label=f"repeat ×{count}",
                    )
                )
        steps.extend(_expand_units(self.after, cell))
        return steps


def charge(
    *,
    c_rate: float,
    end_voltage_v: float | None = None,
    end_time_s: float | None = None,
    mode: RecipeMode = "CC",
    cv_cutoff_c_rate: float | None = None,
    label: str = "",
) -> RecipeUnit:
    return RecipeUnit(
        kind="charge",
        mode=mode,
        c_rate=c_rate,
        end_voltage_v=end_voltage_v,
        end_time_s=end_time_s,
        cv_cutoff_c_rate=cv_cutoff_c_rate,
        label=label,
    )


def discharge(
    *,
    c_rate: float,
    end_voltage_v: float | None = None,
    end_time_s: float | None = None,
    end_capacity_fraction: float | None = None,
    mode: RecipeMode = "CC",
    label: str = "",
) -> RecipeUnit:
    return RecipeUnit(
        kind="discharge",
        mode=mode,
        c_rate=c_rate,
        end_voltage_v=end_voltage_v,
        end_time_s=end_time_s,
        end_capacity_fraction=end_capacity_fraction,
        label=label,
    )


def rest(end_time_s: float, label: str = "") -> RecipeUnit:
    return RecipeUnit(kind="rest", end_time_s=end_time_s, label=label)


def end_step(label: str = "") -> RecipeUnit:
    return RecipeUnit(kind="end", label=label)


def format_c_rate(c_rate: float) -> str:
    if abs(c_rate - 1.0 / 3.0) < 1e-6:
        return "C/3"
    if abs(c_rate - 0.5) < 1e-6:
        return "C/2"
    if abs(c_rate * 10 - round(c_rate * 10)) < 1e-6:
        value = c_rate if abs(c_rate - round(c_rate)) > 1e-6 else int(round(c_rate))
        return f"{value}C"
    return f"{c_rate:g}C"


def format_seconds(seconds: float | None) -> str:
    if seconds is None:
        return ""
    if seconds >= 3600 and abs(seconds % 3600) < 1e-6:
        return f"{int(round(seconds / 3600))} h"
    if seconds >= 60 and abs(seconds % 60) < 1e-6:
        return f"{int(round(seconds / 60))} min"
    if abs(seconds - round(seconds)) < 1e-6:
        return f"{int(round(seconds))} s"
    return f"{seconds:g} s"


def _units_from(items: Iterable[Any]) -> list[RecipeUnit]:
    return [RecipeUnit.from_dict(item) for item in items]


def _expand_units(units: list[RecipeUnit], cell: CellProfile) -> list[StepIntent]:
    steps: list[StepIntent] = []
    for unit in units:
        if unit.kind == "rest":
            steps.append(
                StepIntent(
                    step_type="rest",
                    label=unit.label or "rest",
                    end_time_s=unit.end_time_s,
                )
            )
            continue
        if unit.kind == "cycle":
            steps.append(StepIntent(step_type="cycle", label=unit.label or "cycle"))
            continue
        if unit.kind == "loop":
            steps.append(
                StepIntent(
                    step_type="loop",
                    label=unit.label or "loop",
                    loop_count=unit.loop_count,
                )
            )
            continue
        if unit.kind == "end":
            steps.append(StepIntent(step_type="end", label=unit.label or "end"))
            continue

        voltage = unit.end_voltage_v
        if unit.kind == "charge" and voltage is None:
            voltage = cell.v_max
        if (
            unit.kind == "discharge"
            and voltage is None
            and unit.end_capacity_fraction is None
            and unit.end_time_s is None
        ):
            voltage = cell.v_min
        is_cccv = unit.kind == "charge" and (unit.mode or "CC") == "CCCV"
        steps.append(
            StepIntent(
                step_type=unit.kind,
                mode=unit.mode or "CC",
                label=unit.label or unit.summary(),
                c_rate=unit.c_rate,
                voltage_v=voltage if is_cccv else None,
                end_voltage_v=voltage,
                end_time_s=unit.end_time_s,
                end_capacity_fraction=unit.end_capacity_fraction,
                cv_cutoff_c_rate=unit.cv_cutoff_c_rate if is_cccv else None,
            )
        )
    return steps
