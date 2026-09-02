"""Tests for Ensol-adopted .sch current rescaler."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from pne_scheduler.io.current_rescaler import (
    canonical_c_rate_info,
    collect_current_fields,
    scale_current_fields,
)
from pne_scheduler.schema.ensol_v612 import OFF_CURRENT_MA, OFF_CV_CUTOFF_MA

CAPACHECK = (
    Path(__file__).resolve().parents[1]
    / "example"
    / "fixtures"
    / "capacheck_zip"
    / "9)Bimodal_SJ1300_6040_NCN_capacheck.sch"
)


def test_canonical_c_rate_recognizes_one_third() -> None:
    info = canonical_c_rate_info(33.333, 100.0)
    assert info["value"] == pytest.approx(1.0 / 3.0)
    assert info["label"] == "1/3"


def test_scale_doubles_current_when_capacity_doubles() -> None:
    src = CAPACHECK.read_bytes()
    old_q = 76.55
    new_q = 153.1
    out, summary = scale_current_fields(src, old_q, new_q)
    assert summary["factor"] == pytest.approx(2.0)

    first = summary["changes"][0]
    assert first["new"] == pytest.approx(first["old"] * 2.0, rel=0.01)

    # First CCCV step current in output should match scaled value
    header = summary["header_size"]
    block = memoryview(out)[header : header + 612]
    step4_base = header + 3 * 612
    step4 = memoryview(out)[step4_base : step4_base + 612]
    assert struct.unpack_from("<f", step4, OFF_CURRENT_MA)[0] == pytest.approx(
        first["new"], rel=1e-4
    )


def test_collect_current_fields_on_capacheck() -> None:
    src = CAPACHECK.read_bytes()
    summary = collect_current_fields(src, capacity_mAh=76.55)
    currents = [row for row in summary["fields"] if row.field == "current_mA"]
    assert len(currents) >= 2
    assert currents[0].value == pytest.approx(7.655, rel=0.01)
