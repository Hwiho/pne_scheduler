"""Execute the Gate D verification method and assert remediations from the audit."""

from __future__ import annotations

import json
from pathlib import Path

from pne_scheduler.validate.gate_d_harness import run_module_pipeline
from pne_scheduler.validate.gate_d_verification import (
    GATE_D_MODULE_MATRIX,
    DEFAULT_CELL,
    DEFAULT_REPORT_PATH,
    run_gate_d_verification,
    write_gate_d_verification_report,
)

ROOT = Path(__file__).resolve().parents[1]
METHOD_DOC = ROOT / "planning" / "GATE_D_VERIFICATION.md"
AUDIT_DOC = ROOT / "planning" / "GATE_D_VERIFICATION_AUDIT.md"


def test_gate_d_verification_docs_exist() -> None:
    assert METHOD_DOC.is_file()
    assert AUDIT_DOC.is_file()
    method = METHOD_DOC.read_text(encoding="utf-8")
    assert "V1" in method and "V8" in method
    audit = AUDIT_DOC.read_text(encoding="utf-8")
    assert "A1" in audit and "Remediation" in audit


def test_gate_d_verification_suite_passes(tmp_path: Path) -> None:
    """Attempt full V1–V8 verification; must pass after audit remediations."""
    report = run_gate_d_verification(work_dir=tmp_path / "work")
    assert report.gate_d_passed, [
        c.to_dict() for c in report.checks if c.status == "fail"
    ]
    layers = {c.layer for c in report.checks}
    assert "V1" in layers
    assert "V7" in layers
    assert "V6" in layers
    assert any(c.id == "v8_exit_aggregate" for c in report.checks)


def test_gate_d_verification_writes_exit_report(tmp_path: Path) -> None:
    report = run_gate_d_verification(work_dir=tmp_path / "work")
    out = write_gate_d_verification_report(report, tmp_path / "GATE_D_VALIDATION_REPORT.json")
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema"] == "pne_scheduler.gate_d_validation_report/v1"
    assert payload["gate_d_passed"] is True
    assert payload["summary"]["fail"] == 0


def test_gate_d_matrix_covers_all_p0_p1_modules() -> None:
    types = {row["module_type"] for row in GATE_D_MODULE_MATRIX}
    assert {
        "formation",
        "rest",
        "cycle_life",
        "rpt",
        "dcir",
        "hppc",
        "capacheck",
        "qpeed",
        "insitu_cycle",
    } <= types


def test_audit_remediation_a3_charge_voltage_checked(tmp_path: Path) -> None:
    """A3: harness must flag charge voltage packing (regression guard)."""
    report = run_module_pipeline(
        "formation",
        cell=DEFAULT_CELL,
        output_path=tmp_path / "fm.sch",
        params={"cycle_count": 1, "rest_s": 10.0},
    )
    assert report.passed, report.mismatches
    assert report.topology[0] == "charge"


def test_audit_remediation_a4_loop_fields_checked(tmp_path: Path) -> None:
    report = run_module_pipeline(
        "cycle_life",
        cell=DEFAULT_CELL,
        output_path=tmp_path / "cl.sch",
        params={"loop_count": 3, "rest_s": 10.0},
    )
    assert report.passed, report.mismatches
    assert "loop" in report.topology


def test_default_report_path_is_under_planning() -> None:
    assert DEFAULT_REPORT_PATH.name == "GATE_D_VALIDATION_REPORT.json"
    assert DEFAULT_REPORT_PATH.parent.name == "planning"
