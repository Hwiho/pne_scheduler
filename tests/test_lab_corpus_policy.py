"""Tests for lab corpus zip policy and equipment registry."""

from __future__ import annotations

from pathlib import Path


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
    assert p16.corpus_zip == "PNE16.zip"
    assert p16.corpus_zip_allowed_for_analysis is True
    assert p16.ctspro_build == "CYCC-1004-S01-R004-N01"
    assert p16.ctspro_build_source == "ctsmonpro_titlebar"
    assert any(row.step_size == 696 for row in p16.layouts_confirmed)
    assert any(row.file_version == "0x00010005" and row.step_size == 720 for row in p16.layouts_observed)

    p15 = get_unit_equipment_profile("PNE15")
    assert p15 is not None
    assert p15.corpus_zip == "PNE15.zip"
    assert p15.corpus_zip_allowed_for_analysis is True
    assert p15.rating is not None and p15.rating.rating_mA == 6000
    assert p15.ctspro_build == "CYCC-1004-S01-R004-N01"
    assert any(row.step_size == 696 and row.dominant for row in p15.layouts_observed)
    assert any(row.file_version == "0x00010005" and row.step_size == 720 for row in p15.layouts_observed)

    p17 = get_unit_equipment_profile("PNE17")
    assert p17 is not None
    assert p17.corpus_zip == "PNE17.zip"
    assert p17.corpus_zip_allowed_for_analysis is False
    assert p17.rating is not None and p17.rating.rating_mA == 6000
    assert p17.ctspro_build == "CYCC-1006-S01-R006-N04"
    assert p17.layouts_observed == ()

    p18 = get_unit_equipment_profile("PNE18")
    assert p18 is not None
    assert p18.corpus_zip == "PNE18.zip"
    assert p18.corpus_zip_allowed_for_analysis is True
    assert p18.rating is not None and p18.rating.rating_mA == 6000
    assert p18.ctspro_build == "CYCC-1006-S01-R006-N04"
    assert p18.ctspro_build_source == "ctsmonpro_titlebar"
    assert any(row.step_size == 612 and row.dominant for row in p18.layouts_observed)
    assert all(row.step_size == 612 for row in p18.layouts_observed)

    p19 = get_unit_equipment_profile("PNE19")
    assert p19 is not None
    assert p19.corpus_zip == "PNE19.zip"
    assert p19.corpus_zip_allowed_for_analysis is True
    assert p19.rating is not None and p19.rating.rating_mA == 6000
    assert p19.ctspro_build == "CYCN-P1107-S01-8001-N03"
    assert p19.ctspro_build_source == "ctsmonpro_titlebar"
    assert any(row.file_version == "0x00010004" and row.step_size == 696 and row.dominant for row in p19.layouts_observed)
    assert not any(row.step_size == 720 for row in p19.layouts_observed)

    p20 = get_unit_equipment_profile("PNE20")
    assert p20 is not None
    assert p20.corpus_zip == "PNE20.zip"
    assert p20.corpus_zip_allowed_for_analysis is True
    assert p20.rating is not None and p20.rating.rating_mA == 6000
    assert p20.ctspro_build == "CYCSA-P1107-S01-R001-N013"
    assert p20.ctspro_build_source == "ctsmonpro_titlebar"
    assert any(row.file_version == "0x00010004" and row.step_size == 696 and row.dominant for row in p20.layouts_observed)
    assert not any(row.step_size == 720 for row in p20.layouts_observed)


def test_layout_resolver_includes_unit_metadata() -> None:
    layout = get_sch_layout_for_unit(0x00010003, pne_unit="PNE02")
    assert layout is not None
    assert layout.pne_unit == "PNE02"
    assert layout.step_size == 612
    assert layout.payload_offset == 1760

    layout_v5 = get_sch_layout_for_unit(0x00010005, pne_unit="PNE15")
    assert layout_v5 is not None
    assert layout_v5.payload_offset == 1868
    assert layout_v5.step_size == 720
    assert layout_v5.pne_unit == "PNE15"

    layout_p16 = get_sch_layout_for_unit(0x00010004, pne_unit="PNE16")
    assert layout_p16 is not None
    assert layout_p16.payload_offset == 1844
    assert layout_p16.step_size == 696
    assert layout_p16.pne_unit == "PNE16"

    layout_p18 = get_sch_layout_for_unit(0x00010003, pne_unit="PNE18")
    assert layout_p18 is not None
    assert layout_p18.payload_offset == 1760
    assert layout_p18.step_size == 612
    assert layout_p18.pne_unit == "PNE18"

    layout_p19 = get_sch_layout_for_unit(0x00010004, pne_unit="PNE19")
    assert layout_p19 is not None
    assert layout_p19.payload_offset == 1844
    assert layout_p19.step_size == 696
    assert layout_p19.pne_unit == "PNE19"

    layout_p20 = get_sch_layout_for_unit(0x00010004, pne_unit="PNE20")
    assert layout_p20 is not None
    assert layout_p20.payload_offset == 1844
    assert layout_p20.step_size == 696
    assert layout_p20.pne_unit == "PNE20"
