"""Tests for lab corpus zip policy and equipment registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from pne_scheduler.schema.equipment_registry import get_unit_equipment_profile
from pne_scheduler.schema.lab_corpus import (
    is_unit_numbered_zip,
    unit_id_from_zip,
    validate_unit_corpus_zip,
)
from pne_scheduler.schema.layouts import get_sch_layout_for_unit


def test_unit_zip_naming_policy() -> None:
    assert is_unit_numbered_zip("PNE02.zip")
    assert is_unit_numbered_zip("pne22.ZIP")
    assert not is_unit_numbered_zip("capacheck_zip.zip")
    assert not is_unit_numbered_zip("Ensol_sch_maker.zip")
    assert unit_id_from_zip("PNE05.zip") == "PNE05"


def test_validate_unit_corpus_zip_mismatch() -> None:
    err = validate_unit_corpus_zip("PNE02", Path("PNE22.zip"))
    assert err is not None


def test_registry_cts_and_layouts() -> None:
    p02 = get_unit_equipment_profile("PNE02")
    assert p02 is not None
    assert p02.ctspro_build == "CYCC-1004-S01-R004-N01"
    assert p02.corpus_zip == "PNE02.zip"
    assert any(row.step_size == 612 for row in p02.layouts_observed)

    p16 = get_unit_equipment_profile("PNE16")
    assert p16 is not None
    assert p16.corpus_zip_allowed_for_analysis is False
    assert any(row.step_size == 696 for row in p16.layouts_confirmed)


def test_layout_resolver_includes_unit_metadata() -> None:
    layout = get_sch_layout_for_unit(0x00010003, pne_unit="PNE02")
    assert layout is not None
    assert layout.pne_unit == "PNE02"
    assert layout.step_size == 612
    assert layout.payload_offset == 1760
