"""Gate D — family topology of module expands vs locked golden fixtures.

Modules are protocol templates, not byte clones of lab schedules. These tests
check shared step-type *families*, not identical step counts or LOOP/CYCLE order.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.ir.project import ModuleNode
from pne_scheduler.modules.base import expand_module
from pne_scheduler.validate.topology import (
    fixture_type_family,
    intent_type_family,
    load_golden_by_id,
)

CELL = CellProfile(nominal_capacity_mAh=80.0, v_max=4.2, v_min=2.5)
ROOT = Path(__file__).resolve().parents[1]


def _module_family(module_type: str, params: dict) -> frozenset[str]:
    intents = expand_module(
        ModuleNode(id="m1", module_type=module_type, params=params),
        CELL,
    )
    return intent_type_family(intents)


def _golden_family(golden_id: str) -> frozenset[str]:
    golden = load_golden_by_id(golden_id)
    path = ROOT / "example" / "fixtures" / Path(golden["path"])
    if not path.is_file():
        pytest.skip(f"missing {path}")
    return fixture_type_family(path)


def test_formation_family_matches_golden_fm() -> None:
    fixture = _golden_family("golden-formation-696")
    module = _module_family("formation", {"cycle_count": 1})
    assert {"charge", "discharge", "rest"} <= module
    # This FM golden is charge/rest/cycle/loop oriented (no discharge in parse).
    assert {"charge", "rest"} <= fixture


def test_cycle_life_family_has_loop_like_golden() -> None:
    fixture = _golden_family("golden-cycle-612-long")
    module = _module_family("cycle_life", {"loop_count": 2, "rest_s": 30.0})
    assert {"cycle", "charge", "discharge", "rest", "loop", "end"} <= module
    assert {"charge", "discharge", "rest", "loop", "end"} <= fixture


def test_hppc_fixture_has_soc_staircase_and_pulses() -> None:
    fixture = _golden_family("golden-hppc-612")
    module = _module_family(
        "hppc",
        {"soc_fractions": [0.9, 0.5, 0.1], "rest_between_s": 5.0, "pulse_s": 2.0},
    )
    assert {"charge", "discharge", "rest"} <= module
    assert {"charge", "discharge", "rest"} <= fixture


def test_capacheck_golden_has_cycle_loop_end_family() -> None:
    fixture = _golden_family("golden-capacheck-612-b0")
    module = _module_family(
        "capacheck",
        {"measurement_cycles": 1, "rest_s": 10.0, "loop_count": 1},
    )
    # Module uses CYCLE→body→LOOP (CTS-safe); golden may order differently.
    assert {"cycle", "loop", "charge", "discharge", "rest", "end"} <= module
    assert {"cycle", "loop", "charge", "discharge", "rest", "end"} <= fixture


def test_rpt_and_qpeed_goldens_are_parseable_families() -> None:
    for golden_id in ("golden-rpt-612", "golden-qpeed-612"):
        family = _golden_family(golden_id)
        assert {"charge", "discharge", "rest", "end"} <= family
