from __future__ import annotations

from pathlib import Path

from pne_scheduler.tools.compare_step_layouts import build_step_layout_diff_report
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
