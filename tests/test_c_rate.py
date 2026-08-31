from __future__ import annotations

import pytest

from pne_scheduler.engine.c_rate import (
    FAST_CHARGE_MIN_C_RATE,
    format_c_rate_label,
    is_fast_charge_c_rate,
    snap_c_rate,
    current_mA_from_c_rate,
)
from pne_scheduler.ir import CellProfile


def test_current_from_one_c() -> None:
    cell = CellProfile(nominal_capacity_mAh=80.0, v_max=4.2, v_min=2.5)
    assert current_mA_from_c_rate(1.0, cell) == pytest.approx(80.0)


def test_current_from_c_third() -> None:
    cell = CellProfile(nominal_capacity_mAh=60.0, v_max=4.2, v_min=2.5)
    assert current_mA_from_c_rate(1.0 / 3.0, cell) == pytest.approx(20.0)


@pytest.mark.parametrize(
    ("raw", "label"),
    [
        (0.1, "0.1C"),
        (0.2, "0.2C"),
        (1.0 / 3.0, "C/3"),
        (0.5, "C/2"),
        (1.0, "1C"),
        (1.5, "1.5C"),
        (2.5, "2.5C"),
        (3.0, "3C"),
        (6.0, "6C"),
    ],
)
def test_snap_standard_presets(raw: float, label: str) -> None:
    result = snap_c_rate(raw)
    assert result.preset is not None
    assert result.label == label
    assert result.snapped_value == pytest.approx(raw, rel=1e-6)


def test_snap_near_preset_within_tolerance() -> None:
    result = snap_c_rate(0.98)
    assert result.label == "1C"
    assert result.preset is not None


def test_snap_off_preset_shows_approx_label() -> None:
    result = snap_c_rate(0.72)
    assert result.preset is None
    assert result.label == "~0.72C"


@pytest.mark.parametrize(
    ("c_rate", "expected"),
    [
        (2.5, False),
        (2.51, True),
        (3.0, True),
        (1.0, False),
    ],
)
def test_fast_charge_threshold(c_rate: float, expected: bool) -> None:
    assert is_fast_charge_c_rate(c_rate) is expected
    snap = snap_c_rate(c_rate)
    assert snap.is_fast_charge is expected


def test_format_c_rate_label() -> None:
    assert format_c_rate_label(1.0 / 3.0) == "C/3"
    assert format_c_rate_label(0.72).startswith("~")
