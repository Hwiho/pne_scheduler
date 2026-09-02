from __future__ import annotations

import json
from pathlib import Path

from pne_scheduler.tools.run_gate_b_validation import _controlled_pair_evidence

ROOT = Path(__file__).resolve().parents[1]


def test_pne02_controlled_pairs_are_imported() -> None:
    inventory = _controlled_pair_evidence()
    paths = {row["path"] for row in inventory["intakes"]}
    assert "example/gate_b_pairs/pne02-charge-current/intake.json" in paths
    assert "example/gate_b_pairs/pne02-rest-duration/intake.json" in paths

    charge = next(
        row
        for row in inventory["intakes"]
        if row["path"].endswith("pne02-charge-current/intake.json")
    )
    assert charge["equipment"] == "PNE02"
    assert charge["pair_clean"] is True
    assert charge["reopen_verified"] is True

    comparison = json.loads(
        (
            ROOT / "example" / "gate_b_pairs" / "pne02-charge-current" / "comparison.json"
        ).read_text(encoding="utf-8")
    )
    assert comparison["summary"]["controlled_pair_clean"] is True
    assert comparison["before"]["version"] == "0x00010002"
    word = comparison["step_changes"][0]["words"][0]
    assert word["field"] == "fVref"
    assert word["primary_before"] == 10.0
    assert word["primary_after"] == 17.0


def test_pne02_cv_cutoff_pair_is_clean_after_cap496_normalization() -> None:
    comparison = json.loads(
        (
            ROOT / "example" / "gate_b_pairs" / "pne02-cv-cutoff" / "comparison.json"
        ).read_text(encoding="utf-8")
    )
    assert comparison["summary"]["controlled_pair_clean"] is True
    word = comparison["step_changes"][0]["words"][0]
    assert word["field"] == "fEndI"
    assert word["primary_before"] == 2.0
    assert word["primary_after"] == 3.0

    inventory = _controlled_pair_evidence()
    cv = next(
        row
        for row in inventory["intakes"]
        if row["path"].endswith("pne02-cv-cutoff/intake.json")
    )
    assert cv["pair_clean"] is True
    assert cv["valid"] is True


def test_pne02_rest_pair_uses_rest_schedule_before() -> None:
    from pne_scheduler.io.sch_parser import parse_schedule_file

    before = parse_schedule_file(
        ROOT / "example" / "gate_b_pairs" / "pne02-rest-duration" / "before.sch"
    )
    assert [step.step_type for step in before.steps] == [
        "CCCV",
        "REST",
        "CC_DCHG",
        "LOOP",
        "END",
    ]
