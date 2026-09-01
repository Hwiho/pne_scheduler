"""ASSB vendored constants vs pne_scheduler schema/fields.py parity."""

from __future__ import annotations

from pathlib import Path

import pytest

from pne_scheduler.io.sch_parser import parse_schedule_file
from pne_scheduler.vendor.assb_sch import (
    ASSB_ONLY_FIELDS,
    DOCUMENTED_DIVERGENCES,
    SHARED_OFFSET_PAIRS,
    assb_offset_table,
    parse_sch_cycle_map_bytes,
    pne_scheduler_offset_table,
)

HPPC_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "example"
    / "fixtures"
    / "hppc"
    / "HPPC_Full range.sch"
)


@pytest.mark.parametrize(
    "pair",
    SHARED_OFFSET_PAIRS,
    ids=lambda pair: f"{pair.assb_name}->{pair.pne_name}",
)
def test_shared_assb_and_pne_scheduler_offsets_match(pair) -> None:
    assert pair.assb_offset == pair.pne_offset


@pytest.mark.parametrize(
    "divergence",
    DOCUMENTED_DIVERGENCES,
    ids=lambda item: item.assb_name,
)
def test_documented_offset_divergences_are_stable(divergence) -> None:
    assert divergence.assb_offset != divergence.pne_offset
    assert assb_offset_table()[divergence.assb_name] == divergence.assb_offset
    assert pne_scheduler_offset_table()[divergence.pne_name] == divergence.pne_offset


def test_assb_only_fields_are_documented() -> None:
    pne_offsets = set(pne_scheduler_offset_table().values())
    for name, offset in ASSB_ONLY_FIELDS.items():
        assert name in assb_offset_table()
        assert offset not in pne_offsets


def test_offset_tables_cover_all_assb_condition_fields() -> None:
    table = assb_offset_table()
    assert table["fEndC"] == 36
    assert table["nGotoStepID"] == 84
    assert table["fSocRate"] == 384
    assert "nLoopInfoEndSocGoto" in table


def test_vendored_assb_parser_reads_hppc_fixture() -> None:
    assert HPPC_FIXTURE.is_file()
    data = HPPC_FIXTURE.read_bytes()
    cycle_map = parse_sch_cycle_map_bytes(data, source_path=HPPC_FIXTURE)
    assert cycle_map is not None
    assert cycle_map.step_count == 62
    assert cycle_map.step_size == 612
    assert cycle_map.header_version == 0x00010002 or cycle_map.header_version == 0x10002


def test_vendored_assb_parser_matches_native_viewer_layout() -> None:
    assert HPPC_FIXTURE.is_file()
    data = HPPC_FIXTURE.read_bytes()
    assb_map = parse_sch_cycle_map_bytes(data, source_path=HPPC_FIXTURE)
    native_doc = parse_schedule_file(HPPC_FIXTURE)
    assert assb_map is not None
    assert assb_map.payload_offset == native_doc.payload_offset
    assert assb_map.step_size == native_doc.step_size
    assert assb_map.step_count == len(native_doc.steps)
