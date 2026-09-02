"""Run Gate B validation checks and write a summary report."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from pne_scheduler.tools.compare_step_layouts import build_step_layout_diff_report  # noqa: E402
from pne_scheduler.tools.compare_sch import compare_sch_files  # noqa: E402
from pne_scheduler.engine.c_rate import WRITER_Q_NOM_SOURCE  # noqa: E402
from pne_scheduler.schema.fields import (  # noqa: E402
    get_step_fields,
    validate_step_field_registry,
)
from pne_scheduler.validate.assb_parser_diff import (  # noqa: E402
    build_assb_parser_diff_report,
    compare_fixture_parsers,
    offset_parity_summary,
)
from pne_scheduler.validate.intake import (  # noqa: E402
    validate_intake_file,
    validate_intake_with_compare_report,
)

REPORT_JSON = ROOT / "planning" / "GATE_B_VALIDATION_REPORT.json"
WAIVER_JSON = ROOT / "planning" / "GATE_B_CONTROLLED_PAIR_WAIVERS.json"
CONTROLLED_PAIR_DIR = ROOT / "example" / "gate_b_pairs"
REQUIRED_CONTROLLED_EVIDENCE = {
    "PNE02": {
        "fIref",
        "fVref",
        "fEndV",
        "fEndI",
        "loop_count",
        "loop_target",
        "record_time_s",
    },
    "PNE16": {"fIref", "fVref"},
}
GATE_B_TESTS = [
    "tests/test_gate_b_tooling.py",
    "tests/test_golden_semantic.py",
    "tests/test_golden_fixtures_locked.py",
    "tests/test_validation_intake.py",
    "tests/test_ensol_v612_golden.py",
    "tests/test_compiler_offsets.py",
    "tests/test_unit_contract.py",
    "tests/test_schema_evidence.py",
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
    fixture_root = ROOT / "example" / "fixtures"
    catalog_path = fixture_root / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    fixtures = [fixture_root / row["path"] for row in catalog["fixtures"]]
    existing = [p for p in fixtures if p.is_file()]
    results = []
    for path in existing:
        diff = compare_fixture_parsers(path)
        results.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "layout_match": diff.layout_match,
                "step_count_match": diff.step_count_match,
            }
        )
    report = build_assb_parser_diff_report(existing)
    return {
        "fixtures": results,
        "all_layout_match": all(r["layout_match"] for r in results),
        "all_step_count_match": all(r["step_count_match"] for r in results),
        "assb_summary": report["summary"],
    }


def _load_waiver_payload() -> dict:
    if not WAIVER_JSON.is_file():
        return {}
    return json.loads(WAIVER_JSON.read_text(encoding="utf-8"))


def _load_controlled_pair_waivers() -> dict[str, set[str]]:
    """Equipment → waived required fields (UI-blocked; see GATE_B_CONTROLLED_PAIR_WAIVERS.json)."""
    payload = _load_waiver_payload()
    waived: dict[str, set[str]] = defaultdict(set)
    for row in payload.get("waivers", []):
        equipment = row.get("equipment")
        field = row.get("field")
        if isinstance(equipment, str) and isinstance(field, str):
            waived[equipment].add(field)
    return dict(waived)


def _screenshots_required_for_complete_evidence() -> bool:
    policy = _load_waiver_payload().get("evidence_policy", {})
    return bool(policy.get("screenshots_required", True))


def _controlled_pair_evidence() -> dict:
    """Inventory real intake files without treating the fillable template as evidence."""
    intake_paths = (
        sorted(CONTROLLED_PAIR_DIR.rglob("intake.json"))
        if CONTROLLED_PAIR_DIR.is_dir()
        else []
    )
    rows = []
    for path in intake_paths:
        try:
            result = validate_intake_file(path)
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            rows.append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "valid": False,
                    "reopen_verified": False,
                    "errors": [str(exc)],
                }
            )
            continue
        errors = list(result.errors)
        warnings = list(result.warnings)
        before_path = path.parent / str(payload.get("before_file", ""))
        after_path = path.parent / str(payload.get("after_file", ""))
        pair_clean = False
        if before_path.is_file() and after_path.is_file():
            compare_report = compare_sch_files(before_path, after_path)
            combined = validate_intake_with_compare_report(payload, compare_report)
            errors = list(combined.errors)
            warnings = list(combined.warnings)
            pair_clean = combined.valid
        else:
            errors.append("before_file and after_file must exist next to intake.json")
        equipment = payload.get("equipment", {})
        reopen_verified = payload.get("ctspro_reopen_verified") is True
        evidence_complete = (
            not errors
            and pair_clean
            and reopen_verified
            and bool(equipment.get("ctspro_version"))
            and bool(equipment.get("channel_profile"))
            and bool(payload.get("expected_field"))
        )
        if _screenshots_required_for_complete_evidence():
            evidence_complete = evidence_complete and bool(payload.get("screenshots") or [])
        rows.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "valid": not errors,
                "pair_clean": pair_clean,
                "reopen_verified": reopen_verified,
                "evidence_complete": evidence_complete,
                "equipment": equipment.get("label"),
                "ui_field": payload.get("ui_field"),
                "expected_field": payload.get("expected_field"),
                "errors": errors,
                "warnings": warnings,
            }
        )
    valid = [row for row in rows if row["valid"]]
    reopened = [row for row in valid if row["reopen_verified"]]
    complete = [row for row in valid if row["evidence_complete"]]
    covered = defaultdict(set)
    for row in complete:
        covered[row["equipment"]].add(row["expected_field"])
    waived = _load_controlled_pair_waivers()
    waiver_payload = _load_waiver_payload()
    waiver_rows = list(waiver_payload.get("waivers", []))
    evidence_policy = waiver_payload.get("evidence_policy", {})
    required_equipment = set(REQUIRED_CONTROLLED_EVIDENCE.keys())
    required_intake_rows = [
        row for row in valid if row.get("equipment") in required_equipment
    ]
    required_complete = [row for row in required_intake_rows if row["evidence_complete"]]
    missing_required = {
        equipment: sorted(
            (fields - covered[equipment]) - waived.get(equipment, set())
        )
        for equipment, fields in REQUIRED_CONTROLLED_EVIDENCE.items()
        if (fields - covered[equipment]) - waived.get(equipment, set())
    }
    return {
        "directory": CONTROLLED_PAIR_DIR.relative_to(ROOT).as_posix(),
        "intake_count": len(rows),
        "valid_intake_count": len(valid),
        "reopen_verified_count": len(reopened),
        "complete_evidence_count": len(complete),
        "required_equipment_intake_count": len(required_intake_rows),
        "required_equipment_complete_count": len(required_complete),
        "evidence_policy": evidence_policy,
        "required_fields": {
            equipment: sorted(fields)
            for equipment, fields in REQUIRED_CONTROLLED_EVIDENCE.items()
        },
        "waived_required_fields": {
            equipment: sorted(fields)
            for equipment, fields in sorted(waived.items())
        },
        "controlled_pair_waivers": waiver_rows,
        "missing_required_fields": missing_required,
        "intakes": rows,
    }


def build_gate_b_report() -> dict:
    intake_template = ROOT / "example" / "validation-intake.template.json"
    intake_result = validate_intake_file(intake_template) if intake_template.is_file() else None
    step_layout = build_step_layout_diff_report()
    parity = offset_parity_summary()
    corpus_evidence_path = ROOT / "planning" / "GATE_B_CORPUS_EVIDENCE.json"
    corpus_evidence = json.loads(corpus_evidence_path.read_text(encoding="utf-8"))
    divergence_resolution = corpus_evidence.get("assb_divergence_resolution", {})
    corpus_resolved_divergences = [
        name
        for name, row in divergence_resolution.items()
        if row.get("status") == "corpus_resolved_to_ensol_semantics"
    ]
    externally_unresolved_divergences = [
        name
        for name, row in divergence_resolution.items()
        if row.get("status") == "externally_unresolved"
    ]
    pytest_result = _run_pytest()
    parser_checks = _fixture_parser_checks()
    field_registry_errors = validate_step_field_registry()
    controlled_pairs = _controlled_pair_evidence()

    tooling_checks = {
        "pytest_subset": pytest_result["passed"],
        "B3_fixture_catalog": pytest_result["passed"],
        "B1_step_layout_612_696": step_layout["sampled_step_records"]["612"] > 0
        and step_layout["sampled_step_records"]["696"] > 0,
        "B1_canonical_field_registry": not field_registry_errors
        and bool(get_step_fields(0x00010003))
        and bool(get_step_fields(0x00010004)),
        "B2_assb_offset_parity": bool(parity.get("shared_pairs")),
        "B2_parser_layout_match": (
            parser_checks["all_layout_match"]
            and parser_checks["all_step_count_match"]
            and parser_checks["assb_summary"]["fixtures_with_field_mismatches"] == 0
        ),
        "B4_semantic_golden_tests": pytest_result["passed"],
        "B5_intake_template_valid": intake_result.valid if intake_result else False,
        "B0_explicit_writer_q_nom_contract": (
            WRITER_Q_NOM_SOURCE == "cell_profile.nominal_capacity_mAh"
        ),
    }
    repository_ready = all(tooling_checks.values())
    cp = controlled_pairs
    required_ready = (
        cp["required_equipment_complete_count"] == cp["required_equipment_intake_count"]
        and cp["required_equipment_intake_count"] > 0
    )
    controlled_pair_ready = required_ready and not cp["missing_required_fields"]
    gate_b_passed = repository_ready and controlled_pair_ready
    status = (
        "passed"
        if gate_b_passed
        else "ready_for_controlled_pairs"
        if repository_ready
        else "repository_work_remaining"
    )
    return {
        "schema": "pne_scheduler.gate_b_validation_report/v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "tooling_checks": tooling_checks,
        "tooling_passed": repository_ready,
        "repository_ready_for_controlled_pairs": repository_ready,
        "gate_b_passed": gate_b_passed,
        "all_passed": gate_b_passed,
        "pytest": pytest_result,
        "offset_parity": {
            "shared_pairs": len(parity.get("shared_pairs", [])),
            "documented_divergences": len(parity.get("documented_divergences", [])),
            "corpus_resolved_divergences": corpus_resolved_divergences,
            "externally_unresolved_divergences": externally_unresolved_divergences,
        },
        "step_layout": {
            "extension_bytes": step_layout.get("extension_bytes"),
            "sampled": step_layout.get("sampled_step_records"),
        },
        "parser_fixture_checks": parser_checks,
        "intake_template": {
            "path": intake_template.relative_to(ROOT).as_posix(),
            "valid": intake_result.valid if intake_result else None,
            "errors": list(intake_result.errors) if intake_result else [],
            "warnings": list(intake_result.warnings) if intake_result else [],
        },
        "canonical_field_registry": {
            "valid": not field_registry_errors,
            "errors": list(field_registry_errors),
            "writer_ready_field_count": sum(
                field.writer_ready
                for version in (0x00010002, 0x00010003, 0x00010004)
                for field in get_step_fields(version)
            ),
        },
        "q_nom_contract": {
            "writer_source": WRITER_Q_NOM_SOURCE,
            "inferred_geometry_allowed_for_writer": False,
            "viewer_may_display_inferred_q_nom": True,
        },
        "controlled_pair_evidence": controlled_pairs,
        "gate_b_tasks": {
            "B0_raw_unit_contract": {
                "repository_ready": tooling_checks["B0_explicit_writer_q_nom_contract"],
                "external_evidence_complete": controlled_pair_ready,
            },
            "B1_field_tables": {
                "repository_ready": tooling_checks["B1_canonical_field_registry"],
                "external_evidence_complete": controlled_pair_ready,
            },
            "B2_parser_alignment": {
                "repository_ready": tooling_checks["B2_parser_layout_match"],
                "external_evidence_complete": controlled_pair_ready,
            },
            "B3_read_regression": {
                "repository_ready": tooling_checks["B3_fixture_catalog"],
                "external_evidence_complete": True,
            },
            "B4_semantic_goldens": {
                "repository_ready": tooling_checks["B4_semantic_golden_tests"],
                "external_evidence_complete": controlled_pair_ready,
            },
            "B5_intake_validation": {
                "repository_ready": tooling_checks["B5_intake_template_valid"],
                "external_evidence_complete": controlled_pair_ready,
            },
        },
        "remaining_external_requirements": (
            []
            if controlled_pair_ready
            else [
                "Add real CTSPro-created before/after intake files under example/gate_b_pairs/",
                "Record CTSPro build and channel profile in each intake",
                "Set ctspro_reopen_verified=true only after reopening the exact output hash",
                "Promote individual fields to writer-ready only from clean pair evidence",
            ]
        ),
        "next_actions": [
            (
                "Collect controlled before/after pairs per docs/GATE_B.md"
                if repository_ready
                else "Complete failing repository tooling checks before collecting pairs"
            ),
            "Run with --require-gate-exit after controlled-pair evidence is added",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-gate-exit",
        action="store_true",
        help="Exit nonzero unless real controlled-pair evidence completes Gate B.",
    )
    args = parser.parse_args()
    report = build_gate_b_report()
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Refresh auto-generated annex
    from pne_scheduler.tools.assb_parser_diff_report import main as refresh_annex  # noqa: E402

    refresh_annex()

    print(f"Wrote {REPORT_JSON}")
    print("Gate B status:", report["status"])
    print("repository_ready_for_controlled_pairs:", report["repository_ready_for_controlled_pairs"])
    print("gate_b_passed:", report["gate_b_passed"])
    if not report["repository_ready_for_controlled_pairs"]:
        sys.exit(1)
    if args.require_gate_exit and not report["gate_b_passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
