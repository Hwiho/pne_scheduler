import struct

import pytest

from pne_scheduler.engine.compiler import compile_steps
from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.ir.step_intent import StepIntent
from pne_scheduler.io.sch_parser import _read_steps
from pne_scheduler.schema.v0x00010003_612 import (
    OFFSET_F_END_C,
    OFFSET_F_END_CV_TIME,
    OFFSET_F_END_I,
    OFFSET_F_END_V,
    STEP_RECORD_SIZE,
)


def test_end_condition_offsets_match_fixture_parser_layout() -> None:
    assert OFFSET_F_END_CV_TIME == 28
    assert OFFSET_F_END_V == 32
    assert OFFSET_F_END_I == 36
    assert OFFSET_F_END_C == 40


def test_compiled_end_conditions_are_read_at_canonical_offsets() -> None:
    cell = CellProfile(
        nominal_capacity_mAh=120.0,
        v_max=4.2,
        v_min=2.5,
    )
    intent = StepIntent(
        step_type="charge",
        mode="CCCV",
        c_rate=0.5,
        cv_cutoff_c_rate=0.05,
        end_voltage_v=4.2,
        end_capacity_fraction=0.25,
    )

    record = compile_steps([intent], cell)[0]

    assert struct.unpack_from("<f", record, OFFSET_F_END_CV_TIME)[0] == 0.0
    assert struct.unpack_from("<f", record, OFFSET_F_END_V)[0] == pytest.approx(4.2)
    assert struct.unpack_from("<f", record, OFFSET_F_END_I)[0] == pytest.approx(6.0)
    assert struct.unpack_from("<f", record, OFFSET_F_END_C)[0] == pytest.approx(30.0)

    parsed = _read_steps(record, payload_offset=0, step_size=STEP_RECORD_SIZE)
    assert len(parsed) == 1
    assert parsed[0].f_end_v == pytest.approx(4.2)
    assert parsed[0].f_end_i == pytest.approx(6.0)
    assert parsed[0].f_end_c == pytest.approx(30.0)
