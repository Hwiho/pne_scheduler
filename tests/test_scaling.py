"""What a large campaign costs — pinned so the collapses cannot silently return.

A 2000-cycle campaign produced 1294 validation rows saying six things, 1135
blockers on one gate, seven full schedule expansions per request, and an 800 KB
response on every committed keystroke. These assert the shape of the fix, not a
wall-clock number, so they hold on a slow machine too.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pne_scheduler.api.serializers import views_json
from pne_scheduler.ui.document import ProjectDocument
from pne_scheduler.ui.workspace_model import WorkspaceModel

EXAMPLE = Path(__file__).resolve().parents[1] / "example" / "example.schproj"


def _campaign(cycles: int = 2000, every: int = 25) -> WorkspaceModel:
    source = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    source["modules"] = []
    model = WorkspaceModel(ProjectDocument.detached(source))
    model.add_campaign(
        model.plan_campaign(
            total_cycles=cycles, rpt_every=every, charge_c_rate=0.5, discharge_c_rate=0.5
        )
    )
    return model


@pytest.fixture(scope="module")
def large() -> WorkspaceModel:
    model = _campaign()
    assert len(model.project.expand_steps()) > 2000, "fixture is not actually large"
    return model


def test_a_repeated_finding_is_one_row_that_counts_itself(large):
    rows = large.validation_rows()
    assert len(rows) < 20, f"{len(rows)} rows for a schedule with a handful of problems"
    assert len({(row.code, row.message) for row in rows}) == len(rows)

    repeated = next(row for row in rows if row.occurrences > 1)
    assert "외" in repeated.location_text and str(repeated.occurrences - 1) in repeated.location_text
    assert repeated.other_locations, "the other places must still be reachable"


def test_grouping_hides_no_finding(large):
    """Collapsing repeats must not drop a distinct problem."""
    codes = {row.code for row in large.validation_rows()}
    assert {"DCR_IR_ONLY", "FENDC_UNVERIFIED", "MODULE_TRUST"} <= codes


def test_a_gate_lists_reasons_not_occurrences(large):
    blocked = [o for o in large.release().options if o.blockers]
    assert blocked
    for option in blocked:
        assert len(option.blockers) < 20, f"{len(option.blockers)} blockers on {option.kind}"
        assert len(set(option.blockers)) == len(option.blockers)


def test_trust_is_reported_per_pattern_not_per_module(large):
    """Trust belongs to the pattern; 161 modules of two types have two things to say."""
    notes = large.unverified_notes()
    assert len(notes) < 20, f"{len(notes)} notes for two module types"


def test_one_payload_expands_the_schedule_once(large, monkeypatch):
    import pne_scheduler.ir.procedure as procedure_module
    import pne_scheduler.ui.workspace_model as model_module

    calls = {"n": 0}
    original = procedure_module.build_procedure

    def counted(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(procedure_module, "build_procedure", counted)
    monkeypatch.setattr(model_module, "build_procedure", counted)

    fresh = _campaign(200, 50)
    calls["n"] = 0
    views_json(fresh)
    assert calls["n"] <= 2, f"{calls['n']} full expansions to build one response"


def test_the_step_table_is_not_in_the_default_payload(large):
    """Read-only, one tab, and 78% of the bytes — it is fetched on demand."""
    default = views_json(large)
    assert default["steps"] == []
    assert default["procedure"]["stepCount"] > 2000, "the count still travels"

    included = views_json(large, include_steps=True)
    assert len(included["steps"]) == default["procedure"]["stepCount"]


def test_the_default_payload_does_not_grow_with_the_step_count():
    small = len(json.dumps(views_json(_campaign(200, 50)), ensure_ascii=False))
    big = len(json.dumps(views_json(_campaign(2000, 25)), ensure_ascii=False))
    # Modules still scale, but nothing per-step should. 161 modules vs 9 is the
    # honest growth; a per-step term would be an order of magnitude worse.
    assert big < small * 6, f"{small} → {big} bytes suggests a per-step term returned"
