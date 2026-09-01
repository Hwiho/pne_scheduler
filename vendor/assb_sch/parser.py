"""Vendored ASSB `.sch` parser (stdlib only).

Derived from ASSB_Analyzer_dev assb_analyzer/io/pne_converter.py SCH helpers.
"""

from __future__ import annotations

import hashlib
import math
import struct
from collections.abc import Mapping
from pathlib import Path

from .constants import (
    SCH_CONDITION_CANDIDATE_FIELDS_BY_LAYOUT,
    SCH_CURRENT_CONDITION_MAPPING_POLICY,
    SCH_DCIR_SOC_RULES_LAYOUT_POLICY,
    SCH_DCIR_SOC_RULES_MAPPING_POLICY,
    SCH_DCIR_SOC_RULES_SCHEMA,
    SCH_END_CURRENT_OFFSET,
    SCH_REFERENCE_CURRENT_OFFSET,
    SCH_STEP_SIZE_CANDIDATES,
    SCH_STEP_TYPE_CC_CHARGE,
    SCH_STEP_TYPE_CC_DISCHARGE,
    SCH_STEP_TYPE_CCCV,
    SCH_STEP_TYPE_CYCLE_MARKER,
    SCH_STEP_TYPE_END,
    SCH_STEP_TYPE_LOOP,
    SCH_STEP_TYPES,
)
from .models import MetadataValue, SchCycleMap, SchStep

__all__ = [
    "parse_sch_cycle_map_bytes",
    "sch_cycle_map_has_terminal_end",
    "detect_sch_layout",
]


def _i32_from_record(record: bytes, offset: int) -> int:
    return int(struct.unpack_from("<i", record, offset)[0])


def _schedule_candidate_score(data: bytes, payload_offset: int, step_size: int) -> int:
    score = 0
    for expected_step_no in range(1, 8):
        base = payload_offset + (expected_step_no - 1) * step_size
        if base + 12 > len(data):
            break
        chunk = data[base : base + step_size]
        step_no = _i32_from_record(chunk, 0)
        step_type = _i32_from_record(chunk, 8) & 0xFFFF
        if step_no == expected_step_no and step_type in SCH_STEP_TYPES:
            score += 1
    return score


def detect_sch_layout(data: bytes) -> tuple[int, int] | None:
    best: tuple[int, int, int] | None = None
    scan_limit = min(len(data) - 12, 5000)
    for payload_offset in range(0, scan_limit, 4):
        step_no = struct.unpack_from("<i", data, payload_offset)[0]
        step_type = struct.unpack_from("<i", data, payload_offset + 8)[0] & 0xFFFF
        if step_no != 1 or step_type not in SCH_STEP_TYPES:
            continue
        for step_size in SCH_STEP_SIZE_CANDIDATES:
            score = _schedule_candidate_score(data, payload_offset, step_size)
            if best is None or score > best[0]:
                best = (score, payload_offset, step_size)
    if best is None or best[0] < 3:
        return None
    return best[1], best[2]


def _sch_candidate_value(record: bytes, value_type: str, offset: int) -> MetadataValue:
    size = 1 if value_type == "uint8" else 4
    if offset + size > len(record):
        return None
    if value_type == "float32":
        return float(struct.unpack_from("<f", record, offset)[0])
    if value_type == "uint32":
        return int(struct.unpack_from("<I", record, offset)[0])
    if value_type == "uint8":
        return record[offset]
    return None


def _read_sch_condition_candidates(
    record: bytes,
    fields: Mapping[str, tuple[str, int]],
) -> dict[str, MetadataValue]:
    return {
        field_name: _sch_candidate_value(record, value_type, offset)
        for field_name, (value_type, offset) in fields.items()
    }


def _positive_sch_current_mA(record: bytes, offset: int) -> float | None:
    value = _sch_candidate_value(record, "float32", offset)
    if not isinstance(value, float) or not math.isfinite(value) or value <= 0:
        return None
    return value


def _sch_header_version(data: bytes) -> int | None:
    if len(data) < 8:
        return None
    return int(struct.unpack_from("<I", data, 4)[0])


def _sch_reference_selector(step: SchStep) -> dict[str, MetadataValue]:
    return {
        "StepNo": step.step_no,
        "StepTypeCode": step.step_type,
        "selector_source": "sch_file_step_condition",
        "verified": False,
        "fields": dict(step.condition_candidates),
    }


def _cycle_by_schedule_step(steps: list[SchStep]) -> dict[int, int]:
    cycle_by_step_no: dict[int, int] = {}
    current_cycle = 1
    next_cycle = 2
    pending_cycle: int | None = None
    for step in steps:
        if step.step_type == SCH_STEP_TYPE_CYCLE_MARKER:
            cycle_by_step_no[step.step_no] = current_cycle
            pending_cycle = next_cycle
            next_cycle += 1
            continue
        if pending_cycle is not None:
            cycle_by_step_no[step.step_no] = pending_cycle
            if step.step_type == SCH_STEP_TYPE_LOOP:
                current_cycle = pending_cycle
                pending_cycle = None
            continue
        cycle_by_step_no[step.step_no] = current_cycle
    return cycle_by_step_no


