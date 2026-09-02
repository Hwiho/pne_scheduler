"""B4 semantic golden tests — Ensol v612 field values on locked fixtures."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from pne_scheduler.io.sch_binary import read_sch_binary
from pne_scheduler.schema.ensol_v612 import (
    OFF_CAP_MODE,
    OFF_CURRENT_MA,
    OFF_CV_CUTOFF_MA,
    OFF_STEP_TYPE,
    OFF_TIME_OR_REST_S,
    OFF_VOLT_OR_VLIM_MV,
    OFF_VOLTAGE_CUTOFF_MV,
)
from pne_scheduler.schema.enums import (
    SCH_STEP_TYPE_CC_CHARGE,
    SCH_STEP_TYPE_CC_DISCHARGE,
    SCH_STEP_TYPE_CCCV,
)

ROOT = Path(__file__).resolve().parents[1]
EXPECTATIONS_PATH = ROOT / "planning" / "GOLDEN_SEMANTIC_EXPECTATIONS.json"
FIXTURE_ROOT = ROOT / "example" / "fixtures"

_TYPE_BY_NAME = {
    "CCCV": int(SCH_STEP_TYPE_CCCV),
    "CC_CHG": int(SCH_STEP_TYPE_CC_CHARGE),
    "CC_DCHG": int(SCH_STEP_TYPE_CC_DISCHARGE),
}


def _load_expectations() -> dict:
    return json.loads(EXPECTATIONS_PATH.read_text(encoding="utf-8"))


def _read_f32(record: bytes, offset: int) -> float:
    return struct.unpack_from("<f", record, offset)[0]


@pytest.fixture(scope="module")
def expectations() -> dict:
    payload = _load_expectations()
    assert payload["schema"] == "pne_scheduler.golden_semantic/v1"
    assert len(payload["fixtures"]) == 7
    return payload


@pytest.mark.parametrize(
    "fixture_id",
    [item["id"] for item in json.loads(EXPECTATIONS_PATH.read_text(encoding="utf-8"))["fixtures"]],
)
def test_golden_semantic_step_values(expectations: dict, fixture_id: str) -> None:
    entry = next(item for item in expectations["fixtures"] if item["id"] == fixture_id)
    path = FIXTURE_ROOT / Path(entry["path"])
    doc = read_sch_binary(path)
    steps_by_no = {step.step_no: step for step in doc.steps}

    for check in entry["checks"]:
        step = steps_by_no[check["step_no"]]
        expected_type = _TYPE_BY_NAME[check["step_type"]]
        assert step.step_type_code == expected_type
        record = step.record

        assert _read_f32(record, OFF_VOLT_OR_VLIM_MV) == pytest.approx(
            check["volt_or_vlim_mV"], rel=1e-4
        )
        assert _read_f32(record, OFF_CURRENT_MA) == pytest.approx(check["current_mA"], rel=0.02)
        assert _read_f32(record, OFF_TIME_OR_REST_S) == pytest.approx(
            check["time_or_rest_s"], rel=1e-4
        )

        if "voltage_cutoff_mV" in check:
            assert _read_f32(record, OFF_VOLTAGE_CUTOFF_MV) == pytest.approx(
                check["voltage_cutoff_mV"], rel=1e-4
            )
        if "cv_cutoff_mA" in check:
            assert _read_f32(record, OFF_CV_CUTOFF_MA) == pytest.approx(
                check["cv_cutoff_mA"], rel=0.02
            )
        if "cap_mode_byte_496" in check:
            assert record[OFF_CAP_MODE] == check["cap_mode_byte_496"]


def test_parser_matches_semantic_current_for_capacheck_b0(expectations: dict) -> None:
    from pne_scheduler.io.sch_parser import parse_schedule_file

    entry = next(
        item for item in expectations["fixtures"] if item["id"] == "golden-capacheck-612-b0"
    )
    path = FIXTURE_ROOT / Path(entry["path"])
    doc = parse_schedule_file(path)
    cccv = next(s for s in doc.steps if s.step_type == "CCCV")
    assert cccv.f_iref == pytest.approx(7.655, rel=0.01)
    assert cccv.f_vref == pytest.approx(4200.0, rel=1e-4)
