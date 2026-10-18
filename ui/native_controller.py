"""Offline presentation adapter over the same application operations as HTTP.

No Tk, Flask, socket, or server is needed here. History and local recovery belong
to the desktop session; protocol calculations and export gates remain shared.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..api import routes
from ..edit.steps import step_fields
from ..ir.project import ScheduleProject
from ..library import MethodLibrary
from ..storage_records import StorageStore, default_storage_db
from .document import ProjectDocument


class NativeController:
    def __init__(self, initial_path: Path | None = None, *, data_dir: Path | None = None):
        self.data_dir = Path(data_dir).expanduser().resolve() if data_dir else None
        self.autosave_dir = self.data_dir / "recovery" if self.data_dir else None
        self.library = MethodLibrary(self.data_dir / "library" if self.data_dir else None)
        self.storage = StorageStore(self.data_dir / "storage.sqlite3" if self.data_dir else default_storage_db())
        self.document = (ProjectDocument.open(initial_path, autosave_dir=self.autosave_dir)
                         if initial_path else ProjectDocument.new(autosave_dir=self.autosave_dir))
        self.selected: str | None = None
        self.revision = 0
        self.views: dict[str, Any] = {}
        self.notice = ""
        self.import_session = None
        self.refresh()

    @property
    def project(self) -> dict[str, Any]:
        return self.document.project.to_dict()

    def _payload(self, args=None) -> dict[str, Any]:
        return {"project": self.project, "selected": self.selected, "args": args or {}}

    def _metadata(self):
        self.views.update(title=self.document.title, dirty=self.document.dirty)
        self.selected = self.views.get("selectedModule")

    def refresh(self):
        self.views = routes.views(self._payload())["views"]
        self._metadata()
        return self.views

    def _autosave(self):
        try:
            self.document.autosave()
            self.notice = ""
        except OSError as exc:
            # An edit is already committed. Do not report it as rejected or lose
            # the undo history just because the recovery disk is unavailable.
            self.notice = f"자동 복구 저장 실패 — 직접 저장해 주세요: {exc}"

    def edit(self, action: str, args=None):
        result = routes.transform(action, self._payload(args), library=self.library)
        before = self.project
        after = ScheduleProject.from_dict(result["project"])
        self.document.apply(result.get("label", action), lambda _: setattr(self.document, "project", after))
        if before != self.project:
            self.revision += 1
            self._autosave()
        self.views = result["views"]
        self._metadata()
        return result

    def plan(self, action: str, args=None):
        return routes.plan(action, self._payload(args))

    def select(self, module_id: str | None):
        self.selected = module_id
        return self.refresh()

    def undo(self):
        if self.document.can_undo:
            self.document.undo()
            self.revision += 1
            self._autosave()
        return self.refresh()

    def redo(self):
        if self.document.can_redo:
            self.document.redo()
            self.revision += 1
            self._autosave()
        return self.refresh()

    def open(self, path: Path):
        new = ProjectDocument.open(path, autosave_dir=self.autosave_dir)
        self.preserve_unsaved()
        self.document = new
        self.selected = None
        self.revision += 1
        return self.refresh()

    def new(self):
        self.preserve_unsaved()
        self.document = ProjectDocument.new(autosave_dir=self.autosave_dir)
        self.selected = None
        self.revision += 1
        return self.refresh()

    def save(self, path: Path | None = None):
        result = self.document.save(path)
        self.notice = ""
        self._metadata()
        return result

    def recoveries(self):
        return ProjectDocument.recoveries(self.autosave_dir)

    def recover(self, snapshot):
        self.preserve_unsaved()
        self.document = ProjectDocument.recover(snapshot, autosave_dir=self.autosave_dir)
        self.selected = None
        self.revision += 1
        return self.refresh()

    def preserve_unsaved(self):
        """A failed recovery write may not discard the only edited document."""
        self.document.autosave()
        self.notice = ""

    def module_content(self, module_id, child_index=None):
        return routes.module_content({**self._payload(), "moduleId": module_id, "childIndex": child_index})

    def step_fields(self, module_id, index, child_index=None):
        node = next(n for n in self.document.project.modules if n.id == module_id)
        if child_index is not None:
            from ..ir.project import ModuleNode
            node = ModuleNode.from_dict(node.params["children"][child_index])
        raw = node.params["steps"][index]
        return [{"key": f.key, "label": f.label, "kind": f.kind, "text": f.text,
                 "value": f.text, "numericValue": f.numeric_value, "detail": f.detail}
                for f in step_fields(raw, nominal_capacity_mAh=self.document.project.cell_profile.nominal_capacity_mAh)]

    def export(self, kind, out_dir):
        return routes.export({**self._payload(), "kind": kind, "outDir": str(out_dir)})

    def export_batch(self, args, token, out_dir):
        return routes.export_batch({**self._payload(args), "token": token, "outDir": str(out_dir)})

    def library_preview(self, method_id, version, replace=False, compare_version=None):
        return routes.library_load(self.library, {**self._payload(), "methodId": method_id,
            "version": version, "replace": replace, "compareVersion": compare_version, "preview": True})

    def save_method(self, name, description="", module_ids=None):
        return routes.library_save(self.library, {**self._payload(), "name": name,
            "description": description, "moduleIds": module_ids})

    def import_open(self, path):
        session, info = routes.import_open(str(path))
        self.import_session = session
        return info

    def _import(self):
        if self.import_session is None:
            raise ValueError("먼저 SCH 파일을 여세요.")
        return self.import_session

    def import_stage(self, step_no, field, value):
        return routes.import_stage(self._import(), {"stepNo": step_no, "field": field, "value": value})

    def import_clear(self):
        return routes.import_clear(self._import())

    def import_patch(self, output_path):
        return routes.import_patch(self._import(), {"outputPath": str(output_path), "allowAnalysisOutput": True})
