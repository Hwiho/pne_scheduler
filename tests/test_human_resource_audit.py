"""Bounded human-user audit of local files, imports, library, and storage.

Every writable resource in this module is rooted under pytest's ``tmp_path``.
The Windows notification callback is replaced with an in-process recorder; the
tests do not claim that Windows displayed a notification.
"""

from __future__ import annotations

import json
import struct
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pne_scheduler.api.routes import import_open
from pne_scheduler.ir import ModuleNode
from pne_scheduler.library import LIBRARY_SCHEMA, MethodLibrary
from pne_scheduler.storage_companion import main as companion_main
from pne_scheduler.storage_companion import process_due
from pne_scheduler.storage_records import StorageStore
from pne_scheduler.ui.document import ProjectDocument
from pne_scheduler.ui.workspace_model import WorkspaceModel


ROOT = Path(__file__).resolve().parents[1]
EDITABLE_SCH = (
    ROOT
    / "example"
    / "fixtures"
    / "capacheck_zip"
    / "07100766_260511_SJ1300_dry_40um_RPT_500cycle.sch"
)
NOW = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)


def _copy_editable_sch(tmp_path: Path) -> Path:
    copied = tmp_path / "editable.sch"
    copied.write_bytes(EDITABLE_SCH.read_bytes())
    return copied


def _synthetic_720_header(tmp_path: Path) -> Path:
    """Make a local 720-version probe without depending on private lab corpus.

    The payload remains the public fixture's layout, so this only tests version
    routing and the review-only safeguard, not semantic accuracy for real 720s.
    """
    raw = bytearray(EDITABLE_SCH.read_bytes())
    struct.pack_into("<I", raw, 4, 0x00010005)
    output = tmp_path / "review-only-720.sch"
    output.write_bytes(raw)
    return output


def _storage_row(**changes: object) -> dict[str, object]:
    return {
        "id": "audit_cell_01",
        "sample": "Audit Cell 01",
        "temperatureC": 45,
        "startedAt": (NOW - timedelta(days=2)).isoformat(),
        "targetDays": 1,
        "checkpointDays": [0.5],
        "notifyEnabled": True,
        **changes,
    }


def test_project_save_open_recovery_and_library_round_trip(tmp_path: Path) -> None:
    """A user's local project and reusable method survive fresh instances."""
    recovery_dir = tmp_path / "recovery"
    library = MethodLibrary(tmp_path / "library")
    document = ProjectDocument.new(autosave_dir=recovery_dir)
    document.apply(
        "휴지 추가",
        lambda project: project.modules.append(ModuleNode("rest_1", "rest", {})),
    )

    project_path = document.save(tmp_path / "audit.schproj")
    reopened = ProjectDocument.open(project_path, autosave_dir=recovery_dir)
    assert [node.id for node in reopened.project.modules] == ["rest_1"]
    assert not reopened.dirty

    reopened.apply("이름 변경", lambda project: setattr(project, "name", "복구할 실험"))
    autosave_path = reopened.autosave()
    assert autosave_path is not None and autosave_path.parent == recovery_dir
    snapshot = ProjectDocument.recoveries(recovery_dir)[0]
    recovered = ProjectDocument.recover(snapshot, autosave_dir=recovery_dir)
    assert recovered.project.name == "복구할 실험"
    assert recovered.dirty

    source = WorkspaceModel(recovered, library=library)
    saved = source.save_method("감사 휴지 방법")
    target = WorkspaceModel(
        ProjectDocument.new(autosave_dir=tmp_path / "target-recovery"),
        library=MethodLibrary(tmp_path / "library"),
    )
    loaded = target.load_saved_method(saved.method_id)
    assert loaded == ("rest_1",)
    assert [node.module_type for node in target.project.modules] == ["rest"]
    assert any(
        "검증되었다는 뜻은 아닙니다"
        in warning
        for warning in target.plan_method_load(library.latest(saved.method_id)).warnings
    )


def test_saving_recovered_work_consumes_the_original_recovery(tmp_path: Path) -> None:
    recovery_dir = tmp_path / "recovery"
    document = ProjectDocument.new(autosave_dir=recovery_dir)
    document.apply(
        "휴지 추가",
        lambda project: project.modules.append(ModuleNode("rest_1", "rest", {})),
    )
    document.autosave()
    snapshot = ProjectDocument.recoveries(recovery_dir)[0]

    recovered = ProjectDocument.recover(snapshot, autosave_dir=recovery_dir)
    recovered.save(tmp_path / "recovered.schproj")

    assert ProjectDocument.recoveries(recovery_dir) == ()


