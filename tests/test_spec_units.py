from __future__ import annotations

import pytest

from pne_scheduler.spec import units


@pytest.mark.parametrize(
    "text,expected",
    [
        ("600", 600.0),
        ("600s", 600.0),
        ("30분", 1800.0),
        ("1시간 30분", 5400.0),
        ("1h30m", 5400.0),
        ("2일", 172800.0),
    ],
)
def test_duration_accepts_the_shapes_users_type(text: str, expected: float) -> None:
    assert units.parse_duration_s(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "10x"])
def test_duration_rejects_unreadable_text(text: str) -> None:
    with pytest.raises(units.UnitParseError):
        units.parse_duration_s(text)


@pytest.mark.parametrize(
    "text,expected",
    [("0.5", 0.5), ("0.5C", 0.5), ("C/3", 1.0 / 3.0), ("1.5 c", 1.5)],
)
def test_c_rate_accepts_lab_notation(text: str, expected: float) -> None:
    assert units.parse_c_rate(text) == pytest.approx(expected)


def test_c_rate_round_trips_through_its_label() -> None:
    for value in (0.1, 1.0 / 3.0, 0.5, 1.0, 1.5):
        assert units.parse_c_rate(units.format_c_rate(value)) == pytest.approx(value, rel=1e-3)


def test_duration_input_round_trips() -> None:
    for seconds in (1.0, 600.0, 1800.0, 3600.0, 57600.0):
        assert units.parse_duration_s(units.format_duration_input(seconds)) == seconds


def test_zero_c_rate_formats_instead_of_raising() -> None:
    assert units.format_c_rate(0.0) == "0C"


def test_current_view_reports_headroom() -> None:
    view = units.CurrentView(18.0, 432.0, 500.0)

    assert not view.exceeds_limit
    assert "86%" in view.describe()
    assert units.CurrentView(18.0, 600.0, 500.0).exceeds_limit
