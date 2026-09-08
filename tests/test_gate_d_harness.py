"""Gate D — integration harness for all P0/P1 experiment modules."""

from __future__ import annotations

import struct
from pathlib import Path

from pne_scheduler.engine.compiler import compile_steps
from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.ir.project import ModuleNode
from pne_scheduler.modules.base import expand_module
from pne_scheduler.validate.gate_d_harness import run_module_pipeline

CELL = CellProfile(nominal_capacity_mAh=80.0, v_max=4.2, v_min=2.5)


def test_gate_d_formation_pipeline(tmp_path: Path) -> None:
    report = run_module_pipeline(
        "formation",
        cell=CELL,
        output_path=tmp_path / "formation.sch",
        params={"cycle_count": 1, "rest_s": 60.0},
    )
    assert report.passed, report.mismatches
    assert report.topology == (
        "charge",
        "rest",
        "discharge",
        "rest",
        "end",
    )


def test_gate_d_rest_pipeline(tmp_path: Path) -> None:
    report = run_module_pipeline(
        "rest",
        cell=CELL,
        output_path=tmp_path / "rest.sch",
        params={"duration_s": 120.0},
    )
    assert report.passed, report.mismatches
    assert report.topology == ("rest", "end")


def test_gate_d_cycle_life_pipeline(tmp_path: Path) -> None:
    report = run_module_pipeline(
        "cycle_life",
        cell=CELL,
        output_path=tmp_path / "cycle_life.sch",
        params={"loop_count": 2, "rest_s": 30.0},
    )
    assert report.passed, report.mismatches
    assert report.topology[0] == "cycle"
    assert report.topology[-2] == "loop"
    assert report.topology[-1] == "end"
    assert "charge" in report.topology
    assert "discharge" in report.topology


def test_gate_d_rpt_pipeline(tmp_path: Path) -> None:
    report = run_module_pipeline(
        "rpt",
        cell=CELL,
        output_path=tmp_path / "rpt.sch",
        params={
            "soc_fractions": [0.8, 0.5],
            "rest_s": 10.0,
            "dcir_pulse_s": 2.0,
        },
    )
    assert report.passed, report.mismatches
    assert report.topology.count("discharge") >= 4  # SOC set + pulse per SOC
    assert any("dcr_start_s" in w for w in report.warnings)
    assert any("end_capacity_fraction" in w or "fEndC" in w for w in report.warnings)


def test_gate_d_dcir_pipeline_warns_dcr_ir_only(tmp_path: Path) -> None:
    report = run_module_pipeline(
        "dcir",
        cell=CELL,
        output_path=tmp_path / "dcir.sch",
        params={"soc_fractions": [0.8], "rest_s": 10.0, "pulse_s": 2.0},
    )
    assert report.passed, report.mismatches
    assert any("dcr_start_s" in w for w in report.warnings)
    # DCR Excel offsets stay zero (IR-only).
    intents = expand_module(
        ModuleNode(
            id="d1",
            module_type="dcir",
            params={"soc_fractions": [0.8], "rest_s": 10.0, "pulse_s": 2.0},
        ),
        CELL,
    )
    pulse = next(i for i in intents if i.dcr_start_s is not None)
    record = compile_steps([pulse], CELL)[0]
    assert struct.unpack_from("<f", record, 241)[0] == 0.0
    assert struct.unpack_from("<f", record, 245)[0] == 0.0


def test_gate_d_hppc_pipeline(tmp_path: Path) -> None:
    report = run_module_pipeline(
        "hppc",
        cell=CELL,
        output_path=tmp_path / "hppc.sch",
        params={
            "soc_fractions": [0.9, 0.5],
            "rest_between_s": 5.0,
            "pulse_s": 2.0,
        },
    )
    assert report.passed, report.mismatches
    assert "charge" in report.topology
    assert "discharge" in report.topology


def test_gate_d_capacheck_pipeline(tmp_path: Path) -> None:
    report = run_module_pipeline(
        "capacheck",
        cell=CELL,
        output_path=tmp_path / "capacheck.sch",
        params={"measurement_cycles": 1, "rest_s": 10.0, "loop_count": 1},
    )
    assert report.passed, report.mismatches
    assert report.topology[0] == "cycle"
    assert report.topology[-2] == "loop"
    assert report.topology[-1] == "end"


def test_gate_d_qpeed_full_and_soc_setting(tmp_path: Path) -> None:
    full = run_module_pipeline(
        "qpeed",
        cell=CELL,
        output_path=tmp_path / "qpeed_full.sch",
        params={
            "variant": "full",
            "soc_fractions": [0.5],
            "rest_between_s": 5.0,
            "pulse_s": 2.0,
        },
    )
    assert full.passed, full.mismatches
    assert "charge" in full.topology and "discharge" in full.topology

    soc = run_module_pipeline(
        "qpeed",
        cell=CELL,
        output_path=tmp_path / "qpeed_soc.sch",
        params={
            "variant": "soc_setting",
            "soc_fractions": [0.5],
            "rest_between_s": 5.0,
        },
    )
    assert soc.passed, soc.mismatches
    assert soc.topology[-2:] == ("loop", "end")


def test_gate_d_insitu_cycle_pipeline(tmp_path: Path) -> None:
    report = run_module_pipeline(
        "insitu_cycle",
        cell=CELL,
        output_path=tmp_path / "insitu.sch",
        params={"loop_count": 2, "rest_s": 5.0},
    )
    assert report.passed, report.mismatches
    intents = expand_module(
        ModuleNode(id="i1", module_type="insitu_cycle", params={"loop_count": 2}),
        CELL,
    )
    assert intents[0].label == "in-situ cycle marker (no RPT)"
