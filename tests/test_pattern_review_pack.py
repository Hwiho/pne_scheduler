from __future__ import annotations

import json
import csv
from pathlib import Path

from pne_scheduler.io.reader import read_sch
from pne_scheduler.io.validation_manifest import validate_manifest
from pne_scheduler.tools.pattern_review_pack import (
    CANDIDATE_NAME,
    PATTERN_RECIPES,
    build_pattern_review_pack,
)


def test_pattern_review_pack_is_complete_and_reopen_only(tmp_path: Path) -> None:
    output = tmp_path / "pack"
    result = build_pattern_review_pack(output)

    assert result.pattern_count == len(PATTERN_RECIPES) == 10
    assert (output / "INDEX.md").is_file()
    assert (output / "review_results.csv").is_file()
    assert (output / "pack_manifest.json").is_file()
    assert read_sch(output / "PV-QPEED-F" / CANDIDATE_NAME).step_count == 167
    assert read_sch(output / "PV-HPPC" / CANDIDATE_NAME).step_count == 62
    assert read_sch(output / "PV-QC-C" / CANDIDATE_NAME).step_count == 25

    with (output / "review_results.csv").open(encoding="utf-8", newline="") as handle:
        review_rows = {row["pattern_id"]: row for row in csv.DictReader(handle)}
    assert review_rows["PV-HPPC"]["candidate_sha256"] == result.candidate_hashes["PV-HPPC"]

    for recipe in PATTERN_RECIPES:
        pattern_dir = output / recipe.pattern_id
        assert (pattern_dir / "source.schproj").is_file()
        assert (pattern_dir / "expected_steps.csv").is_file()
        assert (pattern_dir / "expected_overview.md").is_file()
        manifest = json.loads(
            (pattern_dir / f"{CANDIDATE_NAME}.manifest.json").read_text(
                encoding="utf-8"
            )
        )
        assert validate_manifest(manifest) == ()
        assert manifest["status"] == "CTSPro-reopen-candidate"
        assert manifest["equipment_executable"] is False
        assert manifest["validation"]["equipment_smoke_test"] == "not_run"


def test_pattern_review_pack_keeps_existing_review_results(tmp_path: Path) -> None:
    output = tmp_path / "pack"
    build_pattern_review_pack(output)
    review = output / "review_results.csv"
    review.write_text("user-entered-result\n", encoding="utf-8")

    build_pattern_review_pack(output)

    assert review.read_text(encoding="utf-8") == "user-entered-result\n"
