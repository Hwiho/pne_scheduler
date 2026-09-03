from __future__ import annotations

import json
from pathlib import Path

from pne_scheduler.io.validation_manifest import (
    VALIDATION_MANIFEST_SCHEMA,
    experimental_build_manifest,
    validate_manifest,
)
from pne_scheduler.schema.fields import get_writer_ready_fields
from pne_scheduler.tools.rescale_sch_current import main as rescale_main

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "example" / "example.schproj"
CAPACHECK = (
    ROOT
    / "example"
    / "fixtures"
    / "capacheck_zip"
    / "9)Bimodal_SJ1300_6040_NCN_capacheck.sch"
)


def test_manifest_validator_accepts_experimental_build(tmp_path: Path) -> None:
    output = tmp_path / "output.sch"
    output.write_bytes(b"nonempty")
    manifest = experimental_build_manifest(
        PROJECT,
        output,
        sch_version=0x00010003,
        cell_profile={"nominal_capacity_mAh": 80.0},
    )

    assert manifest["schema"] == VALIDATION_MANIFEST_SCHEMA
    assert validate_manifest(manifest) == ()


def test_manifest_validator_reports_missing_required_fields() -> None:
    errors = validate_manifest({"schema": VALIDATION_MANIFEST_SCHEMA})

    assert "writer: required" in errors
    assert "output: required object" in errors
    assert "validation: required object" in errors


def test_writer_ready_allowlist_matches_gate_b_controlled_pairs() -> None:
    expected = {
        "fVref",
        "fIref",
        "fEndV",
        "fEndI",
        "loop_target",
        "loop_count",
        "record_time_s",
    }
    assert set(get_writer_ready_fields(0x00010002)) == expected
    assert set(get_writer_ready_fields(0x00010003)) == expected
    # 696 layout: shared-prefix Gate B fields only (no record_time_s until C6 registry).
    assert set(get_writer_ready_fields(0x00010004)) == {
        "fVref",
        "fIref",
        "fEndV",
        "fEndI",
        "loop_target",
        "loop_count",
    }

def test_current_rescaler_writes_validation_manifest(tmp_path: Path) -> None:
    output = tmp_path / "rescaled.sch"

    result = rescale_main(
        [
            str(CAPACHECK),
            str(output),
            "76.55",
            "153.1",
        ]
    )

    assert result == 0
    manifest_path = output.with_suffix(".sch.manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["writer"] == "current_rescaler"
    assert manifest["template"]["sha256"]
    assert manifest["changed_fields"]
    assert manifest["validation"]["all_passed"] is True
    assert manifest["equipment_executable"] is False
