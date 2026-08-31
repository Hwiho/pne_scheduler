import pytest

from pne_scheduler.stack.footprint import infer_footprint_from_filename
from pne_scheduler.stack.silicon_codes import is_silicon_combo_code


@pytest.mark.parametrize(
    "code",
    ["6040", "6043", "6055", "6535", "7030"],
)
def test_silicon_combo_codes_recognized(code: str) -> None:
    assert is_silicon_combo_code(code)


@pytest.mark.parametrize(
    "code",
    ["1818", "3350", "70150"],
)
def test_footprint_codes_not_silicon_combo(code: str) -> None:
    assert not is_silicon_combo_code(code)


def test_6040_in_filename_not_parsed_as_footprint() -> None:
    fp = infer_footprint_from_filename("9)Bimodal_SJ1300_6040_NCN_capacheck.sch")
    assert fp is None


def test_6535_in_filename_not_parsed_as_footprint() -> None:
    fp = infer_footprint_from_filename("test_SJ1300_6535_cycle.sch")
    assert fp is None
