"""Gate D verification must actually fail when something breaks.

A suite that reports 49/49 but survives injected faults verifies nothing.
These tests are the mutation backtest kept as permanent regression cover for
two holes found on 2026-09-08:

* ``_check_v6_families`` compared only the static golden fixture, so a module
  could be broken arbitrarily and every ``family_*`` check still passed.
* ``gate_d_passed`` ignored skips, so a missing golden fixture yielded a green
  exit claim with zero golden comparisons actually executed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pne_scheduler.ir.step_intent import StepIntent
from pne_scheduler.modules.cycle_life import CycleLifeModule
from pne_scheduler.modules.formation import FormationModule
from pne_scheduler.validate.gate_d_verification import (
    _check_v6_families,
    run_gate_d_verification,
)


def test_baseline_passes_with_no_skips() -> None:
    """The exit claim must rest on checks that actually ran."""
    report = run_gate_d_verification()
    summary = report.to_dict()["summary"]
    assert report.gate_d_passed
    assert summary["fail"] == 0
    assert summary["skip"] == 0, "a skipped check means that layer never ran"


def test_v6_detects_module_topology_regression(monkeypatch: pytest.MonkeyPatch) -> None:
    """V6 must compare the module's live expansion, not just the golden file."""
    only_rest = lambda self, cell: [StepIntent(step_type="rest", end_time_s=1.0)]  # noqa: E731
    monkeypatch.setattr(FormationModule, "expand", only_rest)
    monkeypatch.setattr(CycleLifeModule, "expand", only_rest)

    by_id = {c.id: c for c in _check_v6_families()}

    assert by_id["family_formation"].status == "fail"
    assert by_id["family_cycle"].status == "fail"
    assert "module" in by_id["family_cycle"].detail
    # Untouched modules stay green — the check is specific, not blanket.
    assert by_id["family_hppc"].status == "pass"
    assert by_id["family_capacheck"].status == "pass"


def test_missing_golden_blocks_the_exit_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    """A skipped golden comparison must not read as a pass."""
    real_is_file = Path.is_file

    def sch_missing(self: Path) -> bool:
        if str(self).endswith(".sch"):
            return False
        return real_is_file(self)

    monkeypatch.setattr(Path, "is_file", sch_missing)

    report = run_gate_d_verification()

    assert not report.gate_d_passed
    aggregate = next(c for c in report.checks if c.id == "v8_exit_aggregate")
    assert aggregate.status == "fail"
    assert "never ran" in aggregate.detail
