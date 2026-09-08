"""Gate D P0 — capacity model contract (writer Q_nom vs viewer inference)."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from pne_scheduler.engine.c_rate import (
    WRITER_Q_NOM_SOURCE,
    capacity_mAh_from_fraction,
    current_mA_from_c_rate,
)
from pne_scheduler.engine.compiler import compile_steps
from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.ir.project import ModuleNode, ScheduleProject
from pne_scheduler.ir.step_intent import StepIntent
from pne_scheduler.io.sch_binary import read_sch_binary
from pne_scheduler.io.sch_parser import parse_schedule_file
from pne_scheduler.io.writer import write_sch
from pne_scheduler.schema.ensol_v612 import OFF_CURRENT_MA, OFF_CV_CUTOFF_MA
from pne_scheduler.schema.fields import OFFSET_F_END_C

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "planning" / "Q_NOM_POLICY.json"
RPT_FIXTURE = (
    ROOT
    / "example"
    / "fixtures"
    / "capacheck_zip"
    / "차효현_3350_L.4.36_NP1.08_RPT_SOC50 End_챔버미연동.sch"
)


def test_writer_q_nom_matches_policy_json() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    assert policy["writer"]["source"] == WRITER_Q_NOM_SOURCE
    assert policy["writer"]["explicit_value_required"] is True
    assert policy["writer"]["allow_filename_inference"] is False
    assert policy["writer"]["allow_stack_geometry_inference"] is False
    assert policy["viewer"]["display_only"] is True
    assert policy["viewer"]["may_disagree_with_writer_input"] is True


def test_compile_current_uses_cell_profile_only() -> None:
    cell = CellProfile(nominal_capacity_mAh=80.0, v_max=4.2, v_min=2.5)
    record = compile_steps(
        [StepIntent(step_type="charge", mode="CC", c_rate=0.5, voltage_v=4.2)],
        cell,
    )[0]
    assert struct.unpack_from("<f", record, OFF_CURRENT_MA)[0] == pytest.approx(40.0)

    other = CellProfile(nominal_capacity_mAh=200.0, v_max=4.2, v_min=2.5)
    record_other = compile_steps(
        [StepIntent(step_type="charge", mode="CC", c_rate=0.5, voltage_v=4.2)],
        other,
    )[0]
    assert struct.unpack_from("<f", record_other, OFF_CURRENT_MA)[0] == pytest.approx(100.0)


def test_cv_cutoff_and_end_capacity_scale_from_same_q_nom() -> None:
    cell = CellProfile(nominal_capacity_mAh=80.0, v_max=4.2, v_min=2.5)
    record = compile_steps(
        [
            StepIntent(
                step_type="charge",
                mode="CCCV",
                c_rate=1.0,
                voltage_v=4.2,
                cv_cutoff_c_rate=0.05,
                end_capacity_fraction=0.25,
            )
        ],
        cell,
    )[0]
    assert struct.unpack_from("<f", record, OFF_CURRENT_MA)[0] == pytest.approx(80.0)
    assert struct.unpack_from("<f", record, OFF_CV_CUTOFF_MA)[0] == pytest.approx(4.0)
    assert struct.unpack_from("<f", record, OFFSET_F_END_C)[0] == pytest.approx(
        capacity_mAh_from_fraction(0.25, cell)
    )


def test_roundtrip_packed_current_follows_writer_q_nom(tmp_path: Path) -> None:
    cell = CellProfile(nominal_capacity_mAh=80.0, v_max=4.2, v_min=2.5)
    project = ScheduleProject(
        name="q_nom_contract",
        cell_profile=cell,
        modules=[
            ModuleNode(
                id="fm",
                module_type="formation",
                params={"cycle_count": 1, "charge_c_rate": 0.1, "rest_s": 10.0},
            )
        ],
    )
    output = tmp_path / "q_nom.sch"
    write_sch(project, output)
    doc = read_sch_binary(output)
    packed = struct.unpack_from("<f", doc.steps[0].record, OFF_CURRENT_MA)[0]
    assert packed == pytest.approx(current_mA_from_c_rate(0.1, cell))


@pytest.mark.skipif(not RPT_FIXTURE.is_file(), reason="RPT golden fixture missing")
def test_viewer_inferred_q_nom_may_differ_from_writer() -> None:
    """L7: stack/filename Q_nom is display-only and must not replace CellProfile."""
    parsed = parse_schedule_file(RPT_FIXTURE)
    viewer_q = float(parsed.nominal_capacity_mAh)
    writer_cell = CellProfile(nominal_capacity_mAh=80.0, v_max=4.2, v_min=2.5)
    assert viewer_q > 0

    record = compile_steps(
        [StepIntent(step_type="discharge", mode="CC", c_rate=1.0, end_voltage_v=2.5)],
        writer_cell,
    )[0]
    assert struct.unpack_from("<f", record, OFF_CURRENT_MA)[0] == pytest.approx(80.0)
    # viewer_q is for display only; it must not have been used above.
    assert viewer_q != 0.0