def _sch_dcir_soc_rules_payload(
    *,
    header_version: int | None,
    step_size: int,
    sha256: str,
    steps: list[SchStep],
) -> dict[str, MetadataValue]:
    supported = (header_version, step_size) == (0x00010003, 612)
    rules: list[dict[str, MetadataValue]] = []
    if supported:
        directions = {
            SCH_STEP_TYPE_CCCV: "Charge",
            SCH_STEP_TYPE_CC_CHARGE: "Charge",
            SCH_STEP_TYPE_CC_DISCHARGE: "Discharge",
        }
        for step in steps:
            direction = directions.get(step.step_type)
            rate = step.condition_candidates.get("fSocRate")
            reference_step_no = step.condition_candidates.get("bUseDataStepNo")
            use_actual = step.condition_candidates.get("bUseActualCapa")
            if (
                direction is None
                or not isinstance(rate, float)
                or not math.isfinite(rate)
                or rate <= 0.0
                or rate > 100.0
                or type(reference_step_no) is not int
                or reference_step_no <= 0
                or type(use_actual) is not int
                or use_actual not in {0, 1}
            ):
                continue
            if not rate.is_integer():
                rules.clear()
                break
            rules.append(
                {
                    "sch_step_no": step.step_no,
                    "cts_action_step_no": step.step_no + 1,
                    "sch_step_type_code": step.step_type,
                    "direction": direction,
                    "soc_rate_percent": rate,
                    "reference_cts_step_no": reference_step_no,
                    "use_actual_capacity": bool(use_actual),
                    "verified": True,
                }
            )
    return {
        "schema": SCH_DCIR_SOC_RULES_SCHEMA,
        "layout_policy": SCH_DCIR_SOC_RULES_LAYOUT_POLICY if supported else None,
        "mapping_policy": SCH_DCIR_SOC_RULES_MAPPING_POLICY if supported else None,
        "sch_header_version": header_version,
        "sch_step_size": step_size,
        "sch_sha256": sha256,
        "rules": rules,
        "current_condition_mapping_policy": SCH_CURRENT_CONDITION_MAPPING_POLICY,
    }


def parse_sch_cycle_map_bytes(
    data: bytes,
    *,
    source_path: Path,
) -> SchCycleMap | None:
    if not isinstance(data, bytes):
        raise TypeError("SCH parser requires bytes.")
    source_path = Path(source_path)
    layout = detect_sch_layout(data)
    if layout is None:
        return None
    payload_offset, step_size = layout
    header_version = _sch_header_version(data)
    condition_fields = (
        SCH_CONDITION_CANDIDATE_FIELDS_BY_LAYOUT.get((header_version, step_size), {})
        if header_version is not None
        else {}
    )
    steps: list[SchStep] = []
    index = 0
    while payload_offset + index * step_size + 12 <= len(data):
        base = payload_offset + index * step_size
        step_no = struct.unpack_from("<i", data, base)[0]
        step_type = struct.unpack_from("<i", data, base + 8)[0] & 0xFFFF
        if step_no <= 0 or step_type not in SCH_STEP_TYPES:
            break
        record = data[base : base + step_size]
        steps.append(
            SchStep(
                step_no=step_no,
                step_type=step_type,
                condition_candidates=_read_sch_condition_candidates(
                    record, condition_fields
                ),
                reference_current_mA=_positive_sch_current_mA(
                    record, SCH_REFERENCE_CURRENT_OFFSET
                ),
                end_current_mA=_positive_sch_current_mA(
                    record, SCH_END_CURRENT_OFFSET
                ),
            )
        )
        if step_type == SCH_STEP_TYPE_END:
            break
        index += 1
    if not steps:
        return None
    sha256 = hashlib.sha256(data).hexdigest()
    return SchCycleMap(
        source_path=source_path,
        header_version=header_version,
        payload_offset=payload_offset,
        step_size=step_size,
        step_count=len(steps),
        cycle_by_step_no=_cycle_by_schedule_step(steps),
        sch_condition_candidates=[
            {
                "StepNo": step.step_no,
                "StepTypeCode": step.step_type,
                "source": "PNE_file_structures_sch_condition_candidate",
                "verified": False,
                "field_offsets": {
                    field_name: offset
                    for field_name, (_, offset) in condition_fields.items()
                },
                "raw_fields": step.condition_candidates,
            }
            for step in steps
        ],
        sch_reference_selectors=[_sch_reference_selector(step) for step in steps],
        sch_dcir_soc_rules=_sch_dcir_soc_rules_payload(
            header_version=header_version,
            step_size=step_size,
            sha256=sha256,
            steps=steps,
        ),
        current_steps=tuple(steps),
        physical_bytes=len(data),
        sha256=sha256,
    )


def sch_cycle_map_has_terminal_end(cycle_map: SchCycleMap) -> bool:
    if not cycle_map.sch_condition_candidates:
        return False
    step_type = cycle_map.sch_condition_candidates[-1].get("StepTypeCode")
    return isinstance(step_type, int) and not isinstance(step_type, bool) and (
        step_type == SCH_STEP_TYPE_END
    )
