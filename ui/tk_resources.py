"""Tk resource panels for saved methods, guarded exports, and SCH imports.

The native UI deliberately calls the same controller/routes as the web UI.
It does not reproduce release decisions locally: it only renders serialized
views and submits the exact preview/apply payloads accepted by ``api.routes``.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Any, Callable

from .tk_widgets import ScrollFrame


MAX_MATRIX_VARIANTS = 25
LOAD_MODES = {"현재 실험에 추가": "append", "프로토콜 교체": "replace"}
BATCH_PHASES = {"Formation": "formation", "Derating": "derating", "사이클": "cycle"}
BATCH_KINDS = {"미리보기 파일": "preview", "SCH 검토 후보": "review_candidate"}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else list(value) if isinstance(value, tuple) else []


def _set_readonly_text(widget: tk.Text, text: str) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", text)
    widget.configure(state="disabled")


def _summary_lines(result: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.extend(str(item) for item in _list(result.get("notes")) if item)
    lines.extend(f"주의: {item}" for item in _list(result.get("warnings")) if item)
    lines.extend(f"오류: {item}" for item in _list(result.get("errors")) if item)
    impact = _dict(result.get("impact"))
    if impact:
        lines.append("")
        lines.append("현재 실험에 적용하면")
        lines.append(str(impact.get("headline", "")))
        if impact.get("note"):
            lines.append(str(impact["note"]))
        lines.extend(f"· {item}" for item in _list(impact.get("lines")))
    version_diff = _dict(result.get("versionDiff"))
    if version_diff:
        lines.append("")
        lines.append(
            f"저장 버전 비교 · v{version_diff.get('baseVersion', '—')} → "
            f"v{version_diff.get('headVersion', '—')}"
        )
        lines.append(str(version_diff.get("headline", "")))
        lines.extend(f"· {item}" for item in _list(version_diff.get("lines")))
        lines.extend(f"· {item}" for item in _list(version_diff.get("metadataChanges")))
    elif result:
        lines.extend(("", "비교할 이전 저장 버전이 없습니다."))
    if result:
        lines.extend(("", "비교는 같은 입력 기준용량의 스텝 조건 기준이며 실제 장비 결과 비교가 아닙니다."))
    return "\n".join(lines).strip()


class LibraryPanel(ttk.Frame):
    """Versioned method library with explicit preview-before-apply."""

    def __init__(self, parent: tk.Misc, app: Any) -> None:
        super().__init__(parent)
        self.app = app
        self._busy = False
        self._methods: list[dict[str, Any]] = []
        self._versions: dict[str, list[dict[str, Any]]] = {}
        self._preview: dict[str, Any] | None = None
        self._interactive: list[tk.Widget] = []

        scroll = ScrollFrame(self)
        scroll.pack(fill="both", expand=True)
        body = scroll.body
        body.columnconfigure(0, weight=1)

        ttk.Label(body, text="내 블록 · 저장된 방법", style="Heading.TLabel").grid(
            row=0, column=0, sticky="w", padx=14, pady=(14, 2)
        )
        ttk.Label(
            body,
            text="과거 버전과 변경 내용을 검토한 뒤 적용합니다. 현재 셀 용량과 장비 설정은 유지됩니다.",
            wraplength=720,
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))

        browser = ttk.LabelFrame(body, text="저장된 방법 불러오기")
        browser.grid(row=2, column=0, sticky="ew", padx=14, pady=6)
        browser.columnconfigure(1, weight=1)

        self.method_var = tk.StringVar()
        self.version_var = tk.StringVar()
        self.compare_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="현재 실험에 추가")
        self.method_box = ttk.Combobox(browser, textvariable=self.method_var, state="readonly")
        self.version_box = ttk.Combobox(browser, textvariable=self.version_var, state="readonly", width=20)
        self.compare_box = ttk.Combobox(browser, textvariable=self.compare_var, state="readonly", width=20)
        self.mode_box = ttk.Combobox(
            browser,
            textvariable=self.mode_var,
            values=tuple(LOAD_MODES),
            state="readonly",
            width=16,
        )
        labels = ("저장된 블록", "불러올 버전", "비교 기준", "적용 방식")
        widgets = (self.method_box, self.version_box, self.compare_box, self.mode_box)
        for row, (label, widget) in enumerate(zip(labels, widgets, strict=True)):
            ttk.Label(browser, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=5)
            widget.grid(row=row, column=1, sticky="ew", padx=8, pady=5)
        self._interactive.extend(widgets)

        self.method_box.bind("<<ComboboxSelected>>", self._method_changed)
        for widget in (self.version_box, self.compare_box, self.mode_box):
            widget.bind("<<ComboboxSelected>>", self._selection_changed)

        actions = ttk.Frame(browser)
        actions.grid(row=4, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        self.reload_button = ttk.Button(actions, text="저장 목록 새로고침", command=self._load_library)
        self.preview_button = ttk.Button(actions, text="방법 변경 미리보기", command=self._preview_method)
        self.apply_button = ttk.Button(actions, text="검토한 방법 적용", command=self._apply_method)
        self.reload_button.pack(side="left")
        self.preview_button.pack(side="left", padx=6)
        self.apply_button.pack(side="left")
        self._interactive.extend((self.reload_button, self.preview_button, self.apply_button))

        self.method_meta = ttk.Label(browser, text="저장 목록을 불러오세요.", wraplength=690)
        self.method_meta.grid(row=5, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 8))
        self.replace_warning = ttk.Label(
            browser,
            text="교체는 현재 구간 전체를 바꿉니다. 적용 뒤에는 프로젝트 되돌리기로 복원할 수 있습니다.",
            foreground="#9b4b23",
            wraplength=690,
        )

        preview_frame = ttk.LabelFrame(body, text="변경 검토")
        preview_frame.grid(row=3, column=0, sticky="nsew", padx=14, pady=6)
        preview_frame.columnconfigure(0, weight=1)
        self.preview_text = tk.Text(preview_frame, height=15, wrap="word", state="disabled")
        preview_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview_text.yview)
        self.preview_text.configure(yscrollcommand=preview_scroll.set)
        self.preview_text.grid(row=0, column=0, sticky="nsew")
        preview_scroll.grid(row=0, column=1, sticky="ns")

        save = ttk.LabelFrame(body, text="현재 실험을 새 버전으로 저장")
        save.grid(row=4, column=0, sticky="ew", padx=14, pady=(6, 14))
        save.columnconfigure(1, weight=1)
        self.save_name = tk.StringVar()
        self.save_description = tk.StringVar()
        self.save_scope = tk.StringVar(value="project")
        ttk.Label(save, text="이름").grid(row=0, column=0, sticky="w", padx=8, pady=5)
        name_entry = ttk.Entry(save, textvariable=self.save_name)
        name_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=5)
        ttk.Label(save, text="설명").grid(row=1, column=0, sticky="w", padx=8, pady=5)
        desc_entry = ttk.Entry(save, textvariable=self.save_description)
        desc_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=5)
        scope = ttk.Frame(save)
        scope.grid(row=2, column=0, columnspan=2, sticky="w", padx=8, pady=5)
        project_radio = ttk.Radiobutton(scope, text="프로젝트 전체", variable=self.save_scope, value="project")
        selected_radio = ttk.Radiobutton(scope, text="선택한 모듈만", variable=self.save_scope, value="selected")
        project_radio.pack(side="left")
        selected_radio.pack(side="left", padx=12)
        save_button = ttk.Button(save, text="내 라이브러리에 저장", command=self._save_method)
        save_button.grid(row=3, column=0, columnspan=2, sticky="w", padx=8, pady=8)
        self._interactive.extend((name_entry, desc_entry, project_radio, selected_radio, save_button))

        self._update_controls()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._update_controls()

    def refresh(self) -> None:
        """Redraw project-dependent state without doing disk work."""
        if self._preview and self._preview.get("revision") != self.app.revision:
            self._clear_preview("프로젝트가 바뀌어 이전 미리보기를 폐기했습니다.")
        self._update_controls()

    def _signature(self) -> tuple[str, str, str, str]:
        return (
            self.method_var.get(),
            self.version_var.get(),
            self.compare_var.get(),
            self.mode_var.get(),
        )

    def _load_library(self) -> None:
        if self._busy or self.app.busy:
            return

        def work() -> dict[str, Any]:
            from ..api.routes import library_list, library_versions

            methods = library_list(self.app.controller.library).get("methods", [])
            versions = {
                str(item.get("methodId", "")): library_versions(
                    self.app.controller.library, str(item.get("methodId", ""))
                ).get("versions", [])
                for item in methods
            }
            return {"methods": methods, "versions": versions}

        def loaded(result: dict[str, Any]) -> None:
            self._methods = [_dict(item) for item in _list(result.get("methods"))]
            self._versions = {
                str(key): [_dict(item) for item in _list(value)]
                for key, value in _dict(result.get("versions")).items()
            }
            labels = [self._method_label(item) for item in self._methods]
            self.method_box.configure(values=labels)
            current_id = self._selected_method_id()
            index = next((i for i, item in enumerate(self._methods) if item.get("methodId") == current_id), 0)
            self.method_var.set(labels[index] if labels else "")
            self._method_changed()
            self.app.status(
                f"저장된 방법 {len(self._methods)}개를 불러왔습니다."
                if self._methods else "저장된 방법이 없습니다."
            )

        self.app.submit(work, loaded, message="저장된 방법을 불러오는 중…")

    @staticmethod
    def _method_label(item: dict[str, Any]) -> str:
        return f"{item.get('name', '이름 없음')} · 최신 v{item.get('version', '—')}"

    def _selected_method_id(self) -> str:
        label = self.method_var.get()
        for item in self._methods:
            if self._method_label(item) == label:
                return str(item.get("methodId", ""))
        return ""

    def _selected_version(self) -> dict[str, Any] | None:
        method_id = self._selected_method_id()
        try:
            version = int(self.version_var.get().removeprefix("v"))
        except ValueError:
            return None
        return next(
            (item for item in self._versions.get(method_id, []) if item.get("version") == version),
            None,
        )

    def _method_changed(self, _event: object | None = None) -> None:
        versions = sorted(
            self._versions.get(self._selected_method_id(), []),
            key=lambda item: int(item.get("version", 0)),
            reverse=True,
        )
        labels = [f"v{item.get('version')}" for item in versions]
        self.version_box.configure(values=labels)
        self.version_var.set(labels[0] if labels else "")
        self.compare_box.configure(values=["이전 버전 자동", *labels[1:]])
        self.compare_var.set("이전 버전 자동")
        self._selection_changed()

    def _selection_changed(self, _event: object | None = None) -> None:
        self._clear_preview("")
        chosen = self._selected_version()
        if chosen:
            saved_at = str(chosen.get("savedAt", "")).replace("T", " ")
            equipment = chosen.get("equipmentUnit") or "미지정"
            description = chosen.get("description") or ""
            self.method_meta.configure(
                text=(
                    f"v{chosen.get('version')} · 구간 {chosen.get('moduleCount', '—')}개 · "
                    f"저장 {saved_at} · 장비 {equipment}"
                    + (f" · {description}" if description else "")
                )
            )
        else:
            self.method_meta.configure(text="저장 목록을 불러오세요.")
        if LOAD_MODES.get(self.mode_var.get()) == "replace":
            self.replace_warning.grid(row=6, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 8))
        else:
            self.replace_warning.grid_remove()
        self._update_controls()

    def _preview_method(self) -> None:
        method_id = self._selected_method_id()
        chosen = self._selected_version()
        if not method_id or not chosen:
            self.app.status("저장된 방법과 버전을 먼저 선택하세요.")
            return
        version = int(chosen["version"])
        compare_text = self.compare_var.get()
        compare_version = None if compare_text == "이전 버전 자동" else int(compare_text.removeprefix("v"))
        replace = LOAD_MODES.get(self.mode_var.get()) == "replace"
        revision = self.app.revision
        signature = self._signature()

        def work() -> dict[str, Any]:
            return self.app.controller.library_preview(
                method_id, version, replace=replace, compare_version=compare_version
            )

        def shown(result: dict[str, Any]) -> None:
            if self.app.revision != revision or self._signature() != signature:
                self._clear_preview("선택 또는 프로젝트가 바뀌어 미리보기 결과를 폐기했습니다.")
                return
            self._preview = {
                "revision": revision,
                "signature": signature,
                "token": result.get("token"),
                "ok": bool(result.get("ok")),
            }
            _set_readonly_text(self.preview_text, _summary_lines(result))
            self._update_controls()

        self.app.submit(work, shown, message="저장된 방법의 변경 내용을 계산하는 중…")

    def _apply_method(self) -> None:
        chosen = self._selected_version()
        preview = self._preview
        if (
            not chosen
            or not preview
            or not preview.get("ok")
            or preview.get("revision") != self.app.revision
            or preview.get("signature") != self._signature()
            or not preview.get("token")
        ):
            self.app.status("현재 선택과 일치하는 유효한 미리보기가 필요합니다.")
            self._update_controls()
            return
        args = {
            "methodId": self._selected_method_id(),
            "version": int(chosen["version"]),
            "replace": LOAD_MODES.get(self.mode_var.get()) == "replace",
            "previewToken": preview["token"],
        }
        self._preview = None
        _set_readonly_text(self.preview_text, "적용 요청을 보냈습니다. 전체 적용은 한 번의 되돌리기 항목으로 기록됩니다.")
        self.app.perform("loadMethod", args)

    def _save_method(self) -> None:
        name = self.save_name.get().strip()
        description = self.save_description.get().strip()
        scope = self.save_scope.get()
        selected = self.app.selected
        if not name:
            self.app.status("저장할 방법의 이름을 입력하세요.")
            return
        if scope == "selected" and not selected:
            self.app.status("먼저 저장할 모듈을 선택하세요.")
            return
        module_ids = [selected] if scope == "selected" and selected else None

        def work() -> dict[str, Any]:
            return self.app.controller.save_method(name, description=description, module_ids=module_ids)

        def saved(result: dict[str, Any]) -> None:
            method = _dict(result.get("method", result))
            self.save_name.set("")
            self.save_description.set("")
            self.app.status(
                f"{method.get('name', name)} v{method.get('version', '—')}을(를) 저장했습니다. "
                "목록 새로고침으로 확인할 수 있습니다."
            )

        self.app.submit(work, saved, message="방법을 라이브러리에 저장하는 중…")

    def _clear_preview(self, text: str) -> None:
        self._preview = None
        _set_readonly_text(self.preview_text, text)
        self._update_controls()

    def _update_controls(self) -> None:
        locked = self._busy or bool(getattr(self.app, "busy", False))
        for widget in self._interactive:
            try:
                widget.configure(state="disabled" if locked else "normal")
            except tk.TclError:
                pass
        if not locked:
            for box in (self.method_box, self.version_box, self.compare_box, self.mode_box):
                box.configure(state="readonly")
        self.preview_button.configure(state="disabled" if locked or not self._selected_version() else "normal")
        preview_valid = bool(
            self._preview
            and self._preview.get("ok")
            and self._preview.get("revision") == self.app.revision
            and self._preview.get("signature") == self._signature()
        )
        self.apply_button.configure(state="normal" if preview_valid and not locked else "disabled")


class ExportPanel(ttk.Frame):
    """Release-gated single and per-cell exports."""

    def __init__(self, parent: tk.Misc, app: Any) -> None:
        super().__init__(parent)
        self.app = app
        self._busy = False
        self._interactive: list[tk.Widget] = []
        self._batch_preview: dict[str, Any] | None = None
        self._batch_signature_value: str | None = None
        self._batch_revision: int | None = None

        scroll = ScrollFrame(self)
        scroll.pack(fill="both", expand=True)
        body = scroll.body
        body.columnconfigure(0, weight=1)

        summary_box = ttk.LabelFrame(body, text="실험 요약 · 전류·순서·예상 시간")
        summary_box.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 6))
        summary_box.columnconfigure(0, weight=1)
        self.summary_text = tk.Text(summary_box, height=7, wrap="word", state="disabled")
        self.summary_text.grid(row=0, column=0, sticky="ew", padx=6, pady=6)

        checks = ttk.LabelFrame(body, text="내보내기 전 확인")
        checks.grid(row=1, column=0, sticky="ew", padx=14, pady=6)
        checks.columnconfigure(0, weight=1)
        self.validation_text = tk.Text(checks, height=8, wrap="word", state="disabled")
        self.validation_text.grid(row=0, column=0, sticky="ew", padx=6, pady=6)

        destination = ttk.LabelFrame(body, text="파일 저장 위치")
        destination.grid(row=2, column=0, sticky="ew", padx=14, pady=6)
        destination.columnconfigure(0, weight=1)
        ttk.Label(
            destination,
            text="새 폴더 또는 빈 폴더를 지정하세요. 기존 파일은 덮어쓰지 않습니다.",
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(6, 2))
        self.out_dir = tk.StringVar()
        out_entry = ttk.Entry(destination, textvariable=self.out_dir)
        out_entry.grid(row=1, column=0, sticky="ew", padx=(8, 4), pady=6)
        browse = ttk.Button(destination, text="폴더 선택…", command=self._choose_output_dir)
        browse.grid(row=1, column=1, padx=(4, 8), pady=6)
        self._interactive.extend((out_entry, browse))

        self.release_frame = ttk.LabelFrame(body, text="진행 상태와 생성 가능한 파일")
        self.release_frame.grid(row=3, column=0, sticky="ew", padx=14, pady=6)
        self.release_frame.columnconfigure(0, weight=1)

        batch = ttk.LabelFrame(body, text="셀별 파일 일괄 생성")
        batch.grid(row=4, column=0, sticky="ew", padx=14, pady=(6, 14))
        batch.columnconfigure(1, weight=1)
        ttk.Label(
            batch,
            text="셀별 수동 기준용량으로 C-rate 전류를 다시 계산하고, 생성 전에 차단 사유를 검토합니다.",
            wraplength=720,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(6, 8))
        self.phase_var = tk.StringVar(value="Formation")
        self.kind_var = tk.StringVar(value="미리보기 파일")
        phase = ttk.Combobox(
            batch, textvariable=self.phase_var, values=tuple(BATCH_PHASES), state="readonly"
        )
        kind = ttk.Combobox(
            batch, textvariable=self.kind_var, values=tuple(BATCH_KINDS), state="readonly"
        )
        ttk.Label(batch, text="실험 단계").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        phase.grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        ttk.Label(batch, text="파일 종류").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        kind.grid(row=2, column=1, sticky="ew", padx=8, pady=4)
        self._interactive.extend((phase, kind))
        phase.bind("<<ComboboxSelected>>", self._invalidate_batch)
        kind.bind("<<ComboboxSelected>>", self._invalidate_batch)

        ttk.Label(batch, text="셀 ID, 기준용량(mAh) · 한 줄에 한 셀").grid(
            row=3, column=0, columnspan=3, sticky="w", padx=8, pady=(8, 2)
        )
        self.cells_text = tk.Text(batch, height=5, wrap="none")
        self.cells_text.grid(row=4, column=0, columnspan=3, sticky="ew", padx=8, pady=4)
        self.cells_text.bind("<<Modified>>", self._batch_text_changed)
        self._interactive.append(self.cells_text)

        self.matrix_enabled = tk.BooleanVar(value=False)
        matrix_check = ttk.Checkbutton(
            batch, text="고급: 충전율 × 방전율 조합 생성", variable=self.matrix_enabled, command=self._matrix_toggled
        )
        matrix_check.grid(row=5, column=0, columnspan=3, sticky="w", padx=8, pady=4)
        self._interactive.append(matrix_check)
        self.matrix_frame = ttk.Frame(batch)
        self.matrix_frame.grid(row=6, column=0, columnspan=3, sticky="ew", padx=8, pady=2)
        self.matrix_frame.columnconfigure(1, weight=1)
        self.charge_rates = tk.StringVar(value="0.5")
        self.discharge_rates = tk.StringVar(value="0.5")
        ttk.Label(self.matrix_frame, text="충전 C-rate 목록").grid(row=0, column=0, sticky="w", pady=3)
        charge = ttk.Entry(self.matrix_frame, textvariable=self.charge_rates)
        charge.grid(row=0, column=1, sticky="ew", padx=8, pady=3)
        ttk.Label(self.matrix_frame, text="방전 C-rate 목록").grid(row=1, column=0, sticky="w", pady=3)
        discharge = ttk.Entry(self.matrix_frame, textvariable=self.discharge_rates)
        discharge.grid(row=1, column=1, sticky="ew", padx=8, pady=3)
        self._interactive.extend((charge, discharge))
        self.charge_rates.trace_add("write", lambda *_: self._invalidate_batch())
        self.discharge_rates.trace_add("write", lambda *_: self._invalidate_batch())
        self.matrix_frame.grid_remove()

        actions = ttk.Frame(batch)
        actions.grid(row=7, column=0, columnspan=3, sticky="w", padx=8, pady=8)
        self.batch_plan_button = ttk.Button(actions, text="셀별 전류 미리보기", command=self._plan_batch)
        self.batch_export_button = ttk.Button(actions, text="검토한 배치 생성", command=self._export_batch)
        self.batch_plan_button.pack(side="left")
        self.batch_export_button.pack(side="left", padx=6)
        self._interactive.extend((self.batch_plan_button, self.batch_export_button))
        self.batch_text = tk.Text(batch, height=11, wrap="word", state="disabled")
        self.batch_text.grid(row=8, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 8))

        self.refresh()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._update_controls()

    def refresh(self) -> None:
        views = _dict(self.app.controller.views)
        project = _dict(self.app.project)
        summary = _dict(views.get("summary"))
        capacity = _dict(project.get("cell_profile")).get("nominal_capacity_mAh", "—")
        _set_readonly_text(
            self.summary_text,
            f"{summary.get('text', '')}\n\n기준용량 {capacity} mAh\n"
            "예상 시간은 CV 구간과 장비 지연을 완전히 예측하지 못합니다.",
        )
        validation = [_dict(item) for item in _list(views.get("validation"))]
        lines = [
            f"[{item.get('severityLabel', item.get('severity', '확인'))}] "
            f"{item.get('location', '')} — {item.get('message', '')}"
            + (f" · {item.get('remediation')}" if item.get("remediation") else "")
            for item in validation
        ]
        unverified = [str(item) for item in _list(views.get("unverified"))]
        if unverified:
            lines.extend(("", "미확인 근거: " + " · ".join(unverified)))
        if not lines:
            lines.append("현재 표시할 오류나 경고가 없습니다.")
        _set_readonly_text(self.validation_text, "\n".join(lines))
        self._render_release(_dict(views.get("release")))
        if self._batch_revision is not None and self._batch_revision != self.app.revision:
            self._batch_preview = None
            self._batch_signature_value = None
            self._batch_revision = None
            _set_readonly_text(self.batch_text, "프로젝트가 바뀌어 이전 배치 미리보기를 폐기했습니다.")
        self._update_controls()

    def _render_release(self, release: dict[str, Any]) -> None:
        for child in self.release_frame.winfo_children():
            child.destroy()
        ttk.Label(
            self.release_frame,
            text=f"진행 상태: {release.get('stageLabel', '—')}",
            style="Heading.TLabel",
        ).grid(row=0, column=0, sticky="w", padx=8, pady=(8, 3))
        label = _dict(release.get("label"))
        row = 1
        if label:
            text = f"{label.get('label', '')} ({label.get('labelKo', '')})\n{label.get('meaning', '')}"
            reasons = _list(label.get("reasons"))
            if reasons:
                text += "\n" + "\n".join(f"· {item}" for item in reasons)
            ttk.Label(self.release_frame, text=text, wraplength=700).grid(
                row=row, column=0, sticky="w", padx=8, pady=3
            )
            row += 1
        for option in [_dict(item) for item in _list(release.get("options"))]:
            frame = ttk.Frame(self.release_frame)
            frame.grid(row=row, column=0, sticky="ew", padx=8, pady=5)
            frame.columnconfigure(0, weight=1)
            title = str(option.get("title", option.get("kind", "")))
            if option.get("recommended"):
                title += " · 권장"
            ttk.Label(frame, text=title).grid(row=0, column=0, sticky="w")
            ttk.Label(frame, text=str(option.get("description", "")), wraplength=600).grid(
                row=1, column=0, sticky="w"
            )
            details = [f"· {item}" for item in _list(option.get("blockers"))]
            if not option.get("allowed") and option.get("nextAction"):
                details.append(f"다음 단계: {option['nextAction']}")
            if details:
                ttk.Label(frame, text="\n".join(details), foreground="#9b382f", wraplength=600).grid(
                    row=2, column=0, sticky="w"
                )
            kind = str(option.get("kind", ""))
            if kind == "template_patch":
                command: Callable[[], None] = self._open_import_tab
                button_text = "기존 SCH 열기"
            elif kind in {"draft_save", "preview", "review_candidate"}:
                def command(selected: str = kind) -> None:
                    self._export_one(selected)

                button_text = "파일 생성"
            else:
                command = self._noop
                button_text = "별도 승인 절차" if kind == "equipment_export" else "잠김"
            button = ttk.Button(frame, text=button_text, command=command)
            button.grid(row=0, column=1, rowspan=3, padx=(8, 0))
            if not option.get("allowed") or kind == "equipment_export" or self._busy or self.app.busy:
                button.configure(state="disabled")
            self._interactive.append(button)
            row += 1

    @staticmethod
    def _noop() -> None:
        return

    def _choose_output_dir(self) -> None:
        chosen = filedialog.askdirectory(parent=self.app.root, title="빈 출력 폴더 선택")
        if chosen:
            self.out_dir.set(chosen)

    def _export_one(self, kind: str) -> None:
        out_dir = self.out_dir.get().strip()
        if not out_dir:
            self.app.status("새 출력 폴더 또는 빈 폴더를 선택하세요.")
            return

        def work() -> dict[str, Any]:
            return self.app.controller.export(kind, out_dir)

        def exported(result: dict[str, Any]) -> None:
            paths = [str(item) for item in _list(result.get("paths"))]
            self.app.status(str(result.get("note", "파일을 생성했습니다.")))
            self.app.show_text("생성된 파일", "\n".join(paths) if paths else "생성된 경로가 없습니다.")

        self.app.submit(work, exported, message="내보내기 게이트를 확인하고 파일을 생성하는 중…")

    def _open_import_tab(self) -> None:
        for tab_id in self.app.notebook.tabs():
            label = str(self.app.notebook.tab(tab_id, "text"))
            if "SCH" in label or "가져오기" in label or "불러오기" in label:
                self.app.notebook.select(tab_id)
                return
        self.app.status("기존 SCH 탭을 찾을 수 없습니다.")

    @staticmethod
    def _parse_cells(text: str) -> list[dict[str, Any]]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            first = lines[0].replace(" ", "").split(",")[0].split("\t")[0].lower()
            if first in {"cellid", "cell_id", "셀id", "셀아이디"}:
                lines = lines[1:]
        rows: list[dict[str, Any]] = []
        for line in lines:
            columns = [part.strip() for part in line.replace("\t", ",").split(",")]
            row: dict[str, Any] = {
                "cellId": columns[0] if columns else "",
                "referenceCapacityMah": columns[1] if len(columns) > 1 else "",
            }
            if len(columns) > 2:
                row["extraColumns"] = len(columns) - 2
            rows.append(row)
        return rows

    @staticmethod
    def _parse_rates(text: str, label: str) -> list[float]:
        normalized = text.strip()
        if not normalized:
            raise ValueError(f"{label}을(를) 하나 이상 입력하세요.")
        groups = normalized.replace(";", ",").replace("\n", ",").split(",")
        if any(not group.strip() for group in groups):
            raise ValueError(f"{label}에 비어 있는 값이 있습니다.")
        tokens = [token for group in groups for token in group.split()]
        rates = [float(token) for token in tokens]
        if any(not math.isfinite(rate) or rate <= 0 for rate in rates):
            raise ValueError(f"{label}은(는) 유한한 양수만 입력하세요.")
        if len(set(rates)) != len(rates):
            raise ValueError(f"{label}에 중복 값이 있습니다.")
        return rates

    def _batch_args(self) -> dict[str, Any]:
        args: dict[str, Any] = {
            "phase": BATCH_PHASES[self.phase_var.get()],
            "basis": "manual_reference",
            "kind": BATCH_KINDS[self.kind_var.get()],
            "rows": self._parse_cells(self.cells_text.get("1.0", "end-1c")),
        }
        if self.matrix_enabled.get():
            charge = self._parse_rates(self.charge_rates.get(), "충전 C-rate")
            discharge = self._parse_rates(self.discharge_rates.get(), "방전 C-rate")
            if len(charge) * len(discharge) > MAX_MATRIX_VARIANTS:
                raise ValueError(f"충전율×방전율 조합은 {MAX_MATRIX_VARIANTS}개 이하여야 합니다.")
            args["matrix"] = [
                {"chargeRate": charge_rate, "dischargeRate": discharge_rate}
                for charge_rate in charge
                for discharge_rate in discharge
            ]
        return args

    @staticmethod
    def _batch_signature(args: dict[str, Any]) -> str:
        return json.dumps(args, ensure_ascii=False, sort_keys=True, allow_nan=False)

    def _plan_batch(self) -> None:
        try:
            args = self._batch_args()
        except ValueError as exc:
            self.app.status(str(exc))
            return
        if not args["rows"]:
            self.app.status("셀 ID와 기준용량을 한 줄에 하나씩 입력하세요.")
            return
        signature = self._batch_signature(args)
        revision = self.app.revision

        def work() -> dict[str, Any]:
            return self.app.controller.plan("cellBatch", args)

        def planned(result: dict[str, Any]) -> None:
            if self.app.revision != revision:
                self._invalidate_batch(message="프로젝트가 바뀌어 배치 미리보기를 폐기했습니다.")
                return
            try:
                current = self._batch_signature(self._batch_args())
            except ValueError:
                current = ""
            if current != signature:
                self._invalidate_batch(message="입력이 바뀌어 배치 미리보기를 폐기했습니다.")
                return
            self._batch_preview = result
            self._batch_signature_value = signature
            self._batch_revision = revision
            _set_readonly_text(self.batch_text, self._format_batch(result))
            self._update_controls()

        self.app.submit(work, planned, message="셀별 전류와 내보내기 차단 사유를 계산하는 중…")

    @staticmethod
    def _format_batch(result: dict[str, Any]) -> str:
        rows = [_dict(item) for item in _list(result.get("rows"))]
        lines = [str(result.get("note", ""))]
        lines.extend(f"주의: {item}" for item in _list(result.get("warnings")))
        lines.extend(f"오류: {item}" for item in _list(result.get("errors")))
        lines.append("")
        for row in rows:
            variant = f" · {row.get('variantId')}" if row.get("variantId") else ""
            rates = ""
            if row.get("variantId"):
                rates = (
                    f" · 충전 {row.get('chargeRate')}C/{row.get('chargeCurrentmA')} mA"
                    f" · 방전 {row.get('dischargeRate')}C/{row.get('dischargeCurrentmA')} mA"
                )
            status = "준비됨" if row.get("allowed") else "; ".join(map(str, _list(row.get("blockers"))))
            lines.append(
                f"{row.get('cellId') or '—'}{variant} · 기준 {row.get('selectedCapacityMah', '—')} mAh"
                f" · 1C {row.get('oneCmA', '—')} mA · 최대 {row.get('maxCurrentmA', '—')} mA"
                f"{rates} · {status}"
            )
        return "\n".join(lines).strip()

    def _export_batch(self) -> None:
        try:
            args = self._batch_args()
            signature = self._batch_signature(args)
        except ValueError as exc:
            self.app.status(str(exc))
            return
        preview = self._batch_preview
        out_dir = self.out_dir.get().strip()
        if not out_dir:
            self.app.status("배치를 저장할 새 출력 폴더 또는 빈 폴더를 선택하세요.")
            return
        if (
            not preview
            or not preview.get("ok")
            or not preview.get("token")
            or self._batch_signature_value != signature
            or self._batch_revision != self.app.revision
        ):
            self.app.status("현재 입력과 일치하는 유효한 배치 미리보기가 필요합니다.")
            return
        token = str(preview["token"])

        def work() -> dict[str, Any]:
            return self.app.controller.export_batch(args, token, out_dir)

        def exported(result: dict[str, Any]) -> None:
            paths = [str(item) for item in _list(result.get("paths"))]
            self._invalidate_batch()
            self.app.status(str(result.get("note", f"{len(paths)}개 파일을 생성했습니다.")))
            self.app.show_text("배치 생성 결과", "\n".join(paths))

        self.app.submit(work, exported, message="검토한 셀 배치를 새 폴더에 생성하는 중…")

    def _batch_text_changed(self, _event: object | None = None) -> None:
        if self.cells_text.edit_modified():
            self.cells_text.edit_modified(False)
            self._invalidate_batch()

    def _matrix_toggled(self) -> None:
        if self.matrix_enabled.get():
            self.matrix_frame.grid()
        else:
            self.matrix_frame.grid_remove()
        self._invalidate_batch()

    def _invalidate_batch(self, _event: object | None = None, *, message: str = "") -> None:
        self._batch_preview = None
        self._batch_signature_value = None
        self._batch_revision = None
        if message:
            _set_readonly_text(self.batch_text, message)
        self._update_controls()

    def _update_controls(self) -> None:
        locked = self._busy or bool(getattr(self.app, "busy", False))
        for widget in self._interactive:
            try:
                if isinstance(widget, ttk.Combobox):
                    widget.configure(state="disabled" if locked else "readonly")
                elif isinstance(widget, tk.Text):
                    widget.configure(state="disabled" if locked else "normal")
                else:
                    widget.configure(state="disabled" if locked else "normal")
            except tk.TclError:
                pass
        valid = bool(
            self._batch_preview
            and self._batch_preview.get("ok")
            and self._batch_preview.get("token")
            and self._batch_revision == self.app.revision
        )
        self.batch_export_button.configure(state="normal" if valid and not locked else "disabled")


class ImportPanel(ttk.Frame):
    """Bounded, byte-preserving edits of an existing SCH file."""

    _DTYPE_BYTES = {"uint8": 1, "uint32": 4, "int32": 4, "float32": 4}

    def __init__(self, parent: tk.Misc, app: Any) -> None:
        super().__init__(parent)
        self.app = app
        self._busy = False
        self._info: dict[str, Any] | None = None
        self._proposal: dict[str, Any] | None = None
        self._interactive: list[tk.Widget] = []

        scroll = ScrollFrame(self)
        scroll.pack(fill="both", expand=True)
        body = scroll.body
        body.columnconfigure(0, weight=1)

        open_box = ttk.LabelFrame(body, text="기존 SCH 열기")
        open_box.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 6))
        open_box.columnconfigure(0, weight=1)
        ttk.Label(
            open_box,
            text="구조와 편집 가능 필드를 먼저 검토합니다. 이 단계에서는 원본 파일을 변경하지 않습니다.",
            wraplength=720,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(6, 3))
        self.path_var = tk.StringVar()
        path_entry = ttk.Entry(open_box, textvariable=self.path_var)
        path_entry.grid(row=1, column=0, sticky="ew", padx=(8, 4), pady=6)
        choose = ttk.Button(open_box, text="SCH 파일 선택…", command=self._choose_source)
        choose.grid(row=1, column=1, padx=(4, 8), pady=6)
        open_button = ttk.Button(open_box, text="원본 보호 모드로 열기", command=self._open_import)
        open_button.grid(row=2, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 8))
        self._interactive.extend((path_entry, choose, open_button))

        metadata = ttk.LabelFrame(body, text="열린 SCH · 분석용 설명")
        metadata.grid(row=1, column=0, sticky="ew", padx=14, pady=6)
        metadata.columnconfigure(0, weight=1)
        self.meta_label = ttk.Label(metadata, text="SCH 파일을 선택해 여세요.", wraplength=720)
        self.meta_label.grid(row=0, column=0, sticky="w", padx=8, pady=6)
        self.explanation_text = tk.Text(metadata, height=13, width=90, wrap="word", state="disabled")
        explanation_scroll = ttk.Scrollbar(metadata, orient="vertical", command=self.explanation_text.yview)
        self.explanation_text.configure(yscrollcommand=explanation_scroll.set)
        self.explanation_text.grid(row=1, column=0, sticky="ew", padx=(8, 0), pady=(0, 8))
        explanation_scroll.grid(row=1, column=1, sticky="ns", padx=(0, 8), pady=(0, 8))

        edit = ttk.LabelFrame(body, text="검증된 숫자 필드만 편집")
        edit.grid(row=2, column=0, sticky="ew", padx=14, pady=6)
        edit.columnconfigure(1, weight=1)
        self.step_var = tk.StringVar(value="1")
        self.field_var = tk.StringVar()
        self.value_var = tk.StringVar()
        ttk.Label(edit, text="스텝 번호").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        step = ttk.Entry(edit, textvariable=self.step_var, width=12)
        step.grid(row=0, column=1, sticky="w", padx=8, pady=4)
        ttk.Label(edit, text="허용된 필드").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        self.field_box = ttk.Combobox(edit, textvariable=self.field_var, state="readonly")
        self.field_box.grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        self.field_box.bind("<<ComboboxSelected>>", self._field_changed)
        ttk.Label(edit, text="새 값").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        value = ttk.Entry(edit, textvariable=self.value_var)
        value.grid(row=2, column=1, sticky="ew", padx=8, pady=4)
        self.field_help = ttk.Label(edit, text="", wraplength=700)
        self.field_help.grid(row=3, column=0, columnspan=2, sticky="w", padx=8, pady=4)
        edit_actions = ttk.Frame(edit)
        edit_actions.grid(row=4, column=0, columnspan=2, sticky="w", padx=8, pady=8)
        self.stage_button = ttk.Button(edit_actions, text="편집 추가/바꾸기", command=self._stage_import)
        self.clear_button = ttk.Button(edit_actions, text="모든 편집 되돌리기", command=self._clear_import)
        self.stage_button.pack(side="left")
        self.clear_button.pack(side="left", padx=6)
        self._interactive.extend((step, self.field_box, value, self.stage_button, self.clear_button))

        proposal_box = ttk.LabelFrame(body, text="원본 대비 바이트 영향 미리보기")
        proposal_box.grid(row=3, column=0, sticky="ew", padx=14, pady=6)
        proposal_box.columnconfigure(0, weight=1)
        self.proposal_text = tk.Text(proposal_box, height=10, wrap="word", state="disabled")
        self.proposal_text.grid(row=0, column=0, sticky="ew", padx=8, pady=8)

        output = ttk.LabelFrame(body, text="새 분석용 SCH 저장")
        output.grid(row=4, column=0, sticky="ew", padx=14, pady=(6, 14))
        output.columnconfigure(0, weight=1)
        ttk.Label(
            output,
            text="원본과 다른 .sch 경로에 저장하며, 검증 기록도 함께 만듭니다. CTSPro 재열기 전에는 장비 실행용이 아닙니다.",
            wraplength=720,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(6, 3))
        self.output_var = tk.StringVar()
        output_entry = ttk.Entry(output, textvariable=self.output_var)
        output_entry.grid(row=1, column=0, sticky="ew", padx=(8, 4), pady=5)
        output_choose = ttk.Button(output, text="다른 이름으로…", command=self._choose_output)
        output_choose.grid(row=1, column=1, padx=(4, 8), pady=5)
        self.ack_var = tk.BooleanVar(value=False)
        ack = ttk.Checkbutton(
            output,
            text="이 결과물은 분석용이며 장비 실행용이 아님을 확인했습니다.",
            variable=self.ack_var,
            command=self._update_controls,
        )
        ack.grid(row=2, column=0, columnspan=2, sticky="w", padx=8, pady=4)
        self.patch_button = ttk.Button(output, text="새 SCH 파일 저장", command=self._patch_import)
        self.patch_button.grid(row=3, column=0, columnspan=2, sticky="w", padx=8, pady=8)
        self._interactive.extend((output_entry, output_choose, ack, self.patch_button))

        self._update_controls()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._update_controls()

    def refresh(self) -> None:
        """Import sessions are independent of project redraws."""
        self._update_controls()

    def _choose_source(self) -> None:
        chosen = filedialog.askopenfilename(
            parent=self.app.root,
            title="기존 SCH 파일 선택",
            filetypes=(("PNE schedule", "*.sch"), ("모든 파일", "*")),
        )
        if chosen:
            self.path_var.set(chosen)

    def _open_import(self) -> None:
        path = self.path_var.get().strip()
        if not path:
            self.app.status("열 SCH 파일을 선택하세요.")
            return

        def work() -> dict[str, Any]:
            return self.app.controller.import_open(path)

        def opened(info: dict[str, Any]) -> None:
            self._info = info
            self._proposal = None
            fields = [_dict(item) for item in _list(info.get("editableFields"))]
            labels = [self._field_label(item) for item in fields]
            self.field_box.configure(values=labels)
            self.field_var.set(labels[0] if labels else "")
            self.step_var.set("1")
            self.value_var.set("")
            self.ack_var.set(False)
            source = Path(str(info.get("path", path)))
            self.output_var.set(str(source.with_name(f"{source.stem}_patched.sch")))
            self.meta_label.configure(
                text=(
                    f"{source.name}\n{source}\n{info.get('schVersion', '버전 미상')} · "
                    f"{info.get('stepCount', '—')}스텝 · SHA-256 {str(info.get('sha256', ''))[:12]}…"
                )
            )
            _set_readonly_text(self.explanation_text, str(info.get("explanation", "설명이 없습니다.")))
            if not fields:
                _set_readonly_text(
                    self.proposal_text,
                    "이 SCH 형식에는 쓰기 검증 근거가 없어 편집할 수 없습니다. 설명 검토만 가능합니다.",
                )
            else:
                _set_readonly_text(self.proposal_text, "허용된 필드와 값을 선택해 편집을 추가하세요.")
            self._field_changed()
            self._update_controls()
            self.app.status("SCH를 읽었습니다. 원본은 변경하지 않았습니다.")

        self.app.submit(work, opened, message="SCH 구조와 검증 근거를 읽는 중…")

    @staticmethod
    def _field_label(field: dict[str, Any]) -> str:
        unit = f" ({field.get('unit')})" if field.get("unit") else ""
        return f"{field.get('label', field.get('name', ''))}{unit} · {field.get('name', '')}"

    def _fields(self) -> list[dict[str, Any]]:
        return [_dict(item) for item in _list(_dict(self._info).get("editableFields"))]

    def _selected_field(self) -> dict[str, Any] | None:
        label = self.field_var.get()
        return next((item for item in self._fields() if self._field_label(item) == label), None)

    def _field_changed(self, _event: object | None = None) -> None:
        field = self._selected_field()
        if not field:
            self.field_help.configure(text="편집 가능한 필드가 없습니다.")
            return
        unit = f" · 입력 단위 {field.get('unit')}" if field.get("unit") else ""
        voltage = " · 종료 전압은 mV로 입력합니다 (예: 4200 = 4.2 V)." if field.get("name") == "fEndV" else ""
        self.field_help.configure(
            text=f"내부 필드 {field.get('name')} @+{field.get('offset')}{unit}{voltage}\n근거: {field.get('evidence', '')}"
        )

    def _stage_import(self) -> None:
        field = self._selected_field()
        try:
            step_no = int(self.step_var.get().strip())
            value = float(self.value_var.get().strip())
        except ValueError:
            self.app.status("스텝 번호는 정수, 편집 값은 숫자로 입력하세요.")
            return
        if not field or not math.isfinite(value):
            self.app.status("허용된 필드와 유한한 숫자 값을 입력하세요.")
            return
        name = str(field.get("name", ""))

        def work() -> dict[str, Any]:
            return self.app.controller.import_stage(step_no, name, value)

        def staged(proposal: dict[str, Any]) -> None:
            self._proposal = proposal
            _set_readonly_text(self.proposal_text, self._format_proposal(proposal))
            self._update_controls()

        self.app.submit(work, staged, message="편집 위치와 바이트 범위를 검증하는 중…")

    def _clear_import(self) -> None:
        if not self._info:
            return

        def work() -> dict[str, Any]:
            return self.app.controller.import_clear()

        def cleared(proposal: dict[str, Any]) -> None:
            self._proposal = proposal
            _set_readonly_text(self.proposal_text, "모든 편집을 되돌렸습니다. 원본 파일은 변경되지 않았습니다.")
            self._update_controls()

        self.app.submit(work, cleared, message="편집 제안을 지우는 중…")

    def _format_proposal(self, proposal: dict[str, Any]) -> str:
        accepted = [_dict(item) for item in _list(proposal.get("accepted"))]
        rejected = [_dict(item) for item in _list(proposal.get("rejected"))]
        field_sizes = {
            str(item.get("name", "")): self._DTYPE_BYTES.get(str(item.get("dtype", "")), 0)
            for item in self._fields()
        }
        planned_bytes = sum(field_sizes.get(str(item.get("field", "")), 0) for item in accepted)
        lines = [
            f"허용된 편집 {len(accepted)}개 · 쓰기 대상 필드 폭 합계 {planned_bytes}바이트",
            "실제 값이 같은 바이트는 변경 수에서 제외될 수 있으며, 저장 후 실제 변경 바이트 수를 다시 표시합니다.",
        ]
        lines.extend(
            f"· 스텝 {item.get('stepNo')} · {item.get('field')} = {item.get('value')}"
            for item in accepted
        )
        lines.extend(
            f"거부 · 스텝 {item.get('stepNo')} · {item.get('field')} — {item.get('reason')}"
            for item in rejected
        )
        lines.extend(f"주의: {item}" for item in _list(proposal.get("warnings")))
        lines.extend(str(item) for item in _list(proposal.get("notes")))
        return "\n".join(lines)

    def _choose_output(self) -> None:
        initial = Path(self.output_var.get()) if self.output_var.get().strip() else None
        chosen = filedialog.asksaveasfilename(
            parent=self.app.root,
            title="새 분석용 SCH 저장 위치",
            defaultextension=".sch",
            filetypes=(("PNE schedule", "*.sch"),),
            initialdir=str(initial.parent) if initial else None,
            initialfile=initial.name if initial else None,
        )
        if chosen:
            self.output_var.set(chosen)

    def _patch_import(self) -> None:
        output_path = self.output_var.get().strip()
        proposal = self._proposal
        if not self.ack_var.get():
            self.app.status("분석용이며 장비 실행용이 아님을 확인하세요.")
            return
        if not output_path:
            self.app.status("원본과 다른 .sch 출력 경로를 선택하세요.")
            return
        if not proposal or not proposal.get("ok") or _list(proposal.get("rejected")):
            self.app.status("거부 항목이 없는 유효한 바이트 영향 미리보기가 필요합니다.")
            return

        def work() -> dict[str, Any]:
            return self.app.controller.import_patch(output_path)

        def patched(result: dict[str, Any]) -> None:
            text = (
                f"저장: {result.get('outputPath', output_path)}\n"
                f"검증 기록: {result.get('manifestPath', '—')}\n"
                f"실제 변경된 바이트: {result.get('changedByteCount', '—')}\n"
                "장비 실행 불가 · CTSPro 재열기 확인 필요"
            )
            self.app.status("새 분석용 SCH와 검증 기록을 저장했습니다.")
            self.app.show_text("SCH 패치 결과", text)

        self.app.submit(work, patched, message="원본 해시를 재확인하고 새 분석용 SCH를 쓰는 중…")

    def _update_controls(self) -> None:
        locked = self._busy or bool(getattr(self.app, "busy", False))
        fields_available = bool(self._fields())
        for widget in self._interactive:
            try:
                if widget is self.field_box:
                    widget.configure(state="disabled" if locked or not fields_available else "readonly")
                else:
                    widget.configure(state="disabled" if locked else "normal")
            except tk.TclError:
                pass
        self.stage_button.configure(state="normal" if fields_available and not locked else "disabled")
        self.clear_button.configure(state="normal" if self._info and not locked else "disabled")
        proposal_ok = bool(
            self._proposal
            and self._proposal.get("ok")
            and not _list(self._proposal.get("rejected"))
            and self.ack_var.get()
        )
        self.patch_button.configure(state="normal" if proposal_ok and not locked else "disabled")


__all__ = ["ExportPanel", "ImportPanel", "LibraryPanel"]
