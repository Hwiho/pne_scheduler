"""Read/write raw .sch step records while preserving file header."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from ..schema.enums import SCH_STEP_TYPE_END, SCH_STEP_TYPES
from ..schema.fields import OFFSET_LOOP_COUNT, OFFSET_LOOP_GOTO
from .layout import detect_sch_layout


@dataclass(frozen=True, slots=True)
class SchBinaryStep:
    step_no: int
    step_type_code: int
    record: bytes

    @property
    def is_loop(self) -> bool:
        return self.step_type_code == 8

    @property
    def is_end(self) -> bool:
        return self.step_type_code == int(SCH_STEP_TYPE_END)


@dataclass(frozen=True, slots=True)
class SchBinaryDocument:
    path: Path
    sch_version: int | None
    payload_offset: int
    step_size: int
    header: bytes
    steps: tuple[SchBinaryStep, ...]

    @property
    def step_count(self) -> int:
        return len(self.steps)


def read_sch_binary(path: str | Path) -> SchBinaryDocument:
    resolved = Path(path)
    data = resolved.read_bytes()
    layout = detect_sch_layout(data)
    if layout is None:
        raise ValueError(f"Could not detect SCH layout: {resolved}")

    payload_offset = layout.payload_offset
    step_size = layout.step_size
    sch_version = struct.unpack_from("<I", data, 4)[0] if len(data) >= 8 else None
    header = data[:payload_offset]
    steps: list[SchBinaryStep] = []
    index = 0
    while payload_offset + index * step_size + 12 <= len(data):
        base = payload_offset + index * step_size
        record = data[base : base + step_size]
        step_no = struct.unpack_from("<i", record, 0)[0]
        step_type = struct.unpack_from("<i", record, 8)[0] & 0xFFFF
        if step_no <= 0 or step_type not in SCH_STEP_TYPES:
            break
        steps.append(SchBinaryStep(step_no=step_no, step_type_code=step_type, record=record))
        if step_type == int(SCH_STEP_TYPE_END):
            break
        index += 1

    if not steps:
        raise ValueError(f"No steps found in {resolved}")

    return SchBinaryDocument(
        path=resolved,
        sch_version=sch_version,
        payload_offset=payload_offset,
        step_size=step_size,
        header=header,
        steps=tuple(steps),
    )


def write_sch_binary(doc: SchBinaryDocument, output_path: str | Path) -> None:
    out = Path(output_path)
    body = bytearray(doc.header)
    needed = doc.payload_offset + len(doc.steps) * doc.step_size
    if len(body) < needed:
        body.extend(b"\x00" * (needed - len(body)))
    for index, step in enumerate(doc.steps):
        start = doc.payload_offset + index * doc.step_size
        body[start : start + doc.step_size] = step.record
    out.write_bytes(bytes(body))


def renumber_steps(steps: list[SchBinaryStep]) -> list[SchBinaryStep]:
    renumbered: list[SchBinaryStep] = []
    for index, step in enumerate(steps, start=1):
        record = bytearray(step.record)
        struct.pack_into("<i", record, 0, index)
        renumbered.append(
            SchBinaryStep(step_no=index, step_type_code=step.step_type_code, record=bytes(record))
        )
    return renumbered


def patch_loop_count(step: SchBinaryStep, remaining_loops: int) -> SchBinaryStep:
    if not step.is_loop:
        raise ValueError("step is not LOOP")
    record = bytearray(step.record)
    struct.pack_into("<I", record, OFFSET_LOOP_COUNT, max(0, int(remaining_loops)))
    return SchBinaryStep(step_no=step.step_no, step_type_code=step.step_type_code, record=bytes(record))


def read_loop_info(step: SchBinaryStep) -> tuple[int | None, int | None]:
    if not step.is_loop:
        return None, None
    goto = struct.unpack_from("<I", step.record, OFFSET_LOOP_GOTO)[0]
    count = struct.unpack_from("<I", step.record, OFFSET_LOOP_COUNT)[0]
    return goto or None, count or None
