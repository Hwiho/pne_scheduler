from __future__ import annotations

import json
from pathlib import Path

from pne_scheduler.tools.run_gate_b_validation import _controlled_pair_evidence

ROOT = Path(__file__).resolve().parents[1]


def test_baseline_controlled_pairs_are_imported() -> None:
    inventory = _controlled_pair_evidence()
    assert inventory["intake_count"] >= 5
    paths = {row["path"] for row in inventory["intakes"]}
    assert "example/gate_b_pairs/baseline-charge-current/intake.json" in paths
    assert inventory["valid_intake_count"] >= 4

    charge = next(
        row
        for row in inventory["intakes"]
        if row["path"].endswith("baseline-charge-current/intake.json")
    )
    assert charge["pair_clean"] is True
    assert charge["reopen_verified"] is False

    comparison = json.loads(
        (
            ROOT / "example" / "gate_b_pairs" / "baseline-charge-current" / "comparison.json"
        ).read_text(encoding="utf-8")
    )
    assert comparison["summary"]["controlled_pair_clean"] is True
    word = comparison["step_changes"][0]["words"][0]
    assert word["field"] == "fVref"
    assert word["primary_before"] == 10000.0
    assert word["primary_after"] == 17000.0


def test_baseline_golden_matches_before_sch() -> None:
    golden = json.loads(
        (ROOT / "example" / "gate_b_pairs" / "baseline-golden.json").read_text(
            encoding="utf-8"
        )
    )
    from pne_scheduler.io.sch_parser import parse_schedule_file

    doc = parse_schedule_file(
        ROOT / "example" / "gate_b_pairs" / "baseline-charge-current" / "before.sch"
    )
    charge, discharge, loop_step, end = doc.steps
    assert charge.step_type == "CCCV"
    assert charge.f_iref == 10000.0
    assert charge.f_end_i == 2000.0
    assert discharge.step_type == "CC_DCHG"
    assert discharge.f_iref == 9000.0
    assert discharge.f_end_v == 2500.0
    assert loop_step.step_type == "LOOP"
    assert end.step_type == "END"
    assert golden["ctspro_build"] == "CYCGN-P1107-S01-R001-N022"
    cv = golden["ui_to_binary"]["steps"][0]["fields"]["cv_voltage_mV"]
    assert cv["binary_mode_value@12"] == 4000
    assert cv.get("confirmed")
