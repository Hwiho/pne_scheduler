"""Release labels, and the hash binding that keeps them honest."""

from __future__ import annotations

from pne_scheduler.release import evaluate_release
from pne_scheduler.ui.document import ProjectDocument
from pne_scheduler.release_labels import (
    LABEL_LADDER,
    label_for,
    label_rank,
)

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


def test_the_ladder_climbs_one_human_step_at_a_time():
    assert label_for(software_ok=False, ctspro_reviewed=True, equipment_approved=True).label == (
        "analysis-only"
    )
    assert label_for(
        software_ok=True, ctspro_reviewed=False, equipment_approved=False
    ).label == "software-checked"
    assert label_for(
        software_ok=True, ctspro_reviewed=True, equipment_approved=False
    ).label == "CTSPro-reopen-verified"
    assert label_for(
        software_ok=True, ctspro_reviewed=True, equipment_approved=True
    ).label == "equipment-verified"


def test_only_the_top_label_is_equipment_executable():
    for label in LABEL_LADDER[:-1]:
        assert label_rank(label) < label_rank("equipment-verified")
    decision = label_for(software_ok=True, ctspro_reviewed=True, equipment_approved=True)
    assert decision.equipment_executable
    assert not label_for(
        software_ok=True, ctspro_reviewed=True, equipment_approved=False
    ).equipment_executable


def test_an_approval_does_not_travel_to_a_different_file():
    """Editing after review must not carry the review forward."""
    decision = label_for(
        software_ok=True,
        ctspro_reviewed=True,
        equipment_approved=True,
        reviewed_sha256=DIGEST_A,
        artifact_sha256=DIGEST_B,
    )
    assert decision.label == "software-checked"
    assert decision.digest_mismatch
    assert not decision.equipment_executable
    assert any("해시" in reason for reason in decision.reasons)


def test_a_matching_digest_keeps_the_approval():
    decision = label_for(
        software_ok=True,
        ctspro_reviewed=True,
        equipment_approved=True,
        reviewed_sha256=DIGEST_A,
        artifact_sha256=DIGEST_A,
    )
    assert decision.label == "equipment-verified"
    assert not decision.digest_mismatch


def test_an_approval_with_no_recorded_hash_cannot_claim_a_file():
    """"Reviewed" with nothing to compare against is not evidence about this file."""
    decision = label_for(
        software_ok=True,
        ctspro_reviewed=True,
        equipment_approved=True,
        reviewed_sha256="",
        artifact_sha256=DIGEST_A,
    )
    assert decision.label == "software-checked"
    assert any("확인할 수 없습니다" in reason for reason in decision.reasons)


def test_every_label_says_what_it_means():
    for label in LABEL_LADDER:
        decision = label_for(
            software_ok=label != "analysis-only",
            ctspro_reviewed=label_rank(label) >= label_rank("CTSPro-reopen-verified"),
            equipment_approved=label == "equipment-verified",
        )
        assert decision.label_ko and decision.meaning_ko


def test_the_manifest_fields_match_the_decision():
    decision = label_for(software_ok=True, ctspro_reviewed=False, equipment_approved=False)
    fields = decision.as_manifest_fields()
    assert fields["release_label"] == "software-checked"
    assert fields["equipment_executable"] is False
    assert isinstance(fields["release_label_reasons"], list)


def test_release_state_carries_a_label():
    state = evaluate_release(ProjectDocument.new().project)
    assert state.label is not None
    assert state.label.label in LABEL_LADDER
