from __future__ import annotations

import json
from pathlib import Path

from pne_scheduler.tools.run_gate_b_validation import _controlled_pair_evidence

ROOT = Path(__file__).resolve().parents[1]


def test_goto_controlled_pair_is_imported() -> None:
    inventory = _controlled_pair_evidence()
    paths = {row["path"] for row in inventory["intakes"]}
    assert "example/gate_b_pairs/pne02-loop-goto/intake.json" in paths

    goto = next(
        row
        for row in inventory["intakes"]
        if row["path"].endswith("pne02-loop-goto/intake.json")
    )
    assert goto["equipment"] == "PNE02"
    assert goto["pair_clean"] is True
    assert goto["expected_field"] == "loop_target"

    comparison = json.loads(
        (ROOT / "example" / "gate_b_pairs" / "pne02-loop-goto" / "comparison.json").read_text(
            encoding="utf-8"
        )
    )
    assert comparison["summary"]["controlled_pair_clean"] is True
    word = comparison["step_changes"][0]["words"][0]
    assert word["field"] == "loop_target"
    assert word["offset"] == 48
    assert word["primary_before"] == 1.0
    assert word["primary_after"] == 7.0
    assert comparison["step_changes"][0]["step_no"] == 17
