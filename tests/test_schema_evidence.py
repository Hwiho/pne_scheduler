from __future__ import annotations

import json
import struct
from pathlib import Path

from pne_scheduler.schema.fields import (
    FieldConfidence,
    get_step_field,
    get_step_fields,
)
from pne_scheduler.schema.layouts import SCH_LAYOUTS
from pne_scheduler.tools.compare_sch import compare_sch_files

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


def test_controlled_diff_identifies_known_step_field(tmp_path: Path) -> None:
    before = CAPACHECK.read_bytes()
    after = bytearray(before)
    step_6_base = 1760 + 5 * 612
    struct.pack_into("<f", after, step_6_base + 28, 3123.0)

    after_path = tmp_path / "after.sch"
    after_path.write_bytes(after)
    report = compare_sch_files(CAPACHECK, after_path)

    assert report["compatible"] is True
    assert report["header_changes"] == []
    assert len(report["step_changes"]) == 1
    change = report["step_changes"][0]
    assert change["step_no"] == 6
    assert change["words"] == [
        {
            "offset": 28,
            "field": "fEndV",
            "confidence": "corpus_inferred",
            "before": {
                "hex": "00401c45",
                "uint32": 1159487488,
                "int32": 1159487488,
                "float32": 2500.0,
            },
            "after": {
                "hex": "00344345",
                "uint32": 1162023936,
                "int32": 1162023936,
                "float32": 3123.0,
            },
        }
    ]


def test_diff_refuses_to_align_incompatible_layouts() -> None:
    report = compare_sch_files(CAPACHECK, FORMATION_696)

    assert report["compatible"] is False
    assert report["warnings"]
    assert report["step_changes"] == []


def test_validation_intake_template_is_non_executing() -> None:
    template = json.loads(
        (ROOT / "example" / "validation-intake.template.json").read_text(
            encoding="utf-8"
        )
    )
    assert template["schema"] == "pne_scheduler.validation_intake/v1"
    assert template["executed_on_equipment"] is False
    assert template["ctspro_reopen_verified"] is False
