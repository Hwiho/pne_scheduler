"""Run Gate B validation checks and write a summary report."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from pne_scheduler.tools.compare_step_layouts import build_step_layout_diff_report  # noqa: E402
from pne_scheduler.validate.assb_parser_diff import (  # noqa: E402
    build_assb_parser_diff_report,
    compare_fixture_parsers,
    offset_parity_summary,
)
from pne_scheduler.validate.intake import validate_intake_file  # noqa: E402

REPORT_JSON = ROOT / "planning" / "GATE_B_VALIDATION_REPORT.json"
GATE_B_TESTS = [
    "tests/test_gate_b_tooling.py",
    "tests/test_golden_semantic.py",
    "tests/test_golden_fixtures_locked.py",
    "tests/test_validation_intake.py",
    "tests/test_ensol_v612_golden.py",
    "tests/test_compiler_offsets.py",
    "tests/test_unit_contract.py",
    "tests/test_assb_offset_parity.py",
    "tests/test_fixture_catalog.py",
]


def _run_pytest() -> dict:
    cmd = [sys.executable, "-m", "pytest", *GATE_B_TESTS, "-q", "--tb=line"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "passed": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout.strip().splitlines()[-3:],
        "stderr_tail": proc.stderr.strip().splitlines()[-5:] if proc.stderr else [],
    }


def _fixture_parser_checks() -> dict:
    fixtures = [
        ROOT / "example" / "fixtures" / "hppc" / "HPPC_Full range.sch",
        ROOT
        / "example"
        / "fixtures"
        / "capacheck_zip"
        / "9)Bimodal_SJ1300_6040_NCN_capacheck.sch",
    ]
    existing = [p for p in fixtures if p.is_file()]
    results = []
    for path in existing:
        diff = compare_fixture_parsers(path)
        results.append(
            {
                "path": str(path.relative_to(ROOT)),
                "layout_match": diff.layout_match,
                "step_count_match": diff.step_count_match,
            }
        )
    report = build_assb_parser_diff_report(existing)
    return {
        "fixtures": results,
        "all_layout_match": all(r["layout_match"] for r in results),
        "assb_summary": report["summary"],
    }


def build_gate_b_report() -> dict:
    intake_template = ROOT / "example" / "validation-intake.template.json"
    intake_result = validate_intake_file(intake_template) if intake_template.is_file() else None
    step_layout = build_step_layout_diff_report()
    parity = offset_parity_summary()
    pytest_result = _run_pytest()
    parser_checks = _fixture_parser_checks()

    checks = {
        "B3_fixture_catalog": pytest_result["passed"],
        "B1_step_layout_612_696": step_layout["sampled_step_records"]["612"] > 0
        and step_layout["sampled_step_records"]["696"] > 0,
        "B2_assb_offset_parity": bool(parity.get("shared_pairs")),
        "B2_parser_layout_match": parser_checks["all_layout_match"],
        "B4_semantic_golden_tests": pytest_result["passed"],
        "B5_intake_template_valid": intake_result.valid if intake_result else False,
    }
    return {
        "schema": "pne_scheduler.gate_b_validation_report/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "all_passed": all(checks.values()),
        "pytest": pytest_result,
        "offset_parity": {
            "shared_pairs": len(parity.get("shared_pairs", [])),
            "documented_divergences": len(parity.get("documented_divergences", [])),
        },
        "step_layout": {
            "extension_bytes": step_layout.get("extension_bytes"),
            "sampled": step_layout.get("sampled_step_records"),
        },
        "parser_fixture_checks": parser_checks,
        "intake_template": {
            "path": str(intake_template.relative_to(ROOT)),
            "valid": intake_result.valid if intake_result else None,
            "errors": list(intake_result.errors) if intake_result else [],
            "warnings": list(intake_result.warnings) if intake_result else [],
        },
        "gate_b_tasks": {
            "B0_raw_unit_contract": checks["B4_semantic_golden_tests"],
            "B1_field_tables": checks["B1_step_layout_612_696"],
            "B2_parser_alignment": checks["B2_parser_layout_match"],
            "B3_read_regression": checks["B3_fixture_catalog"],
            "B4_semantic_goldens": checks["B4_semantic_golden_tests"],
            "B5_intake_validation": checks["B5_intake_template_valid"],
        },
        "next_actions": [
            "Collect controlled before/after pairs per docs/GATE_B.md (B5 evidence)",
            "Promote writer-ready fields only after CTSPro reopen check",
            "Resolve ASSB documented divergences in schema/ensol_v612.py",
        ],
    }


def main() -> None:
    report = build_gate_b_report()
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Refresh auto-generated annex
    from pne_scheduler.tools.assb_parser_diff_report import main as refresh_annex  # noqa: E402

    refresh_annex()

    print(f"Wrote {REPORT_JSON}")
    print("Gate B checks:", report["checks"])
    print("all_passed:", report["all_passed"])
    if not report["all_passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
