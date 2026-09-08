"""Compiler stubs for OCV / Impedance / Pattern / Balance (no corpus samples)."""

from __future__ import annotations

import struct

import pytest

from pne_scheduler.engine.compiler import compile_step_warnings, compile_steps
from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.ir.step_intent import StepIntent
from pne_scheduler.schema.ensol_v612 import (
    OFF_CURRENT_MA,
    OFF_RECORD_TIME_S,
    OFF_TIME_OR_REST_S,
    OFF_VOLT_OR_VLIM_MV,
)
from pne_scheduler.schema.enums import (
    SCH_STEP_TYPE_BALANCE,
    SCH_STEP_TYPE_IMPEDANCE,
    SCH_STEP_TYPE_OCV,
    SCH_STEP_TYPE_PATTERN,
)

CELL = CellProfile(nominal_capacity_mAh=80.0, v_max=4.2, v_min=2.5)


def _f(record: bytes, offset: int) -> float:
    return struct.unpack_from("<f", record, offset)[0]


@pytest.mark.parametrize(
    ("step_type", "code"),
    [
        ("ocv", int(SCH_STEP_TYPE_OCV)),
        ("impedance", int(SCH_STEP_TYPE_IMPEDANCE)),
        ("pattern", int(SCH_STEP_TYPE_PATTERN)),
        ("balance", int(SCH_STEP_TYPE_BALANCE)),
    ],
)
def test_extended_step_types_pack_type_code_and_shared_prefix(
    step_type: str, code: int
) -> None:
    record = compile_steps(
        [
            StepIntent(
                step_type=step_type,  # type: ignore[arg-type]
                end_time_s=30.0,
                current_mA=1.5,
                voltage_v=3.7,
                record_time_s=5.0,
            )
        ],
        CELL,
    )[0]
    assert struct.unpack_from("<i", record, 8)[0] == code
    assert _f(record, OFF_TIME_OR_REST_S) == pytest.approx(30.0)
    assert _f(record, OFF_CURRENT_MA) == pytest.approx(1.5)
    assert _f(record, OFF_VOLT_OR_VLIM_MV) == pytest.approx(3700.0)
    assert _f(record, OFF_RECORD_TIME_S) == pytest.approx(5.0)


def test_extended_step_types_emit_corpus_warning() -> None:
    warnings = compile_step_warnings([StepIntent(step_type="ocv", end_time_s=10.0)])
    assert any("OCV/Impedance/Balance/Pattern" in item for item in warnings)
    assert any("STEP_TYPES_EXTENDED" in item for item in warnings)