def test_recovered_save_cleans_its_snapshot_and_own_autosave_only(tmp_path: Path) -> None:
    recovery_dir = tmp_path / "source-recovery"
    document = ProjectDocument.new(autosave_dir=recovery_dir)
    document.apply("원본 이름", lambda project: setattr(project, "name", "original"))
    original = document.autosave()
    snapshot = ProjectDocument.recoveries(recovery_dir)[0]
    other = ProjectDocument.new(autosave_dir=recovery_dir)
    other.apply("다른 작업", lambda project: setattr(project, "name", "unrelated"))
    unrelated = other.autosave()
    unrelated_bytes = unrelated.read_bytes()

    recovered = ProjectDocument.recover(snapshot, autosave_dir=tmp_path / "target-recovery")
    own_autosave = recovered.autosave()
    recovered.save(tmp_path / "recovered.schproj")

    assert not original.exists()
    assert not own_autosave.exists()
    assert unrelated.read_bytes() == unrelated_bytes
    assert [item.autosave_path for item in ProjectDocument.recoveries(recovery_dir)] == [unrelated]


@pytest.mark.parametrize("replacement", ["newer-work", "format-only"])
def test_recovered_save_preserves_snapshot_replaced_since_recovery(
    tmp_path: Path, replacement: str
) -> None:
    recovery_dir = tmp_path / "recovery"
    document = ProjectDocument.new(autosave_dir=recovery_dir)
    document.apply("원본 이름", lambda project: setattr(project, "name", "original"))
    original = document.autosave()
    recovered = ProjectDocument.recover(
        ProjectDocument.recoveries(recovery_dir)[0], autosave_dir=recovery_dir
    )
    if replacement == "newer-work":
        document.apply("새 작업", lambda project: setattr(project, "name", "newer"))
        document.autosave()
    else:
        # Even semantically identical JSON must be preserved if its bytes changed.
        original.write_bytes(original.read_bytes() + b"\n")
    replacement_bytes = original.read_bytes()

    recovered.save(tmp_path / "recovered.schproj")
    recovered.save()

    assert not recovered.dirty
    assert original.read_bytes() == replacement_bytes


def test_failed_recovered_save_preserves_snapshot_until_a_successful_retry(tmp_path: Path) -> None:
    recovery_dir = tmp_path / "recovery"
    document = ProjectDocument.new(autosave_dir=recovery_dir)
    document.apply("원본 이름", lambda project: setattr(project, "name", "original"))
    original = document.autosave()
    original_bytes = original.read_bytes()
    recovered = ProjectDocument.recover(
        ProjectDocument.recoveries(recovery_dir)[0], autosave_dir=recovery_dir
    )
    blocked_parent = tmp_path / "not-a-directory"
    blocked_parent.write_text("existing file", encoding="utf-8")

    with pytest.raises(OSError):
        recovered.save(blocked_parent / "recovered.schproj")

    assert recovered.dirty
    assert original.read_bytes() == original_bytes
    recovered.save(tmp_path / "recovered.schproj")
    assert not original.exists()


def test_recovery_hash_binds_bytes_read_at_recovery_not_at_listing(tmp_path: Path) -> None:
    recovery_dir = tmp_path / "recovery"
    document = ProjectDocument.new(autosave_dir=recovery_dir)
    document.apply("원본 이름", lambda project: setattr(project, "name", "original"))
    original = document.autosave()
    snapshot = ProjectDocument.recoveries(recovery_dir)[0]
    document.apply("새 작업", lambda project: setattr(project, "name", "newer"))
    document.autosave()

    recovered = ProjectDocument.recover(snapshot, autosave_dir=recovery_dir)
    assert recovered.project.name == "newer"
    recovered.save(tmp_path / "recovered.schproj")

    assert not original.exists()


def test_one_malformed_library_entry_does_not_hide_valid_methods(tmp_path: Path) -> None:
    library = MethodLibrary(tmp_path / "library")
    valid = library.save(
        name="정상 방법",
        modules=[{"id": "rest_1", "module_type": "rest", "params": {}}],
    )
    malformed = library.root / "damaged" / "v0001.json"
    malformed.parent.mkdir(parents=True)
    malformed.write_text(
        json.dumps(
            {
                "schema": LIBRARY_SCHEMA,
                "method_id": "damaged",
                "version": "not-a-number",
                "name": "손상된 방법",
                "modules": [],
            }
        ),
        encoding="utf-8",
    )

    assert [entry.method_id for entry in library.methods()] == [valid.method_id]


