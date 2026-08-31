"""PNE .sch step type and mode constants."""

from __future__ import annotations

from enum import IntEnum


class SchFileVersion(IntEnum):
    V0X00010001 = 0x00010001
    V0X00010002 = 0x00010002
    V0X00010003 = 0x00010003
    V0X00010004 = 0x00010004
    V0X00010007 = 0x00010007


class StepType(IntEnum):
    CHARGE = 0x01
    DISCHARGE = 0x02
    REST = 0x03
    OCV = 0x04
    IMPEDANCE = 0x05
    END = 0x06
    CYCLE = 0x07
    LOOP = 0x08
    PATTERN = 0x09
    BALANCE = 0x0A


class StepMode(IntEnum):
    CCCV = 0x0101
    CC_CHARGE = 0x0201
    CC_DISCHARGE = 0x0202


# Combined step_type values used by ASSB/Ensol converter layout detection.
SCH_STEP_TYPE_REST = StepType.REST
SCH_STEP_TYPE_CCCV = StepMode.CCCV
SCH_STEP_TYPE_CC_CHARGE = StepMode.CC_CHARGE
SCH_STEP_TYPE_CC_DISCHARGE = StepMode.CC_DISCHARGE
SCH_STEP_TYPE_END = StepType.END
SCH_STEP_TYPE_CYCLE_MARKER = StepType.CYCLE
SCH_STEP_TYPE_LOOP = StepType.LOOP

SCH_STEP_TYPES = frozenset(
    {
        int(SCH_STEP_TYPE_REST),
        int(SCH_STEP_TYPE_CCCV),
        int(SCH_STEP_TYPE_CC_CHARGE),
        int(SCH_STEP_TYPE_CC_DISCHARGE),
        int(SCH_STEP_TYPE_END),
        int(SCH_STEP_TYPE_CYCLE_MARKER),
        int(SCH_STEP_TYPE_LOOP),
    }
)

DEFAULT_SCH_VERSION = int(SchFileVersion.V0X00010003)
DEFAULT_STEP_SIZE = 612
ALTERNATE_STEP_SIZE = 696

# CTS StepNo = SCH StepNo + 1
CTS_STEP_OFFSET = 1
