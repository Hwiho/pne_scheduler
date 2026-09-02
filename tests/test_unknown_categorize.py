from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from pne_scheduler.classify.training_labels import (
    VERIFIED_LABELS_SCHEMA,
    classify_with_verified_labels,
    load_verified_labels,
    save_verified_labels,
)
from pne_scheduler.classify.unknown_categorize import (
    build_signature_model,
    merge_suggestions,
    probe_filename,
    suggest_from_filename_probes,
    suggest_from_signature,
    tokenize_filename,
)

FIXTURE_ZIP = Path(__file__).resolve().parents[1] / "example" / "fixtures" / "capacheck_zip"


def test_tokenize_filename_splits_on_separators() -> None:
    tokens = tokenize_filename("07000872_250325_JHY_0_L1_L6_initial_check_28.sch")
    assert "initial" in tokens
    assert "check" in tokens


def test_probe_filename_detects_initial_check() -> None:
    hits = probe_filename("07000872_250325_JHY_0_L1_L6_initial_check_28.sch")
    labels = [h[0] for h in hits]
    assert "initial_check" in labels


def test_signature_model_suggests_dominant_category() -> None:
    labeled = [
        ("cycle_life", "CCCV-REST-LOOP-END"),
        ("cycle_life", "CCCV-REST-LOOP-END"),
        ("rate_test", "CC_CHG-CC_DCHG-END"),
    ]
    model = build_signature_model(labeled, min_votes=1)
    cat, conf, method, votes = suggest_from_signature("CCCV-REST-LOOP-END", model)
    assert cat == "cycle_life"
    assert conf == 1.0
    assert method == "binary_signature"
    assert votes[0].count == 2


def test_merge_prefers_high_confidence_signature() -> None:
    cat, conf, method = merge_suggestions(
        "cycle_life",
        0.85,
        "binary_signature",
        "rate_test",
        0.55,
        "filename_probe:c_rate_token",
    )
    assert cat == "cycle_life"
    assert conf == 0.85


def test_filename_probe_suggests_capacheck() -> None:
    cat, conf, method = suggest_from_filename_probes(
        [("initial_check", "capacheck")]
    )
    assert cat == "capacheck"
    assert conf == 0.55
    assert method.startswith("filename_probe:")


def test_verified_labels_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "verified.json"
    save_verified_labels(path, {"foo.sch": "formation"}, note="test")
    loaded = load_verified_labels(path)
    assert loaded["foo.sch"] == "formation"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema"] == VERIFIED_LABELS_SCHEMA


def test_build_unit_review_priority_shape() -> None:
    from pne_scheduler.classify.unknown_categorize import (
        UnknownSchRecord,
        build_unit_review_priority,
    )

    rec = UnknownSchRecord(
        unit="PNE04",
        zip_path="z",
        archive_path="a/x.sch",
        stem="x.sch",
        step_signature="CCCV-END",
        step_count=2,
        loop_steps=0,
        current_mA_max=10.0,
        filename_probes=(),
        filename_tokens=("dry", "1818"),
        suggested_category="formation",
        confidence=0.8,
        method="binary_signature",
        matched_rule="none",
        signature_votes=(),
    )
    review = build_unit_review_priority("PNE04", [rec])
    assert review["unit"] == "PNE04"
    assert review["unknown_count"] == 1
    assert review["review_clusters"]

    match = classify_with_verified_labels(
        "totally_opaque_name.sch",
        {"totally_opaque_name.sch": "hppc"},
    )
    assert match.category.value == "hppc"
    assert match.matched_rule == "verified_label"
