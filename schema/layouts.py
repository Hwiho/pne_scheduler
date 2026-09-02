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
    pne_unit: str | None = None
    ctspro_build: str | None = None


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


def get_sch_layout_for_unit(
    version: int,
    pne_unit: str | None = None,
    ctspro_build: str | None = None,
) -> SchLayout | None:
    """
    Resolve layout for (unit, CTS build, file version).

    Per-unit overrides from EQUIPMENT_REGISTRY take precedence when they match
    the requested file version. Falls back to global SCH_LAYOUTS by version.
    """
    base = get_sch_layout(version)
    if base is None or pne_unit is None:
        return base

    from .equipment_registry import get_unit_equipment_profile

    profile = get_unit_equipment_profile(pne_unit)
    if profile is None:
        return SchLayout(
            version=base.version,
            payload_offset=base.payload_offset,
            step_size=base.step_size,
            pne_unit=pne_unit,
            ctspro_build=ctspro_build,
        )

    version_hex = f"0x{int(version):08x}"
    candidates = (*profile.layouts_confirmed, *profile.layouts_observed)
    for row in candidates:
        if row.file_version.lower() != version_hex.lower():
            continue
        return SchLayout(
            version=int(version),
            payload_offset=row.payload_offset,
            step_size=row.step_size,
            pne_unit=pne_unit,
            ctspro_build=ctspro_build or profile.ctspro_build,
        )

    return SchLayout(
        version=base.version,
        payload_offset=base.payload_offset,
        step_size=base.step_size,
        pne_unit=pne_unit,
        ctspro_build=ctspro_build or profile.ctspro_build,
    )
