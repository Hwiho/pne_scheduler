from __future__ import annotations

from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.modules.cycle_life import CycleLifeModule
from pne_scheduler.modules.insitu_cycle import InsituCycleModule

CELL = CellProfile(nominal_capacity_mAh=80.0, v_max=4.2, v_min=2.5)


def test_insitu_cycle_relabels_the_inherited_cycle_marker() -> None:
    """InsituCycleModule.expand() used to check `label is None`, but
    CycleLifeModule always sets a non-None default label ("cycle marker"), so
    the relabel to "in-situ cycle marker (no RPT)" could never actually run."""
    steps = InsituCycleModule().expand(CELL)
    assert steps[0].step_type == "cycle"
    assert steps[0].label == "in-situ cycle marker (no RPT)"


def test_cycle_life_marker_unaffected() -> None:
    steps = CycleLifeModule().expand(CELL)
    assert steps[0].step_type == "cycle"
    assert steps[0].label == "cycle marker"
