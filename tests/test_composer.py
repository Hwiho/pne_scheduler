from __future__ import annotations

import struct
from pathlib import Path

from pne_scheduler.engine.compiler import compile_steps
from pne_scheduler.io.reader import read_sch
from pne_scheduler.ir import CellProfile, ModuleNode, compose_module_steps


CELL = CellProfile(nominal_capacity_mAh=80.0, v_max=4.2, v_min=2.5)
ROOT = Path(__file__).resolve().parents[1]


def test_composer_removes_fragment_end_and_rebases_raw_loop_target() -> None:
    steps = compose_module_steps(
        [
            ModuleNode("rest_1", "rest", {"duration_s": 10.0}),
            ModuleNode("cycle_1", "cycle_life", {"loop_count": 2}),
        ],
        CELL,
    )

    assert sum(step.step_type == "end" for step in steps) == 1
    assert steps[-1].step_type == "end"
    loop = next(step for step in steps if step.step_type == "loop")
    assert loop.loop_goto_step == 3


def test_qpeed_canonical_shapes_and_resolved_loops() -> None:
    full = compose_module_steps([ModuleNode("q1", "qpeed", {"variant": "full"})], CELL)
    soc = compose_module_steps(
        [ModuleNode("q2", "qpeed", {"variant": "soc_setting"})], CELL
    )

    assert len(full) == 167
    assert len(soc) == 11
    assert all(step.loop_target_ref is None for step in full + soc)
    rates = [step.c_rate for step in full if step.label.startswith("QPEED ") and step.label.endswith("C charge")]
    assert rates[0] == 1.5
    assert rates[-1] == 18.0


def test_qpeed_type_topologies_match_locked_pne02_fixtures() -> None:
    fixture_root = ROOT / "example" / "fixtures" / "capacheck_zip"
    cases = (
        (
            "full",
            "07100766_260617_Set2_bimodal-SJ1300-40um_80C_QPEED-2.sch",
        ),
        (
            "soc_setting",
            "07100766_260713_Set9_QPEED_SOC_setting_BM_SJ1300_6040_C_NCN.sch",
        ),
    )
    for variant, fixture_name in cases:
        steps = compose_module_steps(
            [ModuleNode("q", "qpeed", {"variant": variant})], CELL
        )
        records = compile_steps(steps, CELL)
        compiled_types = [struct.unpack_from("<i", record, 8)[0] for record in records]
        golden_types = [
            step["step_type_code"]
            for step in read_sch(fixture_root / fixture_name).steps
        ]
        assert compiled_types == golden_types
