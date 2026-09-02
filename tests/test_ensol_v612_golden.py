"""Ensol v612 offset map validated against golden capacheck (PNE02)."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from pne_scheduler.schema.ensol_v612 import (
    OFF_CURRENT_MA,
    OFF_CV_CUTOFF_MA,
    OFF_RECORD_DV_MV,
    OFF_RECORD_TIME_S,
    OFF_TIME_OR_REST_S,
    OFF_VOLT_OR_VLIM_MV,
    OFF_VOLTAGE_CUTOFF_MV,
)

CAPACHECK = (
    Path(__file__).resolve().parents[1]
    / "example"
    / "fixtures"
    / "capacheck_zip"
    / "9)Bimodal_SJ1300_6040_NCN_capacheck.sch"
)
PAYLOAD = 1760
STEP_SIZE = 612


def _step(data: bytes, index: int) -> memoryview:
    base = PAYLOAD + index * STEP_SIZE
    return memoryview(data)[base : base + STEP_SIZE]


def test_golden_capacheck_cccv_step_matches_ensol_layout() -> None:
    data = CAPACHECK.read_bytes()
    step = _step(data, 3)  # step_no 4 CCCV
    assert struct.unpack_from("<i", step, 0)[0] == 4
    assert struct.unpack_from("<i", step, 8)[0] & 0xFFFF == 0x0101
    assert struct.unpack_from("<f", step, OFF_VOLT_OR_VLIM_MV)[0] == pytest.approx(4200.0)
    assert struct.unpack_from("<f", step, OFF_CURRENT_MA)[0] == pytest.approx(7.655, rel=1e-3)
    assert struct.unpack_from("<f", step, OFF_TIME_OR_REST_S)[0] == pytest.approx(21600.0)
    assert struct.unpack_from("<f", step, OFF_CV_CUTOFF_MA)[0] == pytest.approx(3.828, rel=1e-3)
    assert struct.unpack_from("<f", step, OFF_RECORD_DV_MV)[0] == pytest.approx(10.0)
    assert struct.unpack_from("<f", step, OFF_RECORD_TIME_S)[0] == pytest.approx(60.0)


def test_golden_capacheck_ccdi_step_matches_ensol_layout() -> None:
    data = CAPACHECK.read_bytes()
    step = _step(data, 5)  # step_no 6 CCDi
    assert struct.unpack_from("<i", step, 0)[0] == 6
    assert struct.unpack_from("<i", step, 8)[0] & 0xFFFF == 0x0202
    assert struct.unpack_from("<f", step, OFF_VOLT_OR_VLIM_MV)[0] == pytest.approx(2000.0)
    assert struct.unpack_from("<f", step, OFF_CURRENT_MA)[0] == pytest.approx(7.655, rel=1e-3)
    assert struct.unpack_from("<f", step, OFF_VOLTAGE_CUTOFF_MV)[0] == pytest.approx(2500.0)
    assert step[496] == 1


def test_parser_reads_current_from_offset_16() -> None:
    from pne_scheduler.io.sch_parser import parse_schedule_file

    doc = parse_schedule_file(CAPACHECK)
    cccv = next(s for s in doc.steps if s.step_type == "CCCV")
    assert cccv.f_iref == pytest.approx(7.655, rel=1e-3)
