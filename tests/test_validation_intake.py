from __future__ import annotations

import json
from pathlib import Path

import pytest

from pne_scheduler.tools.compare_sch import compare_sch_files
from pne_scheduler.validate.intake import (
    INTAKE_SCHEMA_ID,
    validate_intake_file,
    validate_intake_metadata,
    validate_intake_with_compare_report,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "example" / "validation-intake.template.json"
CAPACHECK = (
    ROOT
    / "example"
    / "fixtures"
    / "capacheck_zip"
    / "9)Bimodal_SJ1300_6040_NCN_capacheck.sch"
)


def test_template_intake_metadata_is_valid_except_reopen_warning() -> None:
    result = validate_intake_file(TEMPLATE)
    assert result.valid
    assert any("ctspro_reopen_verified" in warning for warning in result.warnings)


def test_intake_rejects_executed_on_equipment() -> None:
    payload = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    payload["executed_on_equipment"] = True
    result = validate_intake_metadata(payload)
    assert not result.valid
    assert any("executed_on_equipment" in error for error in result.errors)


def test_intake_rejects_unknown_equipment_without_extra_errors() -> None:
    payload = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    payload["equipment"]["source"] = "unknown"
    result = validate_intake_metadata(payload)
    assert result.valid
    assert any("equipment.source is unknown" in warning for warning in result.warnings)


def test_intake_with_compare_report_flags_dirty_pair(tmp_path: Path) -> None:
    intake = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    intake["changed_step"] = 6
    intake["expected_field"] = "fEndV"
    intake["ctspro_reopen_verified"] = True

    before = CAPACHECK.read_bytes()
    after = bytearray(before)
    import struct

    struct.pack_into("<f", after, 1760 + 5 * 612 + 28, 3123.0)
    after_path = tmp_path / "after.sch"
    after_path.write_bytes(after)
    before_path = tmp_path / "before.sch"
    before_path.write_bytes(before)
    intake["before_file"] = before_path.name
    intake["after_file"] = after_path.name

    report = compare_sch_files(before_path, after_path)
    result = validate_intake_with_compare_report(intake, report)
    assert result.valid
    assert not any("not a clean single-field" in error for error in result.errors)


def test_intake_with_compare_report_rejects_multi_change_pair(tmp_path: Path) -> None:
    intake = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    intake["changed_step"] = 6

    before = CAPACHECK.read_bytes()
    after = bytearray(before)
    import struct

    for index, value in ((5, 3123.0), (6, 3124.0)):
        struct.pack_into("<f", after, 1760 + index * 612 + 28, value)
    after_path = tmp_path / "after.sch"
    after_path.write_bytes(after)
    before_path = tmp_path / "before.sch"
    before_path.write_bytes(before)

    report = compare_sch_files(before_path, after_path)
    result = validate_intake_with_compare_report(intake, report)
    assert not result.valid
    assert any("not a clean single-field" in error for error in result.errors)


def test_intake_schema_id_constant_matches_template() -> None:
    payload = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    assert payload["schema"] == INTAKE_SCHEMA_ID
