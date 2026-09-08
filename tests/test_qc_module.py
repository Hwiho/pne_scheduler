from __future__ import annotations

import struct
from pathlib import Path

import pytest

from pne_scheduler.engine.compiler import compile_steps
from pne_scheduler.io.reader import read_sch
from pne_scheduler.ir import CellProfile, ModuleNode, compose_module_steps


CELL = CellProfile(nominal_capacity_mAh=80.0, v_max=4.2, v_min=2.5)
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("params", "expected_count"),
    [
        ({"variant": "cycle"}, 17),
        ({"variant": "1n1q"}, 17),
        (
            {
                "variant": "cycle",
                "fast_rates_c": [5.0, 4.0, 3.0, 2.0],
                "fast_voltages_v": [3.8, 3.9, 4.0, 4.05],
                "fast_times_s": [120.0, 180.0, 240.0, 300.0],
            },
            18,
        ),
        ({"variant": "1_charge"}, 25),
    ],
)
def test_qc_candidate_shapes(params: dict, expected_count: int) -> None:
    steps = compose_module_steps([ModuleNode("qc_1", "qc", params)], CELL)

    assert len(steps) == expected_count
    assert steps[-1].step_type == "end"
    assert all(step.loop_target_ref is None for step in steps)


def test_qc_rejects_misaligned_fast_segments() -> None:
    with pytest.raises(ValueError, match="equal nonzero lengths"):
        compose_module_steps(
            [
                ModuleNode(
                    "qc_1",
                    "qc",
                    {"fast_rates_c": [4.0], "fast_voltages_v": [3.9, 4.0]},
                )
            ],
            CELL,
        )


@pytest.mark.parametrize(
    ("variant", "fixture_name"),
    [
        ("cycle", "07100766_260522_Set2_SJ1300_60-40_wet_QC_cycle.sch"),
        ("1n1q", "Set2_QC_1N1Q.sch"),
        ("1_charge", "Set2_QC_1_charge.sch"),
    ],
)
def test_qc_default_type_topology_matches_set2_fixture(
    variant: str,
    fixture_name: str,
) -> None:
    steps = compose_module_steps(
        [ModuleNode("qc_1", "qc", {"variant": variant})], CELL
    )
    records = compile_steps(steps, CELL)
    compiled_types = [struct.unpack_from("<i", record, 8)[0] for record in records]
    fixture = ROOT / "example" / "fixtures" / "sch_lab_zip" / fixture_name
    golden_types = [step["step_type_code"] for step in read_sch(fixture).steps]

    assert compiled_types == golden_types
