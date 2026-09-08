from __future__ import annotations

import struct
from pathlib import Path

from pne_scheduler.engine.compiler import compile_steps
from pne_scheduler.io.reader import read_sch
from pne_scheduler.ir import CellProfile, ModuleNode, ScheduleProject
from pne_scheduler.schema.ensol_v612 import (
    OFF_DOD_PERCENT,
    OFF_LOOP_GOTO_ENSOL,
    OFF_VOLT_OR_VLIM_MV,
)

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "example" / "fixtures" / "hppc" / "HPPC_Full range.sch"


def _full_steps():
    project = ScheduleProject(
        name="hppc-full",
        cell_profile=CellProfile(83.24, 4.2, 2.5, max_current_mA=500.0),
        modules=[ModuleNode("hppc", "hppc", {"variant": "full"})],
    )
    return project, project.expand_steps()


def test_hppc_full_matches_locked_62_step_type_topology() -> None:
    project, steps = _full_steps()
    records = compile_steps(steps, project.cell_profile)
    compiled_types = [struct.unpack_from("<i", record, 8)[0] for record in records]
    golden_types = [step["step_type_code"] for step in read_sch(GOLDEN).steps]

    assert len(steps) == 62
    assert compiled_types == golden_types


def test_hppc_full_resolves_nested_loop_and_key_dod_fields() -> None:
    project, steps = _full_steps()
    records = compile_steps(steps, project.cell_profile)

    assert steps[45].loop_goto_step == 8  # SCH step 46 -> SCH step 8
    assert struct.unpack_from("<I", records[45], OFF_LOOP_GOTO_ENSOL)[0] == 8
    assert struct.unpack_from("<f", records[28], OFF_DOD_PERCENT)[0] == 10.0
    assert struct.unpack_from("<f", records[50], OFF_DOD_PERCENT)[0] == 5.0
    assert struct.unpack_from("<f", records[19], OFF_VOLT_OR_VLIM_MV)[0] == 2200.0
    assert struct.unpack_from("<f", records[58], OFF_VOLT_OR_VLIM_MV)[0] == 2000.0
