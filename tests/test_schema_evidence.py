from __future__ import annotations

import json
import struct
from pathlib import Path

from pne_scheduler.schema.fields import (
    FieldConfidence,
    get_step_field,
    get_step_fields,
    validate_step_field_registry,
)
from pne_scheduler.schema.layouts import SCH_LAYOUTS
from pne_scheduler.schema.v0x00010003_612 import VERIFIED_STEP_FIELDS
from pne_scheduler.tools.compare_sch import compare_sch_files
from pne_scheduler.io.sch_binary import read_sch_binary

ROOT = Path(__file__).resolve().parents[1]
CAPACHECK = (
    ROOT
    / "example"
    / "fixtures"
    / "capacheck_zip"
    / "9)Bimodal_SJ1300_6040_NCN_capacheck.sch"
)
FORMATION_696 = (
    ROOT
    / "example"
    / "fixtures"
    / "capacheck_zip"
    / "3.BM_C1%_FM.sch"
)


def test_partial_field_registry_is_valid_for_each_layout() -> None:
    assert validate_step_field_registry() == ()

    for version, layout in SCH_LAYOUTS.items():
        fields = get_step_fields(version)
        assert fields
        offsets = [field.offset for field in fields]
        assert len(offsets) == len(set(offsets))
        assert all(field.offset + field.size <= layout.step_size for field in fields)

    assert get_step_field(0x00010003, 28).name == "fEndV"
    assert (
        get_step_field(0x00010003, 36).confidence
        == FieldConfidence.SEMANTIC_UNVERIFIED
    )
    assert get_step_field(0x00010004, 600) is None


def test_legacy_v3_field_exports_are_derived_from_canonical_registry() -> None:
    canonical = get_step_fields(0x00010003)
    assert [
        (field.name, field.offset, field.dtype, field.size)
        for field in VERIFIED_STEP_FIELDS
    ] == [
        (field.name, field.offset, field.dtype, field.size)
        for field in canonical
    ]


def test_controlled_diff_identifies_known_step_field(tmp_path: Path) -> None:
    before = CAPACHECK.read_bytes()
    after = bytearray(before)
    doc = read_sch_binary(CAPACHECK)
    step_6_base = doc.payload_offset + 5 * doc.step_size
    struct.pack_into("<f", after, step_6_base + 28, 3123.0)

    after_path = tmp_path / "after.sch"
    after_path.write_bytes(after)
    report = compare_sch_files(CAPACHECK, after_path)

    assert report["schema"] == "pne_scheduler.sch_diff/v2"
    assert report["compatible"] is True
    assert report["header_changes"] == []
    assert len(report["step_changes"]) == 1
    change = report["step_changes"][0]
    assert change["step_no"] == 6
    assert len(change["words"]) == 1
    word = change["words"][0]
    assert word["offset"] == 28
    assert word["field"] == "fEndV"
    assert word["confidence"] == "corpus_inferred"
    assert word["dtype"] == "float32"
    assert word["writer_ready"] is True
    assert word["primary_before"] == 2500.0
    assert word["primary_after"] == 3123.0
    assert word["before"]["float32"] == 2500.0
    assert word["after"]["float32"] == 3123.0
    assert report["summary"]["controlled_pair_clean"] is True


def test_controlled_diff_warns_about_multiple_step_changes(tmp_path: Path) -> None:
    doc = read_sch_binary(CAPACHECK)
    after = bytearray(CAPACHECK.read_bytes())
    for index, value in ((5, 3123.0), (6, 3124.0)):
        struct.pack_into(
            "<f",
            after,
            doc.payload_offset + index * doc.step_size + 28,
            value,
        )
    after_path = tmp_path / "multiple.sch"
    after_path.write_bytes(after)

    report = compare_sch_files(CAPACHECK, after_path)

    assert report["summary"]["controlled_pair_clean"] is False
    assert (
        "A controlled pair should change exactly one step; found 2."
        in report["warnings"]
    )


def test_diff_uses_canonical_loop_field_registry(tmp_path: Path) -> None:
    doc = read_sch_binary(CAPACHECK)
    loop_index = next(index for index, step in enumerate(doc.steps) if step.is_loop)
    after = bytearray(CAPACHECK.read_bytes())
    offset = doc.payload_offset + loop_index * doc.step_size + 52
    struct.pack_into("<I", after, offset, 321)
    after_path = tmp_path / "loop.sch"
    after_path.write_bytes(after)

    report = compare_sch_files(CAPACHECK, after_path)

    word = report["step_changes"][0]["words"][0]
    assert word["field"] == "loop_count"
    assert word["primary_after"] == 321


def test_diff_refuses_to_align_incompatible_layouts() -> None:
    report = compare_sch_files(CAPACHECK, FORMATION_696)

    assert report["compatible"] is False
    assert report["warnings"]
    assert report["step_changes"] == []


def test_diff_refuses_to_align_changed_step_number_sequence(tmp_path: Path) -> None:
    after = bytearray(CAPACHECK.read_bytes())
    struct.pack_into("<i", after, 1760 + 5 * 612, 99)
    after_path = tmp_path / "renumbered.sch"
    after_path.write_bytes(after)

    report = compare_sch_files(CAPACHECK, after_path)

    assert report["compatible"] is False
    assert report["warnings"] == [
        "Step number sequences differ; step records were not aligned automatically."
    ]
    assert report["step_changes"] == []


def test_diff_reports_hashes_summary_and_unparsed_tail(tmp_path: Path) -> None:
    after_path = tmp_path / "with-tail.sch"
    after_path.write_bytes(CAPACHECK.read_bytes() + b"\x01")

    report = compare_sch_files(CAPACHECK, after_path)

    assert len(report["before"]["sha256"]) == 64
    assert len(report["after"]["sha256"]) == 64
    assert report["before"]["sha256"] != report["after"]["sha256"]
    assert report["summary"]["files_identical"] is False
    assert report["summary"]["unparsed_changed_byte_count"] == 1
    assert report["unparsed_tail_changes"] == [
        {
            "start": 0,
            "end_exclusive": 1,
            "length": 1,
            "before_hex": "",
            "after_hex": "01",
        }
    ]


def test_validation_intake_template_is_non_executing() -> None:
    template = json.loads(
        (ROOT / "example" / "validation-intake.template.json").read_text(
            encoding="utf-8"
        )
    )
    assert template["schema"] == "pne_scheduler.validation_intake/v1"
    assert template["executed_on_equipment"] is False
    assert template["ctspro_reopen_verified"] is False
