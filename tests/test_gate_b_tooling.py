from __future__ import annotations

import json
from pathlib import Path

from pne_scheduler.engine.c_rate import WRITER_Q_NOM_SOURCE
from pne_scheduler.schema.fields import FieldConfidence, get_step_field
from pne_scheduler.tools.compare_step_layouts import build_step_layout_diff_report
from pne_scheduler.tools.run_gate_b_validation import (
    _controlled_pair_evidence,
    _fixture_parser_checks,
)
from pne_scheduler.validate.assb_parser_diff import (
    build_assb_parser_diff_report,
    compare_fixture_parsers,
    offset_parity_summary,
)

ROOT = Path(__file__).resolve().parents[1]
HPPC = ROOT / "example" / "fixtures" / "hppc" / "HPPC_Full range.sch"


def test_step_layout_diff_report_has_samples() -> None:
    report = build_step_layout_diff_report()
    assert report["schema"] == "pne_scheduler.step_layout_diff/v1"
    assert report["sampled_step_records"]["612"] > 0
    assert report["sampled_step_records"]["696"] > 0
    assert report["extension_bytes"] == 84


def test_assb_offset_parity_summary_lists_divergences() -> None:
    summary = offset_parity_summary()
    assert summary["schema"] == "pne_scheduler.assb_offset_parity/v1"
    assert summary["documented_divergences"]
    assert summary["shared_pairs"]


def test_hppc_fixture_layout_matches_between_parsers() -> None:
    diff = compare_fixture_parsers(HPPC)
    assert diff.layout_match
    assert diff.step_count_match


def test_assb_parser_diff_report_on_representative_fixtures() -> None:
    catalog_fixtures = [
        ROOT / "example" / "fixtures" / "hppc" / "HPPC_Full range.sch",
        ROOT
        / "example"
        / "fixtures"
        / "capacheck_zip"
        / "9)Bimodal_SJ1300_6040_NCN_capacheck.sch",
    ]
    existing = [path for path in catalog_fixtures if path.is_file()]
    report = build_assb_parser_diff_report(existing)
    assert report["summary"]["fixture_count"] == len(existing)
    assert report["summary"]["layout_match_count"] == len(existing)


def test_writer_q_nom_contract_is_explicit_project_input() -> None:
    assert WRITER_Q_NOM_SOURCE == "cell_profile.nominal_capacity_mAh"
    policy = json.loads(
        (ROOT / "planning" / "Q_NOM_POLICY.json").read_text(encoding="utf-8")
    )
    assert policy["writer"]["source"] == WRITER_Q_NOM_SOURCE
    assert policy["writer"]["explicit_value_required"] is True
    assert policy["writer"]["allow_filename_inference"] is False
    assert policy["writer"]["allow_stack_geometry_inference"] is False


def test_corpus_evidence_matches_canonical_v612_registry() -> None:
    evidence = json.loads(
        (ROOT / "planning" / "GATE_B_CORPUS_EVIDENCE.json").read_text(encoding="utf-8")
    )
    assert evidence["schema"] == "pne_scheduler.gate_b_corpus_evidence/v1"
    assert evidence["scope"]["sch_files"] == 23281
    assert evidence["scope"]["parsed_files"] == 23275

    expected = {
        88: "loop_reset_flag",
        332: "record_dV_mV",
        340: "record_time_s",
        384: "dod_percent",
        496: "cap_mode",
        497: "cap_ref_step",
        564: "loop_goto_ensol",
    }
    for offset, name in expected.items():
        field = get_step_field(0x00010003, offset)
        assert field is not None
        assert field.name == name
        assert field.confidence == FieldConfidence.CORPUS_INFERRED
        assert field.writer_ready is False

    resolutions = evidence["assb_divergence_resolution"]
    assert resolutions["fSocRate"]["canonical_field"] == "dod_percent@384"
    assert resolutions["bUseActualCapa"]["canonical_field"] == "cap_mode@496"
    assert resolutions["bUseDataStepNo"]["canonical_field"] == "cap_ref_step@497"
    assert resolutions["nGotoStepID"]["status"] == "externally_unresolved"
    assert resolutions["fMaxCapacity"]["status"] == "externally_unresolved"


def test_controlled_pair_inventory_excludes_fillable_template() -> None:
    inventory = _controlled_pair_evidence()
    assert inventory["directory"] == "example/gate_b_pairs"
    assert inventory["valid_intake_count"] <= inventory["intake_count"]
    assert inventory["reopen_verified_count"] <= inventory["valid_intake_count"]
    assert inventory["complete_evidence_count"] <= inventory["valid_intake_count"]
    assert inventory["missing_required_fields"] == {}
    assert "PNE02" not in inventory["missing_required_fields"]
    assert "PNE16" not in inventory["missing_required_fields"]
    assert inventory["required_equipment_complete_count"] == inventory[
        "required_equipment_intake_count"
    ]
    assert inventory["evidence_policy"].get("screenshots_required") is False
    assert "loop_goto_ensol" in inventory["waived_required_fields"]["PNE02"]
    assert set(inventory["waived_required_fields"]["PNE16"]) == {"fIref", "fVref"}


def test_gate_b_parser_cross_check_covers_locked_fixture_catalog() -> None:
    checks = _fixture_parser_checks()
    assert len(checks["fixtures"]) == 102
    assert checks["all_layout_match"]
    assert checks["all_step_count_match"]
    assert checks["assb_summary"]["fixtures_with_field_mismatches"] == 0
