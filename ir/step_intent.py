"""User-facing schedule step intent (C-rate based)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

StepKind = Literal[
    "charge",
    "discharge",
    "rest",
    "ocv",
    "impedance",
    "cycle",
    "loop",
    "end",
]
StepModeName = Literal["CCCV", "CC", "CV"]


@dataclass
class StepIntent:
    step_type: StepKind
    mode: StepModeName | None = None
    label: str = ""
    c_rate: float | None = None
    cv_cutoff_c_rate: float | None = None
    voltage_v: float | None = None
    end_voltage_v: float | None = None
    end_time_s: float | None = None
    end_capacity_fraction: float | None = None
    loop_goto_step: int | None = None
    loop_count: int | None = None
    goto_step_id: int | None = None
    dcr_start_s: float | None = None
    dcr_end_s: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StepIntent:
        payload = dict(data)
        extra = payload.pop("extra", {})
        intent = cls(**payload)
        intent.extra = extra
        return intent
