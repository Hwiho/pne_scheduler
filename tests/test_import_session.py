"""Opening an existing .sch: patch keeps the bytes, clone admits it does not."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from pne_scheduler.import_session import ImportSession
from pne_scheduler.io.template_writer import apply_sch_patch

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "example"
    / "fixtures"
    / "capacheck_zip"
    / "07100766_260511_SJ1300_dry_40um_RPT_500cycle.sch"
)


@pytest.fixture()
def session() -> ImportSession:
    return ImportSession.open(FIXTURE)


def test_opening_records_the_bytes_and_their_digest(session):
    assert session.raw == FIXTURE.read_bytes()
    assert session.sha256 == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert session.step_count > 0
    assert session.source_unchanged()


def test_only_writer_ready_fields_are_offered(session):
    """Evidence-promoted offsets only — the rest have no proven meaning."""
    from pne_scheduler.schema.fields import get_writer_ready_fields

    offered = {item.name for item in session.editable_fields()}
    assert offered == set(get_writer_ready_fields(session.sch_version))
    assert offered, "the fixture's version has no writable fields at all"
    assert all(item.evidence for item in session.editable_fields())


def test_an_unproven_field_is_refused(session):
    session.stage(1, "some_unproven_offset", 1.0)
    proposal = session.propose_patch()
    assert not proposal.accepted
    assert proposal.plan is None
    assert any("writer-ready" in item.reason for item in proposal.rejected)


def test_a_step_outside_the_file_is_refused(session):
    field_name = session.editable_fields()[0].name
    session.stage(session.step_count + 1, field_name, 1.0)
    proposal = session.propose_patch()
    assert not proposal.accepted
    assert any("범위를 벗어납니다" in item.reason for item in proposal.rejected)


def test_good_and_bad_edits_are_separated_not_all_or_nothing(session):
    field_name = session.editable_fields()[0].name
    session.stage(2, field_name, 25.0)
    session.stage(2, "not_a_real_field", 1.0)
    proposal = session.propose_patch()
    assert len(proposal.accepted) == 1 and len(proposal.rejected) == 1
    assert proposal.ok


def test_the_plan_is_bound_to_the_bytes_that_were_read(session):
    session.stage(2, session.editable_fields()[0].name, 25.0)
    proposal = session.propose_patch()
    assert proposal.plan.template_sha256 == session.sha256
    assert proposal.plan.expected_version == session.sch_version


def test_patching_changes_only_the_targeted_bytes(session, tmp_path):
    """The point of the whole session: everything not edited stays identical."""
    session.stage(3, "fVref", 25.0)
    proposal = session.propose_patch()

    output = tmp_path / "patched.sch"
    apply_sch_patch(FIXTURE, proposal.plan, output, allow_analysis_output=True)

    before, after = FIXTURE.read_bytes(), output.read_bytes()
    assert len(before) == len(after)
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert changed, "the edit did not reach the file"
    assert len(changed) <= 4, f"{len(changed)} bytes changed for one float field"
    assert before[:1760] == after[:1760], "the CTSPro header must survive untouched"


def test_a_source_edited_underneath_the_session_is_reported(session, tmp_path):
    copy = tmp_path / "copy.sch"
    copy.write_bytes(FIXTURE.read_bytes())
    moving = ImportSession.open(copy)
    copy.write_bytes(FIXTURE.read_bytes() + b"\x00")

    assert not moving.source_unchanged()
    moving.stage(2, moving.editable_fields()[0].name, 25.0)
    assert any("바뀌었습니다" in warning for warning in moving.propose_patch().warnings)


def test_the_patch_result_still_is_not_equipment_ready(session):
    session.stage(2, session.editable_fields()[0].name, 25.0)
    warnings = " ".join(session.propose_patch().warnings)
    assert "CTSPro 재열기 확인" in warnings


def test_cloning_names_what_it_throws_away(session):
    clone = session.propose_clone()
    assert clone.ok and len(clone.steps) == session.step_count
    dropped = " ".join(clone.dropped)
    assert "헤더" in dropped and "SHA-256" in dropped
    assert any("원본을 고치는 방법이 아니며" in w for w in clone.warnings)


def test_staged_edits_can_be_cleared(session):
    session.stage(2, session.editable_fields()[0].name, 25.0)
    session.clear()
    assert not session.propose_patch().accepted
