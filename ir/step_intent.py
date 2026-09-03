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
    # Absolute overrides (preferred over C-rate when both are set).
    current_mA: float | None = None
    cv_cutoff_mA: float | None = None
    voltage_v: float | None = None
    end_voltage_v: float | None = None
    end_time_s: float | None = None
    end_capacity_fraction: float | None = None
    # SOC / capacity-reference (Ensol dod_percent @+384).
    dod_percent: float | None = None
    # Sampling (Ensol record_dV_mV @+332, record_time_s @+340).
    record_time_s: float | None = None
    record_dV_mV: float | None = None
    # LOOP (Gate B: loop_target@48 + loop_count@52; Ensol also writes @564).
    loop_goto_step: int | None = None
    loop_count: int | None = None
    loop_reset_capacity: bool = False
    # Legacy ASSB SOC reference step (offset unresolved vs Ensol map).
    goto_step_id: int | None = None
    # DC-IR window — kept on IR; binary packing deferred (Excel≠Ensol offsets).
    dcr_start_s: float | None = None
    dcr_end_s: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StepIntent:
        payload = dict(data)
        extra = payload.pop("extra", {})
        known = {key: payload[key] for key in cls.__dataclass_fields__ if key in payload}
        intent = cls(**known)
        intent.extra = extra
        return intent
