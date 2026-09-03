"""Gate C2 — step compiler covers mode, end, loop/goto, sampling, SOC."""

from __future__ import annotations

import struct

import pytest

from pne_scheduler.engine.compiler import (
    DEFAULT_RECORD_DV_MV,
    DEFAULT_RECORD_TIME_S,
    compile_step_warnings,
    compile_steps,
)
from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.ir.step_intent import StepIntent
from pne_scheduler.schema.ensol_v612 import (
    OFF_CAP_MODE,
    OFF_CURRENT_MA,
    OFF_CV_CUTOFF_MA,
    OFF_DOD_PERCENT,
    OFF_LOOP_COUNT,
    OFF_LOOP_GOTO_ENSOL,
    OFF_LOOP_GOTO_LEGACY,
    OFF_RECORD_DV_MV,
    OFF_RECORD_TIME_S,
    OFF_TIME_OR_REST_S,
    OFF_VOLT_OR_VLIM_MV,
    OFF_VOLTAGE_CUTOFF_MV,
)

CELL = CellProfile(nominal_capacity_mAh=80.0, v_max=4.2, v_min=2.5)


def _f(record: bytes, offset: int) -> float:
    return struct.unpack_from("<f", record, offset)[0]


def _u(record: bytes, offset: int) -> int:
    return struct.unpack_from("<I", record, offset)[0]


def test_compiler_charge_mode_cccv_vs_cc() -> None:
    cccv = compile_steps(
        [StepIntent(step_type="charge", mode="CCCV", c_rate=0.1, voltage_v=4.2)],
        CELL,
    )[0]
    cc = compile_steps(
        [StepIntent(step_type="charge", mode="CC", c_rate=0.1, voltage_v=4.2)],
        CELL,
    )[0]

    assert struct.unpack_from("<i", cccv, 8)[0] == 0x0101
    assert struct.unpack_from("<i", cc, 8)[0] == 0x0201
    assert _f(cccv, OFF_VOLT_OR_VLIM_MV) == pytest.approx(4200.0)
    assert _f(cccv, OFF_CURRENT_MA) == pytest.approx(8.0)


def test_compiler_writes_end_conditions_and_sampling_defaults() -> None:
    record = compile_steps(
        [
            StepIntent(
                step_type="charge",
                mode="CCCV",
                c_rate=1.0,
                voltage_v=4.2,
                cv_cutoff_c_rate=0.05,
                end_time_s=3600.0,
            )
        ],
        CELL,
    )[0]

    assert _f(record, OFF_CV_CUTOFF_MA) == pytest.approx(4.0)
    assert _f(record, OFF_TIME_OR_REST_S) == pytest.approx(3600.0)
    assert _f(record, OFF_RECORD_TIME_S) == pytest.approx(DEFAULT_RECORD_TIME_S)
    assert _f(record, OFF_RECORD_DV_MV) == pytest.approx(DEFAULT_RECORD_DV_MV)
    assert record[OFF_CAP_MODE] == 0x01


def test_compiler_absolute_current_and_sampling_overrides() -> None:
    record = compile_steps(
        [
            StepIntent(
                step_type="discharge",
                mode="CC",
                current_mA=17.0,
                end_voltage_v=2.5,
                record_time_s=120.0,
                record_dV_mV=5.0,
            )
        ],
        CELL,
    )[0]

    assert _f(record, OFF_CURRENT_MA) == pytest.approx(17.0)
    assert _f(record, OFF_VOLTAGE_CUTOFF_MV) == pytest.approx(2500.0)
    assert _f(record, OFF_RECORD_TIME_S) == pytest.approx(120.0)
    assert _f(record, OFF_RECORD_DV_MV) == pytest.approx(5.0)


def test_compiler_loop_writes_gate_b_and_ensol_goto_slots() -> None:
    record = compile_steps(
        [
            StepIntent(
                step_type="loop",
                loop_goto_step=7,
                loop_count=3,
            )
        ],
        CELL,
    )[0]

    assert struct.unpack_from("<i", record, 8)[0] == 8
    assert _u(record, OFF_LOOP_COUNT) == 3
    assert _u(record, OFF_LOOP_GOTO_LEGACY) == 7
    assert _u(record, OFF_LOOP_GOTO_ENSOL) == 7


def test_compiler_writes_soc_dod_percent() -> None:
    record = compile_steps(
        [
            StepIntent(
                step_type="discharge",
                mode="CC",
                c_rate=0.1,
                end_voltage_v=2.5,
                dod_percent=50.0,
            )
        ],
        CELL,
    )[0]
    assert _f(record, OFF_DOD_PERCENT) == pytest.approx(50.0)


def test_compiler_warns_when_dcr_ir_cannot_be_packed() -> None:
    intents = [
        StepIntent(
            step_type="discharge",
            mode="CC",
            c_rate=1.0,
            end_time_s=10.0,
            dcr_start_s=1.0,
            dcr_end_s=10.0,
        )
    ]
    warnings = compile_step_warnings(intents)
    assert any("dcr_start_s" in item for item in warnings)
    # Record still compiles; DCR bytes stay zero at Excel-claimed offsets.
    record = compile_steps(intents, CELL)[0]
    assert _f(record, 241) == pytest.approx(0.0)
    assert _f(record, 245) == pytest.approx(0.0)
