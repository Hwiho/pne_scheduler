import struct
from pathlib import Path
from zipfile import ZipFile

import pytest

from pne_scheduler.engine.compiler import compile_steps
from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.ir.step_intent import StepIntent
from pne_scheduler.io.sch_parser import _read_steps
from pne_scheduler.schema.v0x00010003_612 import (
    OFFSET_F_END_C,
    OFFSET_F_END_I,
    OFFSET_F_END_V,
    STEP_RECORD_SIZE,
)

ARCHIVE = (
    Path(__file__).resolve().parents[1]
    / "example"
    / "archives"
    / "9)Bimodal_SJ1300_6040_NCN_capacheck.zip"
)
CAPACHECK_NAME = "9)Bimodal_SJ1300_6040_NCN_capacheck.sch"


def test_end_condition_offsets_match_fixture_parser_layout() -> None:
    assert OFFSET_F_END_V == 28
    assert OFFSET_F_END_I == 32
    assert OFFSET_F_END_C == 36


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

    assert struct.unpack_from("<f", record, OFFSET_F_END_V)[0] == pytest.approx(4.2)
    assert struct.unpack_from("<f", record, OFFSET_F_END_I)[0] == pytest.approx(6.0)
    assert struct.unpack_from("<f", record, OFFSET_F_END_C)[0] == pytest.approx(30.0)
    assert struct.unpack_from("<f", record, 40)[0] == 0.0

    parsed = _read_steps(record, payload_offset=0, step_size=STEP_RECORD_SIZE)
    assert len(parsed) == 1
    assert parsed[0].f_end_v == pytest.approx(4.2)
    assert parsed[0].f_end_i == pytest.approx(6.0)
    assert parsed[0].f_end_c == pytest.approx(30.0)


def test_raw_612_fixture_distinguishes_end_voltage_and_current() -> None:
    with ZipFile(ARCHIVE) as archive:
        member = next(
            item for item in archive.infolist() if item.filename.endswith(CAPACHECK_NAME)
        )
        data = archive.read(member)

    steps = _read_steps(data, payload_offset=1760, step_size=612)
    charge = steps[3]
    discharge = steps[5]

    assert charge.step_type == "CCCV"
    assert charge.f_end_v == 0.0
    assert charge.f_end_i == pytest.approx(3.828)
    assert discharge.step_type == "CC_DCHG"
    assert discharge.f_end_v == pytest.approx(2500.0)
    assert discharge.f_end_i == 0.0
