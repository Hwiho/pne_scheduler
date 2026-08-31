"""Parse .sch binary into a display-friendly schedule document."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

from ..classify import ScheduleFilenameMatch, classify_schedule_filename
from ..schema.enums import (
    SCH_STEP_TYPE_CC_CHARGE,
    SCH_STEP_TYPE_CC_DISCHARGE,
    SCH_STEP_TYPE_CCCV,
    SCH_STEP_TYPE_CYCLE_MARKER,
    SCH_STEP_TYPE_END,
    SCH_STEP_TYPE_LOOP,
    SCH_STEP_TYPE_REST,
    SCH_STEP_TYPES,
)
from ..engine.c_rate import snap_c_rate
from ..protocol import ProtocolInference, infer_protocol_from_schedule
from ..schema.v0x00010003_612 import (
    OFFSET_F_END_C,
    OFFSET_F_END_I,
    OFFSET_F_END_V,
)
from ..stack import CellGeometryInference, c_rate_from_current, infer_cell_geometry, l_from_fvref
from .layout import detect_sch_layout

TYPE_NAMES: dict[int, str] = {
    1: "CHARGE",
    2: "DISCHARGE",
    3: "REST",
    4: "OCV",
    5: "IMPEDANCE",
    6: "END",
    7: "CYCLE",
    8: "LOOP",
    9: "PATTERN",
    0x0A: "BALANCE",
    int(SCH_STEP_TYPE_CCCV): "CCCV",
    int(SCH_STEP_TYPE_CC_CHARGE): "CC_CHG",
    int(SCH_STEP_TYPE_CC_DISCHARGE): "CC_DCHG",
}


@dataclass(frozen=True, slots=True)
class SchStepView:
    step_no: int
    step_type: str
    step_type_code: int
    f_vref: float
    f_iref: float
    f_end_time: float
    f_end_v: float
    f_end_i: float
    f_end_c: float
    step_l_level: float | None = None
    c_rate: float | None = None
    c_rate_label: str = ""
    c_rate_preset: float | None = None
    is_fast_charge: bool = False
    step_l_detail: str = ""


@dataclass
class ScheduleDocument:
    path: Path
    sch_version: int | None
    payload_offset: int
    step_size: int
    classification: ScheduleFilenameMatch
    geometry: CellGeometryInference
    protocol: ProtocolInference | None = None
    steps: list[SchStepView] = field(default_factory=list)

    @property
    def stack_level(self):
        return self.geometry.stack_level

    @property
    def nominal_capacity_mAh(self) -> float:
        return self.geometry.capacity.nominal_capacity_mAh


def parse_schedule_file(path: str | Path) -> ScheduleDocument:
    resolved = Path(path)
    data = resolved.read_bytes()
    layout = _detect_layout(data)
    if layout is None:
        raise ValueError(f"Could not detect SCH step layout: {resolved}")

    payload_offset, step_size = layout
    sch_version = struct.unpack_from("<I", data, 4)[0] if len(data) >= 8 else None
    raw_steps = _read_steps(data, payload_offset, step_size)

    classification = classify_schedule_filename(resolved)
    geometry = infer_cell_geometry(
        resolved.name,
        [s.f_vref for s in raw_steps],
        [s.f_iref for s in raw_steps],
    )

    fp = geometry.footprint
    mode = geometry.cell_mode
    file_l = geometry.stack_level.primary.l_value

    steps: list[SchStepView] = []
    for step in raw_steps:
        step_l = None
        step_l_detail = ""
        if step.f_vref >= 15.0:
            guess = l_from_fvref(step.f_vref)
            if guess is not None:
                step_l = guess.l_value
                step_l_detail = guess.detail

        l_for_c = step_l if step_l is not None else file_l
        c_rate = c_rate_from_current(
            step.f_iref,
            footprint=fp,
            cell_mode=mode,
            l_value=l_for_c,
        )
        c_snap = snap_c_rate(c_rate) if c_rate is not None else None

        steps.append(
            SchStepView(
                step_no=step.step_no,
                step_type=step.step_type,
                step_type_code=step.step_type_code,
                f_vref=step.f_vref,
                f_iref=step.f_iref,
                f_end_time=step.f_end_time,
                f_end_v=step.f_end_v,
                f_end_i=step.f_end_i,
                f_end_c=step.f_end_c,
                step_l_level=step_l,
                c_rate=c_rate,
                c_rate_label=c_snap.label if c_snap is not None else "",
                c_rate_preset=c_snap.snapped_value if c_snap is not None else None,
                is_fast_charge=c_snap.is_fast_charge if c_snap is not None else False,
                step_l_detail=step_l_detail,
            )
        )

    return ScheduleDocument(
        path=resolved,
        sch_version=sch_version,
        payload_offset=payload_offset,
        step_size=step_size,
        classification=classification,
        geometry=geometry,
        protocol=infer_protocol_from_schedule(
            resolved.name,
            steps,
            filename_category=classification.category.value,
        ),
        steps=steps,
    )


@dataclass(frozen=True, slots=True)
class _RawStep:
    step_no: int
    step_type_code: int
    step_type: str
    f_vref: float
    f_iref: float
    f_end_time: float
    f_end_v: float
    f_end_i: float
    f_end_c: float


def _detect_layout(data: bytes) -> tuple[int, int] | None:
    layout = detect_sch_layout(data)
    if layout is None:
        return None
    return layout.payload_offset, layout.step_size


def _read_steps(data: bytes, payload_offset: int, step_size: int) -> list[_RawStep]:
    steps: list[_RawStep] = []
    index = 0
    while payload_offset + index * step_size + 12 <= len(data):
        base = payload_offset + index * step_size
        step_no = struct.unpack_from("<i", data, base)[0]
        step_type_code = struct.unpack_from("<i", data, base + 8)[0] & 0xFFFF
        if step_no <= 0 or step_type_code not in SCH_STEP_TYPES:
            break
        steps.append(
            _RawStep(
                step_no=step_no,
                step_type_code=step_type_code,
                step_type=TYPE_NAMES.get(step_type_code, hex(step_type_code)),
                f_vref=struct.unpack_from("<f", data, base + 16)[0],
                f_iref=struct.unpack_from("<f", data, base + 20)[0],
                f_end_time=struct.unpack_from("<f", data, base + 24)[0],
                f_end_v=struct.unpack_from("<f", data, base + OFFSET_F_END_V)[0],
                f_end_i=struct.unpack_from("<f", data, base + OFFSET_F_END_I)[0],
                f_end_c=struct.unpack_from("<f", data, base + OFFSET_F_END_C)[0],
            )
        )
        if step_type_code == int(SCH_STEP_TYPE_END):
            break
        index += 1
    return steps
