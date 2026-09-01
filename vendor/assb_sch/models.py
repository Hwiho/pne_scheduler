"""ASSB-compatible SCH cycle map models (vendored subset)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

MetadataValue = Any


@dataclass(slots=True)
class SchStep:
    step_no: int
    step_type: int
    condition_candidates: dict[str, MetadataValue]
    reference_current_mA: float | None
    end_current_mA: float | None


@dataclass(frozen=True, slots=True)
class SchCycleMap:
    source_path: Path
    header_version: int | None
    payload_offset: int
    step_size: int
    step_count: int
    cycle_by_step_no: dict[int, int]
    sch_condition_candidates: list[dict[str, MetadataValue]]
    sch_reference_selectors: list[dict[str, MetadataValue]]
    sch_dcir_soc_rules: dict[str, MetadataValue]
    current_steps: tuple[SchStep, ...]
    physical_bytes: int
    sha256: str
