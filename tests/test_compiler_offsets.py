import struct
from pathlib import Path
from zipfile import ZipFile

import pytest

from pne_scheduler.engine.compiler import compile_steps
from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.ir.step_intent import StepIntent
from pne_scheduler.io.sch_parser import _read_steps
from pne_scheduler.schema.ensol_v612 import (
    OFF_CURRENT_MA,
    OFF_CV_CUTOFF_MA,
    OFF_TIME_OR_REST_S,
    OFF_VOLT_OR_VLIM_MV,
    OFF_VOLTAGE_CUTOFF_MV,
)
from pne_scheduler.schema.v0x00010003_612 import STEP_RECORD_SIZE

ARCHIVE = (
    Path(__file__).resolve().parents[1]
    / "example"
    / "archives"
    / "9)Bimodal_SJ1300_6040_NCN_capacheck.zip"
)
CAPACHECK_NAME = "9)Bimodal_SJ1300_6040_NCN_capacheck.sch"


def test_end_condition_offsets_match_fixture_parser_layout() -> None:
    assert OFF_VOLTAGE_CUTOFF_MV == 28
    assert OFF_CV_CUTOFF_MA == 32


def test_compiled_end_conditions_use_ensol_millivolt_and_milliampere_layout() -> None:
    cell = CellProfile(
        nominal_capacity_mAh=120.0,
        v_max=4.2,
        v_min=2.5,
    )
    intent = StepIntent(
        step_type="discharge",
        mode="CC",
        c_rate=0.5,
        end_voltage_v=2.5,
    )

    record = compile_steps([intent], cell)[0]

    assert struct.unpack_from("<f", record, OFF_VOLT_OR_VLIM_MV)[0] == pytest.approx(2000.0)
    assert struct.unpack_from("<f", record, OFF_CURRENT_MA)[0] == pytest.approx(60.0)
    assert struct.unpack_from("<f", record, OFF_VOLTAGE_CUTOFF_MV)[0] == pytest.approx(2500.0)

    parsed = _read_steps(record, payload_offset=0, step_size=STEP_RECORD_SIZE)
    assert len(parsed) == 1
    assert parsed[0].f_end_v == pytest.approx(2500.0)
    assert parsed[0].current_mA == pytest.approx(60.0)


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
