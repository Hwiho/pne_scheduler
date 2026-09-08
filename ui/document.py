"""Editing session state: undo/redo, dirty tracking, autosave, and recovery.

Every mutation goes through :meth:`ProjectDocument.apply`, which snapshots the
project first.  Snapshots are cheap here (a project is a small JSON document)
and they make undo exact — including edits that reshape the module list, where
an inverse-operation stack would be easy to get subtly wrong.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar

from ..ir.cell_profile import CellProfile
from ..ir.loader import ProjectLoad, load_project_lenient
from ..ir.project import ScheduleProject

T = TypeVar("T")

AUTOSAVE_SCHEMA = "pne_scheduler.autosave/v1"
UNDO_LIMIT = 100


def default_autosave_dir() -> Path:
    return Path.home() / ".pne_scheduler" / "recovery"


@dataclass(frozen=True, slots=True)
class RecoverySnapshot:
    autosave_path: Path
    saved_at: datetime
    project_name: str
    source_path: Path | None

    def describe(self) -> str:
        when = self.saved_at.strftime("%m월 %d일 %H:%M")
        where = str(self.source_path) if self.source_path else "저장된 적 없는 새 프로젝트"
        return f"{self.project_name} · {when} · {where}"


@dataclass(frozen=True, slots=True)
class UndoEntry:
    label: str
    snapshot: dict[str, Any]


def new_project(name: str = "새 스케줄") -> ScheduleProject:
    return ScheduleProject(
        name=name,
        cell_profile=CellProfile(
            nominal_capacity_mAh=24.0,
            v_max=4.2,
            v_min=2.5,
            max_current_mA=None,
        ),
    )


class ProjectDocument:
    """One open project plus its edit history."""

    def __init__(
        self,
        project: ScheduleProject,
        *,
        path: Path | None = None,
        autosave_dir: Path | None = None,
        load_repairs: tuple[str, ...] = (),
    ) -> None:
        self.project = project
        self.path = Path(path) if path else None
        self.autosave_dir = Path(autosave_dir) if autosave_dir else default_autosave_dir()
        self.load_repairs = load_repairs
        self.session_id = uuid.uuid4().hex[:12]
        self._undo: list[UndoEntry] = []
        self._redo: list[UndoEntry] = []
        self._saved_snapshot = project.to_dict()
        self._autosaved_snapshot: dict[str, Any] | None = None

    # ----------------------------------------------------------- lifecycle

    @classmethod
    def new(cls, *, autosave_dir: Path | None = None) -> ProjectDocument:
        return cls(new_project(), autosave_dir=autosave_dir)

    @classmethod
    def open(cls, path: Path, *, autosave_dir: Path | None = None) -> ProjectDocument:
        """Open leniently: a project with bad values still opens, with repairs."""
        load: ProjectLoad = load_project_lenient(Path(path))
        document = cls(
            load.project,
            path=Path(path),
            autosave_dir=autosave_dir,
            load_repairs=load.repairs,
        )
        if load.repairs:
            # Repairs changed the in-memory project, so it no longer matches the
            # file: mark it dirty rather than pretending it is saved.
            document._saved_snapshot = {}
        return document

    # -------------------------------------------------------------- state

    @property
    def dirty(self) -> bool:
        return self.project.to_dict() != self._saved_snapshot

    @property
    def title(self) -> str:
        base = self.path.name if self.path else "저장 안 된 새 프로젝트"
        return f"{'*' if self.dirty else ''}{base}"

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def undo_label(self) -> str:
        return self._undo[-1].label if self._undo else ""

    @property
    def redo_label(self) -> str:
        return self._redo[-1].label if self._redo else ""

    # ------------------------------------------------------------ editing

    def apply(self, label: str, mutator: Callable[[ScheduleProject], T]) -> T:
        """Run a mutation under one named undo entry.

        The mutation may raise; the project is restored and the exception is
        re-raised so a rejected edit never leaves half-applied state.
        """
        before = self.project.to_dict()
        try:
            result = mutator(self.project)
        except Exception:
            self._restore(before)
            raise
        after = self.project.to_dict()
        if after != before:
            self._push_undo(UndoEntry(label, before))
        return result

    @contextmanager
    def edit(self, label: str) -> Iterator[ScheduleProject]:
        """``with document.edit("이름 변경") as project:`` — same guarantees."""
        before = self.project.to_dict()
        try:
            yield self.project
        except Exception:
            self._restore(before)
            raise
        if self.project.to_dict() != before:
            self._push_undo(UndoEntry(label, before))

    def undo(self) -> str | None:
        if not self._undo:
            return None
        entry = self._undo.pop()
        current = self.project.to_dict()
        self._restore(entry.snapshot)
        self._redo.append(UndoEntry(entry.label, current))
        return entry.label

    def redo(self) -> str | None:
        if not self._redo:
            return None
        entry = self._redo.pop()
        current = self.project.to_dict()
        self._restore(entry.snapshot)
        self._undo.append(UndoEntry(entry.label, current))
        return entry.label

    def _push_undo(self, entry: UndoEntry) -> None:
        self._undo.append(entry)
        del self._undo[:-UNDO_LIMIT]
        self._redo.clear()

    def _restore(self, snapshot: dict[str, Any]) -> None:
        self.project = ScheduleProject.from_dict(snapshot)

    # ------------------------------------------------------------- saving

    def save(self, path: Path | None = None) -> Path:
        """Write the project. Never blocked by validation — that gates export."""
        target = Path(path) if path else self.path
        if target is None:
            raise ValueError("저장 경로가 필요합니다.")
        target.parent.mkdir(parents=True, exist_ok=True)
        self.project.save(target)
        self.path = target
        self._saved_snapshot = self.project.to_dict()
        self.load_repairs = ()
        self.clear_autosave()
        return target

    # ----------------------------------------------------------- autosave

    def autosave_path(self) -> Path:
        return self.autosave_dir / f"autosave-{self.session_id}.json"

    def autosave(self, *, force: bool = False) -> Path | None:
        """Write a recovery copy when there is something new to recover."""
        snapshot = self.project.to_dict()
        if not force and not self.dirty:
            return None
        if not force and snapshot == self._autosaved_snapshot:
            return None
        target = self.autosave_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": AUTOSAVE_SCHEMA,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "source_path": str(self.path) if self.path else None,
            "project": snapshot,
        }
        _atomic_write(target, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        self._autosaved_snapshot = snapshot
        return target

    def clear_autosave(self) -> None:
        target = self.autosave_path()
        try:
            target.unlink()
        except FileNotFoundError:
            pass
        self._autosaved_snapshot = None

    @staticmethod
    def recoveries(autosave_dir: Path | None = None) -> tuple[RecoverySnapshot, ...]:
        directory = Path(autosave_dir) if autosave_dir else default_autosave_dir()
        if not directory.is_dir():
            return ()
        found: list[RecoverySnapshot] = []
        for candidate in sorted(directory.glob("autosave-*.json")):
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if payload.get("schema") != AUTOSAVE_SCHEMA:
                continue
            project = payload.get("project") or {}
            try:
                saved_at = datetime.fromisoformat(payload.get("saved_at", ""))
            except ValueError:
                saved_at = datetime.fromtimestamp(candidate.stat().st_mtime)
            source = payload.get("source_path")
            found.append(
                RecoverySnapshot(
                    autosave_path=candidate,
                    saved_at=saved_at,
                    project_name=str(project.get("name", "이름 없는 프로젝트")),
                    source_path=Path(source) if source else None,
                )
            )
        return tuple(sorted(found, key=lambda item: item.saved_at, reverse=True))

    @classmethod
    def recover(
        cls,
        snapshot: RecoverySnapshot,
        *,
        autosave_dir: Path | None = None,
    ) -> ProjectDocument:
        payload = json.loads(snapshot.autosave_path.read_text(encoding="utf-8"))
        from ..ir.loader import repair_project_dict

        load = repair_project_dict(payload.get("project") or {})
        document = cls(
            load.project,
            path=snapshot.source_path,
            autosave_dir=autosave_dir,
            load_repairs=load.repairs,
        )
        # Recovered content is by definition unsaved work.
        document._saved_snapshot = {}
        return document

    @staticmethod
    def discard_recovery(snapshot: RecoverySnapshot) -> None:
        try:
            snapshot.autosave_path.unlink()
        except FileNotFoundError:
            pass


def _atomic_write(path: Path, text: str) -> None:
    handle, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".autosave-")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


__all__ = [
    "AUTOSAVE_SCHEMA",
    "ProjectDocument",
    "RecoverySnapshot",
    "default_autosave_dir",
    "new_project",
]
