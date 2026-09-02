"""Gate B0 unit contract — Ensol-validated mV/mA layout."""

from __future__ import annotations

import struct
from pathlib import Path
from zipfile import ZipFile

import pytest

from pne_scheduler.engine.compiler import compile_steps
from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.ir.step_intent import StepIntent
from pne_scheduler.io.sch_parser import _read_steps
from pne_scheduler.schema.ensol_v612 import OFF_CURRENT_MA, OFF_VOLTAGE_CUTOFF_MV
from pne_scheduler.schema.v0x00010003_612 import STEP_RECORD_SIZE

ARCHIVE = (
    Path(__file__).resolve().parents[1]
    / "example"
    / "archives"
    / "9)Bimodal_SJ1300_6040_NCN_capacheck.zip"
)
CAPACHECK_NAME = "9)Bimodal_SJ1300_6040_NCN_capacheck.sch"


def _capacheck_discharge_end_voltage_mV() -> float:
    with ZipFile(ARCHIVE) as archive:
        member = next(
            item for item in archive.infolist() if item.filename.endswith(CAPACHECK_NAME)
        )
        data = archive.read(member)
    steps = _read_steps(data, payload_offset=1760, step_size=612)
    discharge = steps[5]
    assert discharge.step_type == "CC_DCHG"
    return discharge.f_end_v


def test_fixture_corpus_end_voltage_uses_millivolt_scale() -> None:
    assert _capacheck_discharge_end_voltage_mV() == pytest.approx(2500.0)


def test_compiler_writes_discharge_end_voltage_in_millivolts() -> None:
    cell = CellProfile(nominal_capacity_mAh=120.0, v_max=4.2, v_min=2.5)
    intent = StepIntent(
        step_type="discharge",
        mode="CC",
        c_rate=0.5,
        end_voltage_v=2.5,
    )
    record = compile_steps([intent], cell)[0]
    written = struct.unpack_from("<f", record, OFF_VOLTAGE_CUTOFF_MV)[0]
    assert written == pytest.approx(2500.0)


def test_compiler_current_is_written_at_offset_16_mA() -> None:
    cell = CellProfile(nominal_capacity_mAh=80.0, v_max=4.2, v_min=2.5)
    intent = StepIntent(step_type="charge", mode="CCCV", c_rate=1.0, voltage_v=4.2)
    record = compile_steps([intent], cell)[0]
    assert struct.unpack_from("<f", record, OFF_CURRENT_MA)[0] == pytest.approx(80.0)
