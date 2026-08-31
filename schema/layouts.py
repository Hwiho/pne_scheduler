"""Version-specific framing for observed PNE CTSPro schedule files."""

from __future__ import annotations

from dataclasses import dataclass

from .enums import SchFileVersion

SCH_FILE_MAGIC = 0x000B4D71


@dataclass(frozen=True, slots=True)
class SchLayout:
    version: int
    payload_offset: int
    step_size: int


SCH_LAYOUTS: dict[int, SchLayout] = {
    int(SchFileVersion.V0X00010002): SchLayout(
        version=int(SchFileVersion.V0X00010002),
        payload_offset=1632,
        step_size=612,
    ),
    int(SchFileVersion.V0X00010003): SchLayout(
        version=int(SchFileVersion.V0X00010003),
        payload_offset=1760,
        step_size=612,
    ),
    int(SchFileVersion.V0X00010004): SchLayout(
        version=int(SchFileVersion.V0X00010004),
        payload_offset=1844,
        step_size=696,
    ),
}


def get_sch_layout(version: int) -> SchLayout | None:
    return SCH_LAYOUTS.get(int(version))
