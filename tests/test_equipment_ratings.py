"""Tests for official equipment current ratings."""

from __future__ import annotations

from pne_scheduler.schema.equipment import get_equipment_rating, normalize_pne_unit


def test_normalize_pne_unit_aliases() -> None:
    assert normalize_pne_unit("PNE2") == "PNE02"
    assert normalize_pne_unit("PNE 02") == "PNE02"
    assert normalize_pne_unit("pne22") == "PNE22"


def test_official_ratings_user_guideline() -> None:
    assert get_equipment_rating("PNE02").rating_mA == 500
    assert get_equipment_rating("PNE04").rating_mA == 500
    assert get_equipment_rating("PNE06").rating_mA == 500
    assert get_equipment_rating("PNE08").rating_mA == 500
    assert get_equipment_rating("PNE09").rating_mA == 500
    assert get_equipment_rating("PNE10").rating_mA == 500
    assert get_equipment_rating("PNE11").rating_mA == 500
    assert get_equipment_rating("PNE16").rating_mA == 6000
    assert get_equipment_rating("PNE22").rating_mA == 100
    assert get_equipment_rating("PNE01").rating_mA == 500
    assert get_equipment_rating("PNE33").rating_mA == 10000
    assert get_equipment_rating("PNE12").rating_mA == 20000


def test_unlisted_corpus_unit() -> None:
    assert get_equipment_rating("PNE99") is None
