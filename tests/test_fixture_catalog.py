from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from pne_scheduler.io.sch_binary import read_sch_binary
from pne_scheduler.tools.build_fixture_catalog import build_catalog

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "example" / "fixtures"
CATALOG_PATH = FIXTURE_ROOT / "catalog.json"


def _load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def test_fixture_catalog_is_complete_and_deterministic() -> None:
    catalog = _load_catalog()
    actual_paths = {
        path.relative_to(FIXTURE_ROOT).as_posix()
        for path in FIXTURE_ROOT.rglob("*.sch")
    }
    catalog_paths = {entry["path"] for entry in catalog["fixtures"]}

    assert catalog["schema"] == "pne_scheduler.fixture_catalog/v1"
    assert catalog["fixture_count"] == 102
    assert catalog_paths == actual_paths
    assert build_catalog() == catalog


def test_all_catalog_layouts_match_binary_parser() -> None:
    catalog = _load_catalog()
    layout_counts = Counter()

    for entry in catalog["fixtures"]:
        path = FIXTURE_ROOT / entry["path"]
        data = path.read_bytes()
        document = read_sch_binary(path)
        expected = entry["layout"]

        assert hashlib.sha256(data).hexdigest() == entry["sha256"]
        assert len(data) == entry["size"]
        assert document.sch_version == int(expected["version"], 16)
        assert document.payload_offset == expected["payload_offset"]
        assert document.step_size == expected["step_size"]
        assert document.step_count == expected["step_count"]
        assert len(data) == document.payload_offset + document.step_count * document.step_size
        assert document.steps[-1].is_end

        layout_counts[
            (
                expected["version"],
                expected["payload_offset"],
                expected["step_size"],
            )
        ] += 1

    assert layout_counts == {
        ("0x00010002", 1632, 612): 6,
        ("0x00010003", 1760, 612): 4,
        ("0x00010004", 1844, 696): 92,
    }


def test_equipment_provenance_is_fixture_scoped() -> None:
    catalog = _load_catalog()
    assert "only to these exact checked-in fixtures" in catalog["scope"]
    formation_routing = catalog["operational_context"]["formation"]
    assert formation_routing["current_equipment"] == ["PNE02", "PNE21", "PNE22"]
    assert formation_routing["exclusive"] is False
    assert "not fixture provenance" in formation_routing["note"]

    qpeed_entries = [
        entry for entry in catalog["fixtures"] if "qpeed" in entry["path"].casefold()
    ]
    assert len(qpeed_entries) == 2
    assert {
        entry["equipment_provenance"]["equipment"] for entry in qpeed_entries
    } == {"PNE02"}

    current_pne16_confirmed = [
        entry
        for entry in catalog["fixtures"]
        if entry["equipment_provenance"]["equipment"] == "PNE16"
        and entry["equipment_provenance"]["confidence"] == "confirmed"
    ]
    assert current_pne16_confirmed
    assert all(
        "1ah" in entry["path"].casefold()
        or (
            "qc" in entry["path"].casefold()
            and (
                "1n1q" in entry["path"].casefold()
                or "cycle" in entry["path"].casefold()
            )
        )
        for entry in current_pne16_confirmed
    )

    assigned_equipment = {
        entry["equipment_provenance"]["equipment"] for entry in catalog["fixtures"]
    }
    assert "PNE21" not in assigned_equipment
    assert "PNE22" not in assigned_equipment