def test_distinct_fallback_library_names_do_not_merge(tmp_path: Path) -> None:
    library = MethodLibrary(tmp_path / "library")
    modules = [{"id": "rest_1", "module_type": "rest", "params": {}}]

    fire = library.save(name="🔥", modules=modules)
    bolt = library.save(name="⚡", modules=modules)

    assert fire.method_id != bolt.method_id
    assert fire.version == bolt.version == 1


def test_import_explains_file_and_separates_staged_rejections(tmp_path: Path) -> None:
    source = _copy_editable_sch(tmp_path)
    session, info = import_open(str(source))

    assert info["stepCount"] == session.step_count > 0
    assert info["explanation"].strip()
    assert all(field["evidence"] for field in info["editableFields"])
    editable = info["editableFields"][0]["name"]

    session.stage(1, editable, 25.0)
    session.stage(1, "unverified_offset", 1.0)
    proposal = session.propose_patch()
    assert [(item.step_no, item.field) for item in proposal.accepted] == [(1, editable)]
    assert [item.field for item in proposal.rejected] == ["unverified_offset"]
    assert proposal.ok
    assert any("CTSPro 재열기 확인" in warning for warning in proposal.warnings)


def test_720_import_is_explainable_but_review_only(tmp_path: Path) -> None:
    source = _synthetic_720_header(tmp_path)
    session, info = import_open(str(source))

    assert session.sch_version == 0x00010005
    assert info["stepCount"] > 0
    assert info["editableFields"] == []
    assert info["explanation"].strip()

    session.stage(1, "fVref", 25.0)
    proposal = session.propose_patch()
    assert not proposal.ok
    assert proposal.plan is None
    assert "writer-ready" in proposal.rejected[0].reason


def test_storage_lifecycle_companion_payload_and_persistence(tmp_path: Path) -> None:
    database = tmp_path / "storage.sqlite3"
    store = StorageStore(database)
    store.add(_storage_row(), now=NOW)

    # Re-open through a fresh store to prove this is DB state, not object memory.
    persisted = StorageStore(database)
    checkpoint, final = persisted.list_records()[0]["alerts"]
    persisted.acknowledge_alert("audit_cell_01", checkpoint["id"], now=NOW)
    persisted.snooze_alert(
        "audit_cell_01",
        final["id"],
        (NOW + timedelta(hours=2)).isoformat(),
        now=NOW,
    )

    notices: list[tuple[str, str]] = []
    assert process_due(
        StorageStore(database),
        lambda title, message: notices.append((title, message)),
        now=NOW + timedelta(hours=1),
    ) == 0
    assert process_due(
        StorageStore(database),
        lambda title, message: notices.append((title, message)),
        now=NOW + timedelta(hours=2),
    ) == 1
    assert notices == [
        ("고온저장 최종 목표 시각 도달", "Audit Cell 01 · 45°C · 최종 목표 1일")
    ]

    record = StorageStore(database).list_records()[0]
    assert next(alert for alert in record["alerts"] if alert["id"] == checkpoint["id"])[
        "acknowledgedAt"
    ]
    assert next(alert for alert in record["alerts"] if alert["id"] == final["id"])[
        "notifiedAt"
    ]


def test_legacy_storage_import_is_persistent_and_opted_out(tmp_path: Path) -> None:
    database = tmp_path / "storage.sqlite3"
    imported = StorageStore(database).import_legacy([_storage_row()], now=NOW)

    assert imported == {"inserted": 1, "alreadyPresent": 0}
    record = StorageStore(database).list_records()[0]
    assert record["notifyEnabled"] is False
    assert process_due(
        StorageStore(database),
        lambda *_: pytest.fail("legacy import silently enabled notifications"),
        now=NOW,
    ) == 0


@pytest.mark.skipif(sys.platform == "win32", reason="non-Windows refusal only")
def test_companion_cli_refuses_non_windows_without_creating_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    database = tmp_path / "storage.sqlite3"

    with pytest.raises(SystemExit) as raised:
        companion_main(["--db", str(database), "--poll-seconds", "30"])

    assert raised.value.code == 2
    assert "Windows 사용자 세션에서만" in capsys.readouterr().err
    assert not database.exists()
