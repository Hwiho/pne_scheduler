from __future__ import annotations

import json
from pathlib import Path

import pytest

from pne_scheduler.classify import QpeedVariant, classify_schedule_filename
from pne_scheduler.io.sch_binary import read_sch_binary
from pne_scheduler.tests.golden_fixtures import (
    LOCKED_PATH,
    load_locked_golden_fixtures,
    locked_fixture_paths,
)

ROOT = Path(__file__).resolve().parents[1]
DEFERRED_SOC_SETTING = (
    ROOT
    / "example"
    / "fixtures"
    / "capacheck_zip"
    / "07100766_260713_Set9_QPEED_SOC_setting_BM_SJ1300_6040_C_NCN.sch"
)
FM_ONLY_FORMATION = (
    ROOT / "example" / "fixtures" / "capacheck_zip" / "3.BM_C1%_FM.sch"
)


def test_locked_golden_manifest_exists() -> None:
    payload = load_locked_golden_fixtures()
    assert payload["schema"] == "pne_scheduler.golden_fixtures_locked/v1"
    assert len(payload["selected"]) == 7


@pytest.mark.parametrize("path", locked_fixture_paths(), ids=lambda p: p.name)
def test_locked_golden_fixtures_exist_on_disk(path: Path) -> None:
    assert path.is_file(), f"missing golden fixture: {path}"


@pytest.mark.parametrize("path", locked_fixture_paths(), ids=lambda p: p.name)
def test_locked_golden_fixtures_parse(path: Path) -> None:
    doc = read_sch_binary(path)
    assert doc.step_count > 0
    assert doc.step_size in (612, 696)


def test_locked_manifest_paths_match_step_counts() -> None:
    payload = load_locked_golden_fixtures()
    for item in payload["selected"]:
        path = ROOT / "example" / "fixtures" / Path(item["path"])
        doc = read_sch_binary(path)
        assert doc.step_count == item["step_count"]


def test_user_domain_rules_formation_vs_capacheck() -> None:
    fm_match = classify_schedule_filename(FM_ONLY_FORMATION)
    assert fm_match.category.value == "formation"
    assert fm_match.category.value != "capacheck"


def test_user_domain_rules_qpeed_soc_setting_subtype() -> None:
    match = classify_schedule_filename(DEFERRED_SOC_SETTING)
    assert match.category.value == "qpeed"
    assert match.qpeed_variant == QpeedVariant.SOC_SETTING
    assert match.is_qpeed_soc_setting


def test_intake_file_was_processed_into_locked_json() -> None:
    locked = json.loads(LOCKED_PATH.read_text(encoding="utf-8"))
    pne_units = {item["pne_unit"] for item in locked["selected"]}
    assert pne_units == {"PNE02", "PNE16"}
