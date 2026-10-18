"""Native Tk protocol authoring panel.

The panel is deliberately a renderer over ``NativeController.views``.  Every
mutation goes through ``WorkspaceApp.perform`` and every preview goes through
``NativeController.plan``; no protocol arithmetic is duplicated here.
"""

from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from ..protocol.qpeed_results import MAX_BYTES
from .tk_widgets import FieldInput, ScrollFrame


Json = dict[str, Any]


_BASIC_STEPS: tuple[Json, ...] = (
    {"key": "primitive:cc_charge", "moduleType": "primitive", "title": "CC 충전", "description": "정전류 충전", "params": {"kind": "cc_charge"}},
    {"key": "primitive:cccv_charge", "moduleType": "primitive", "title": "CCCV 충전", "description": "정전류·정전압 충전", "params": {"kind": "cccv_charge"}},
    {"key": "primitive:cc_discharge", "moduleType": "primitive", "title": "CC 방전", "description": "정전류 방전", "params": {"kind": "cc_discharge"}},
    {"key": "primitive:rest", "moduleType": "primitive", "title": "휴지", "description": "지정 시간 휴지", "params": {"kind": "rest"}},
    {"key": "primitive:ocv", "moduleType": "primitive", "title": "OCV", "description": "개방전압 측정", "params": {"kind": "ocv"}},
)

_STEP_KINDS: tuple[tuple[str, str], ...] = (
    ("rest", "휴지"),
    ("ocv", "OCV"),
    ("cc_charge", "CC 충전"),
    ("cccv_charge", "CCCV 충전"),
    ("cv_charge", "CV 충전"),
    ("cc_discharge", "CC 방전"),
)


def _clear(widget: tk.Misc) -> None:
    for child in widget.winfo_children():
        child.destroy()


def _join_lines(values: Any) -> str:
    if not values:
        return ""
    return "\n".join(str(value) for value in values)


def _alive(widget: tk.Misc) -> bool:
    try:
        return bool(widget.winfo_exists())
    except tk.TclError:
        return False


class _DialogPreview:
    """Bind a reviewed result to its inputs, request epoch and project revision.

    All methods run on Tk's thread. Input traces also reject a late worker
    result when the user changes a value and then changes it back.
    """

    def __init__(self, panel, window, button, signature, notice):
        self.panel = panel
        self.window = window
        self.button = button
        self.signature = signature
        self.notice = notice
        self.epoch = 0
        self.approved = None
        self.args = None
        self._traces = []
        panel._dialog_previews.append(self)
        window.bind("<Destroy>", self._destroy, add=True)

    def watch(self, variable):
        self._traces.append((variable, variable.trace_add("write", self.invalidate)))

    def unwatch(self, variables):
        names = {str(variable) for variable in variables}
        retained = []
        for variable, token in self._traces:
            if str(variable) in names:
                variable.trace_remove("write", token)
            else:
                retained.append((variable, token))
        self._traces = retained

    def _destroy(self, event):
        if event.widget is self.window:
            self.unwatch([variable for variable, _token in self._traces])
            self.panel._dialog_previews.remove(self)

    def invalidate(self, *_args):
        self.epoch += 1
        self.approved = None
        self.args = None
        if _alive(self.window):
            self.button.configure(state="disabled")
            self.notice.set("입력이나 프로젝트가 바뀌었습니다. 다시 미리보기 하세요.")

    def stamp(self):
        return self.epoch, self.panel._revision, self.signature()

    def begin(self):
        self.invalidate()
        self.notice.set("미리보기를 계산하는 중…")
        return self.stamp()

    def accept(self, ticket, args, render, *, enabled=True):
        if not _alive(self.window):
            return
        if ticket != self.stamp():
            self.invalidate()
            return
        render()
        # Rendering may populate automatically inferred QPEED column choices.
        self.approved = self.stamp()
        self.args = deepcopy(args) if args is not None else None
        self.notice.set("")
        self.button.configure(state="normal" if enabled and self.args is not None else "disabled")

    def check_revision(self):
        if self.approved is not None and self.approved[1] != self.panel._revision:
            self.invalidate()

    def ready(self):
        if not _alive(self.window):
            return False
        if self.args is None or self.approved != self.stamp():
            self.invalidate()
            return False
        return True

    def apply(self, action):
        if self.ready():
            if self.panel.app.perform(action, deepcopy(self.args)):
                self.window.destroy()
            else:
                self.notice.set("다른 작업이 진행 중입니다. 완료 후 다시 적용하세요.")


class ProtocolPanel(ttk.Frame):
    """Complete native protocol editor used when the web UI is unavailable."""

    def __init__(self, parent: tk.Misc, app: Any):
        super().__init__(parent)
        self.app = app
        self._busy = False
        self._dialog_previews: list[_DialogPreview] = []
        self._buttons: list[tk.Widget] = []
        self._drafts: dict[tuple[Any, ...], Json] = {}
        self._committing_drafts: set[tuple[Any, ...]] = set()
        self._field_widgets: dict[tuple[Any, ...], FieldInput] = {}
        self._field_enabled: dict[tuple[Any, ...], bool] = {}
        self._expanded: set[str] = set()
        self._content_cache: dict[tuple[int, str, int | None], Json] = {}
        self._last_revision = int(getattr(app, "revision", 0))
        self._group_selection: list[str] = []
        self._flow_vars: list[tk.Variable] = []
        self._palette_query = tk.StringVar()
        self._group_name = tk.StringVar(value="내 모듈")
        self._group_repeat = tk.StringVar(value="1")
        self._step_kind = tk.StringVar(value="rest")
        self._core_child = None
        self._core_module = None
        self._core_selectors = []

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self._main = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        self._main.grid(row=0, column=0, sticky="nsew")

        self._palette_scroll = ScrollFrame(self._main)
        self._flow_scroll = ScrollFrame(self._main)
        self._inspector_scroll = ScrollFrame(self._main)
        self._main.add(self._palette_scroll, weight=1)
        self._main.add(self._flow_scroll, weight=2)
        self._main.add(self._inspector_scroll, weight=2)

        self._palette_query.trace_add("write", lambda *_: self._render_palette())
        self.refresh()

    # -- public panel contract ---------------------------------------------

    def set_busy(self, busy: bool) -> None:
        self._busy = bool(busy)
        state = "disabled" if self._busy else "normal"
        for widget in self._core_selectors:
            if _alive(widget):
                widget.configure(state="disabled" if self._busy else "readonly")
        for widget in tuple(self._buttons):
            try:
                widget.configure(state=state)
            except tk.TclError:
                pass
        for key, field in tuple(self._field_widgets.items()):
            try:
                field.set_enabled(not self._busy and self._field_enabled.get(key, True))
            except tk.TclError:
                pass

    def refresh(self) -> None:
        for preview in tuple(self._dialog_previews):
            preview.check_revision()
        self._capture_drafts()
        self._buttons.clear()
        self._field_widgets.clear()
        self._field_enabled.clear()
        if self._revision != self._last_revision:
            # Expanded contents are a derived snapshot.  Collapse them after an
            # edit instead of showing stale steps or starting work from refresh.
            self._expanded.clear()
            self._content_cache = {
                key: value for key, value in self._content_cache.items()
                if key[0] == self._revision
            }
            self._last_revision = self._revision
        views = self._views
        valid_ids = {str(row.get("moduleId", "")) for row in views.get("modules", [])}
        self._group_selection = [item for item in self._group_selection if item in valid_ids]
        self._expanded.intersection_update(valid_ids)
        self._render_palette()
        self._render_flow()
        self._render_inspector()
        self.set_busy(bool(self._busy or getattr(self.app, "busy", False)))
        self._committing_drafts.clear()

    # -- common helpers ----------------------------------------------------

    @property
    def _views(self) -> Json:
        value = getattr(self.app.controller, "views", {})
        return value if isinstance(value, dict) else {}

    @property
    def _revision(self) -> int:
        return int(getattr(self.app, "revision", 0))

    def _button(self, parent: tk.Misc, text: str, command: Callable[[], Any], **options: Any) -> ttk.Button:
        button = ttk.Button(parent, text=text, command=command, **options)
        self._buttons.append(button)
        return button

    def _capture_drafts(self) -> None:
        for key, widget in tuple(self._field_widgets.items()):
            if key in self._committing_drafts:
                continue
            try:
                if widget.focus_get() is not None and str(widget.focus_get()).startswith(str(widget)):
                    self._drafts[key] = widget.draft()
            except tk.TclError:
                pass

    def _field(
        self,
        parent: tk.Misc,
        field: Json,
        draft_key: tuple[Any, ...],
        action: str,
        base_args: Json,
        *,
        enabled: bool = True,
    ) -> FieldInput:
        normalized = dict(field)
        normalized.setdefault("value", normalized.get("text", ""))
        normalized.setdefault("numericValue", None)
        normalized.setdefault("numericValues", None)
        normalized.setdefault("choices", [])
        normalized.setdefault("checked", False)
        holder: dict[str, FieldInput] = {}

        def commit(*values: Any) -> None:
            widget = holder["widget"]
            text = str(values[0]) if values else widget.get()
            self._drafts.pop(draft_key, None)
            self._committing_drafts.add(draft_key)
            args = {**base_args, "key": field.get("key", ""), "text": text}
            def failed(error):
                self._committing_drafts.discard(draft_key)
                self._drafts[draft_key] = widget.draft()
                if _alive(widget):
                    widget.show_issue(str(error))
            accepted = self.app.submit(lambda: self.app.controller.edit(action, args),
                                       message="조건 변경 적용", on_error=failed)
            if not accepted:
                self._committing_drafts.discard(draft_key)
                widget.show_issue("다른 작업이 진행 중입니다. 완료 후 다시 적용하세요.")

        widget = FieldInput(parent, normalized, on_commit=commit)
        holder["widget"] = widget
        if draft_key in self._drafts:
            widget.restore_draft(self._drafts[draft_key])
        widget.variable.trace_add(
            "write",
            lambda *_args, key=draft_key, input_widget=widget: (
                self._drafts.__setitem__(key, input_widget.draft())
                if key not in self._committing_drafts else None
            ),
        )
        self._field_widgets[draft_key] = widget
        self._field_enabled[draft_key] = enabled
        widget.set_enabled(enabled and not self._busy)
        return widget

    def _submit_plan(self, action: str, args: Json, callback: Callable[[Json], None], message: str) -> None:
        captured = dict(args)
        self.app.submit(
            lambda: self.app.controller.plan(action, captured),
            on_success=callback,
            message=message,
        )

    def _label(self, parent: tk.Misc, text: str, *, wrap: int = 360, style: str | None = None) -> ttk.Label:
        options: Json = {"text": text, "wraplength": wrap, "justify": tk.LEFT}
        if style:
            options["style"] = style
        label = ttk.Label(parent, **options)

        def resize(_event=None):
            # Only the parent's allocated width is authoritative. Grid cell
            # widths still depend on label requests during geometry settlement.
            allocated = parent.winfo_width()
            if allocated <= 1:
                return
            if label.winfo_manager() == "grid":
                layout = label.grid_info()
                raw_padding = layout.get("padx", 0)
                padding = raw_padding if isinstance(raw_padding, (tuple, list)) else parent.tk.splitlist(str(raw_padding))
                allocated -= sum(parent.winfo_pixels(value) for value in padding) * (2 if len(padding) == 1 else 1)
            width = max(1, min(allocated - 8, wrap))
            if int(label.cget("wraplength")) != width:
                label.configure(wraplength=width)

        binding = parent.bind("<Configure>", resize, add=True)
        label.bind("<Map>", resize)

        def cleanup(event):
            if event.widget is label:
                parent.unbind("<Configure>", binding)

        label.bind("<Destroy>", cleanup)
        return label

    # -- palette and goal picker ------------------------------------------

    def _palette_entries(self) -> list[Json]:
        presets = [
            {
                "key": f"module:{item.get('moduleType', '')}",
                "moduleType": item.get("moduleType", ""),
                "title": item.get("title", item.get("moduleType", "")),
                "description": item.get("description", ""),
                "category": item.get("category", ""),
            }
            for item in self._views.get("palette", [])
            if item.get("moduleType") not in {"primitive", "rest"}
        ]
        return [dict(item) for item in _BASIC_STEPS] + presets

    def _render_palette(self) -> None:
        body = self._palette_scroll.body
        _clear(body)
        body.columnconfigure(0, weight=1)
        ttk.Label(body, text="모듈 팔레트", font=("TkDefaultFont", 12, "bold")).grid(row=0, column=0, sticky="w", padx=8, pady=(8, 3))
        ttk.Entry(body, textvariable=self._palette_query).grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))

        query = self._palette_query.get().strip().casefold()
        entries = [
            item for item in self._palette_entries()
            if not query or query in " ".join(
                str(item.get(key, "")) for key in ("title", "description", "category", "moduleType")
            ).casefold()
        ]
        basic_keys = {item["key"] for item in _BASIC_STEPS}
        row = 2
        for heading, filtered in (
            ("기본 스텝", [item for item in entries if item.get("key") in basic_keys]),
            ("실험 프리셋", [item for item in entries if item.get("key") not in basic_keys]),
        ):
            ttk.Label(body, text=heading, font=("TkDefaultFont", 10, "bold")).grid(row=row, column=0, sticky="w", padx=8, pady=(8, 2))
            row += 1
            for item in filtered:
                frame = ttk.Frame(body, padding=5)
                frame.grid(row=row, column=0, sticky="ew", padx=6, pady=2)
                frame.columnconfigure(0, weight=1)
                ttk.Label(frame, text=str(item.get("title", ""))).grid(row=0, column=0, sticky="w")
                self._label(frame, str(item.get("description", "")), wrap=210).grid(row=1, column=0, sticky="ew")
                self._button(frame, "추가", lambda entry=dict(item): self._add_palette(entry)).grid(row=0, column=1, rowspan=2, padx=(5, 0))
                row += 1
        if not entries:
            self._label(body, "검색 결과가 없습니다.", wrap=220).grid(row=row, column=0, sticky="ew", padx=8, pady=8)

        ttk.Separator(body).grid(row=row + 1, column=0, sticky="ew", padx=8, pady=10)
        ttk.Label(body, text="실험 목적", font=("TkDefaultFont", 10, "bold")).grid(row=row + 2, column=0, sticky="w", padx=8)
        for offset, goal in enumerate(self._views.get("goals", []), start=row + 3):
            title = f"{goal.get('title', '')}\n{goal.get('question', '')}"
            self._button(body, title, lambda goal_id=goal.get("goalId", ""): self.app.perform("addGoal", {"goalId": goal_id})).grid(
                row=offset, column=0, sticky="ew", padx=8, pady=2
            )

    def _add_palette(self, entry: Json) -> None:
        args: Json = {"moduleType": entry.get("moduleType", "")}
        if entry.get("params"):
            args["params"] = dict(entry["params"])
        self.app.perform("addModule", args)

    # -- vertical flow -----------------------------------------------------

    def _render_flow(self) -> None:
        body = self._flow_scroll.body
        _clear(body)
        self._flow_vars.clear()
        body.columnconfigure(0, weight=1)
        summary = self._views.get("summary", {})
        ttk.Label(body, text="프로토콜 흐름", font=("TkDefaultFont", 13, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 0))
        self._label(
            body,
            f"{len(self._views.get('modules', []))}개 구간 · {summary.get('totalSteps', 0)}스텝 · {summary.get('durationText', '')}",
            wrap=500,
        ).grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))

        row = 2
        if self._group_selection:
            group = ttk.LabelFrame(body, text=f"연속 선택 {len(self._group_selection)}개", padding=7)
            group.grid(row=row, column=0, sticky="ew", padx=8, pady=4)
            group.columnconfigure(1, weight=1)
            ttk.Label(group, text="이름").grid(row=0, column=0, sticky="w")
            ttk.Entry(group, textvariable=self._group_name).grid(row=0, column=1, sticky="ew", padx=4)
            ttk.Label(group, text="반복").grid(row=1, column=0, sticky="w")
            ttk.Entry(group, textvariable=self._group_repeat, width=8).grid(row=1, column=1, sticky="w", padx=4)
            self._button(group, "내 모듈 만들기", self._create_group).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))
            self._button(group, "선택 해제", self._clear_group).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(3, 0))
            row += 1

        ttk.Label(body, text="START · 실험 시작", anchor=tk.CENTER).grid(row=row, column=0, sticky="ew", padx=35, pady=(6, 3))
        row += 1
        modules = self._views.get("modules", [])
        for index, module in enumerate(modules):
            ttk.Label(body, text="↓", anchor=tk.CENTER).grid(row=row, column=0, sticky="ew")
            row += 1
            box = ttk.LabelFrame(body, text=f"STEP {int(module.get('position', index + 1)):02d}", padding=7)
            box.grid(row=row, column=0, sticky="ew", padx=8, pady=2)
            box.columnconfigure(1, weight=1)
            module_id = str(module.get("moduleId", ""))
            module_type = str(module.get("moduleType", ""))
            selected = module_id == self._views.get("selectedModule")
            grouped = module_type == "sequence"
            mark = tk.BooleanVar(value=module_id in self._group_selection)
            self._flow_vars.append(mark)
            check = ttk.Checkbutton(
                box,
                variable=mark,
                command=lambda mid=module_id: self._toggle_group(mid),
                state="disabled" if grouped else "normal",
            )
            check.grid(row=0, column=0, rowspan=2, sticky="n")
            title = str(module.get("title", module_type))
            self._button(box, ("● " if selected else "") + title, lambda mid=module_id: self.app.select(mid)).grid(row=0, column=1, sticky="ew")
            self._label(
                box,
                f"{module.get('subtitle', '')} · {module.get('steps', 0)}스텝 · {module.get('duration', '')}",
                wrap=430,
            ).grid(row=1, column=1, sticky="ew", padx=4)
            tools = ttk.Frame(box)
            tools.grid(row=0, column=2, rowspan=2, sticky="ne")
            self._button(tools, "↑", lambda mid=module_id: self.app.perform("move", {"moduleId": mid, "delta": -1}), width=3).pack(side=tk.LEFT)
            self._button(tools, "↓", lambda mid=module_id: self.app.perform("move", {"moduleId": mid, "delta": 1}), width=3).pack(side=tk.LEFT)
            self._button(tools, "복제", lambda mid=module_id: self.app.perform("duplicateModule", {"moduleId": mid})).pack(side=tk.LEFT, padx=(3, 0))
            if grouped:
                self._button(tools, "해제", lambda mid=module_id, name=title: self._ungroup(mid, name)).pack(side=tk.LEFT, padx=(3, 0))
            self._button(tools, "삭제", lambda mid=module_id, name=title: self._remove_module(mid, name)).pack(side=tk.LEFT, padx=(3, 0))

            if module.get("error"):
                self._label(box, f"조건 확인 필요: {module.get('error')}", wrap=500).grid(row=2, column=1, columnspan=2, sticky="ew", padx=4, pady=(3, 0))
            if grouped or module_type == "custom_steps" or int(module.get("steps", 0) or 0) > 1:
                views = ttk.Frame(box)
                views.grid(row=3, column=1, columnspan=2, sticky="ew", pady=(5, 0))
                expanded = module_id in self._expanded
                self._button(views, "구성 접기" if expanded else "구성 펼치기", lambda mid=module_id: self._toggle_expand(mid)).pack(side=tk.LEFT)
                self._button(views, "크게 보기", lambda mid=module_id, name=title: self._open_large_content(mid, name)).pack(side=tk.LEFT, padx=4)
                if expanded:
                    target = ttk.Frame(box, padding=(4, 6))
                    target.grid(row=4, column=0, columnspan=3, sticky="ew")
                    content = self._content_cache.get((self._revision, module_id, None))
                    if content is None:
                        self._label(target, "구성을 불러오는 중…").pack(anchor="w", fill=tk.X)
                    else:
                        self._render_content(target, content, compact=True)
            row += 1

        ttk.Label(body, text="↓", anchor=tk.CENTER).grid(row=row, column=0, sticky="ew")
        ttk.Label(body, text="END · 실험 종료", anchor=tk.CENTER).grid(row=row + 1, column=0, sticky="ew", padx=35, pady=(3, 12))

    def _toggle_group(self, module_id: str) -> None:
        modules = self._views.get("modules", [])
        ids = [str(item.get("moduleId", "")) for item in modules]
        if module_id not in ids:
            return
        index = ids.index(module_id)
        selected = list(self._group_selection)
        positions = sorted(ids.index(item) for item in selected if item in ids)
        if module_id not in selected:
            if not positions or index in {positions[0] - 1, positions[-1] + 1}:
                selected.append(module_id)
                selected.sort(key=ids.index)
            else:
                selected = [module_id]
        elif len(selected) == 1:
            selected = []
        elif index in {positions[0], positions[-1]}:
            selected.remove(module_id)
        else:
            selected = [module_id]
        self._group_selection = selected
        self.refresh()

    def _clear_group(self) -> None:
        self._group_selection = []
        self.refresh()

    def _create_group(self) -> None:
        try:
            repeat = int(self._group_repeat.get())
        except ValueError:
            messagebox.showerror("그룹", "반복 횟수는 정수여야 합니다.", parent=self.app.root)
            return
        name = self._group_name.get().strip()
        if len(self._group_selection) < 2 or not name or not 1 <= repeat <= 10000:
            messagebox.showerror("그룹", "연속된 모듈 2개 이상, 이름, 1–10000 반복을 확인하세요.", parent=self.app.root)
            return
        args = {"moduleIds": list(self._group_selection), "name": name, "repeatCount": repeat}
        self._group_selection = []
        self.app.perform("groupModules", args)

    def _remove_module(self, module_id: str, title: str) -> None:
        if messagebox.askyesno("모듈 삭제", f"‘{title}’ 박스를 삭제할까요?\n되돌리기로 복구할 수 있습니다.", parent=self.app.root):
            self.app.perform("removeModule", {"moduleId": module_id})

    def _ungroup(self, module_id: str, title: str) -> None:
        if messagebox.askyesno("그룹 해제", f"‘{title}’을 반복 횟수만큼 풀어 놓을까요?", parent=self.app.root):
            self.app.perform("ungroupModule", {"moduleId": module_id})

    # -- expanded module contents ----------------------------------------

    def _request_content(self, module_id: str, child_index: int | None, callback: Callable[[Json], None]) -> None:
        revision = self._revision
        self.app.submit(
            lambda: self.app.controller.module_content(module_id, child_index),
            on_success=lambda result: self._accept_content(revision, module_id, child_index, result, callback),
            message="모듈 구성을 불러오는 중…",
        )

    def _accept_content(
        self,
        revision: int,
        module_id: str,
        child_index: int | None,
        result: Json,
        callback: Callable[[Json], None],
    ) -> None:
        if not _alive(self) or revision != self._revision:
            return
        self._content_cache[(revision, module_id, child_index)] = result
        callback(result)

    def _toggle_expand(self, module_id: str) -> None:
        if module_id in self._expanded:
            self._expanded.remove(module_id)
            self.refresh()
            return
        self._expanded.add(module_id)
        key = (self._revision, module_id, None)
        if key in self._content_cache:
            self.refresh()
            return
        self.refresh()
        self._request_content(module_id, None, lambda _result: self.refresh())

    def _open_large_content(self, module_id: str, title: str, child_index: int | None = None) -> None:
        key = (self._revision, module_id, child_index)
        content = self._content_cache.get(key)
        if content is not None:
            self._content_dialog(title, content)
            return
        self._request_content(module_id, child_index, lambda result: self._content_dialog(title, result))

    def _content_dialog(self, title: str, content: Json) -> None:
        window = tk.Toplevel(self.app.root)
        window.title(f"{title} · 모듈 구성")
        window.geometry("780x720")
        window.transient(self.app.root)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        scroll = ScrollFrame(window)
        scroll.grid(row=0, column=0, sticky="nsew")
        self._render_content(scroll.body, content, compact=False)
        ttk.Button(window, text="닫기", command=window.destroy).grid(row=1, column=0, pady=8)

    def _render_content(self, parent: tk.Misc, content: Json, *, compact: bool) -> None:
        parent.columnconfigure(0, weight=1)
        module_id = str(content.get("moduleId", ""))
        child_index = content.get("childIndex")
        ttk.Label(parent, text=str(content.get("title", "모듈 구성")), font=("TkDefaultFont", 11, "bold")).grid(row=0, column=0, sticky="w")
        row = 1
        children = content.get("children", [])
        if children:
            for child in children:
                frame = ttk.LabelFrame(parent, text=f"{int(child.get('index', 0)) + 1}. {child.get('title', '')}", padding=6)
                frame.grid(row=row, column=0, sticky="ew", pady=3)
                frame.columnconfigure(0, weight=1)
                self._label(frame, f"{child.get('summary', '')} · {child.get('stepCount', 0)}스텝" + (f" · ×{child.get('repeatCount')}" if int(child.get('repeatCount', 1) or 1) > 1 else ""), wrap=600).grid(row=0, column=0, sticky="ew")
                form = child.get("form", {})
                subrow = 1
                for section in form.get("sections", []):
                    ttk.Label(frame, text=str(section.get("title", "")), font=("TkDefaultFont", 9, "bold")).grid(row=subrow, column=0, sticky="w", pady=(5, 1))
                    subrow += 1
                    for field in section.get("fields", []):
                        key = (module_id, "child", child.get("index"), field.get("key"))
                        widget = self._field(frame, field, key, "setGroupChildParam", {"moduleId": module_id, "index": child.get("index")})
                        widget.grid(row=subrow, column=0, sticky="ew", pady=1)
                        subrow += 1
                self._button(
                    frame,
                    "내부 스텝 크게 보기",
                    lambda index=int(child.get("index", 0)), name=str(child.get("title", "")): self._open_large_content(module_id, name, index),
                ).grid(row=subrow, column=0, sticky="w", pady=(5, 0))
                row += 1
            return

        customized = bool(content.get("customized"))
        if content.get("steps") and not customized:
            self._label(parent, "프리셋 원본 · 읽기 전용. 개별 스텝을 바꾸려면 먼저 분리하세요.", wrap=650).grid(row=row, column=0, sticky="ew", pady=3)
            action = "detach" if child_index is None else "detachGroupChild"
            args = {"moduleId": module_id} if child_index is None else {"moduleId": module_id, "index": child_index}
            self._button(parent, "개별 스텝 수정으로 전환", lambda a=action, payload=args: self.app.perform(a, payload)).grid(row=row + 1, column=0, sticky="w", pady=(0, 5))
            row += 2

        for step in content.get("steps", []):
            title = f"STEP {step.get('number', '')} · {step.get('title', step.get('stepType', ''))}"
            frame = ttk.LabelFrame(parent, text=title, padding=6)
            frame.grid(row=row, column=0, sticky="ew", pady=3)
            frame.columnconfigure(0, weight=1)
            if step.get("summary"):
                self._label(frame, str(step.get("summary", "")), wrap=640).grid(row=0, column=0, sticky="ew")
            for field_row, field in enumerate(step.get("fields", []), start=1):
                action = "setStepField" if child_index is None else "setGroupChildStepField"
                args: Json = {"moduleId": module_id, "index": step.get("index")}
                if child_index is not None:
                    args["childIndex"] = child_index
                key = (module_id, "content-step", child_index, step.get("index"), field.get("key"))
                widget = self._field(frame, field, key, action, args, enabled=customized)
                widget.grid(row=field_row, column=0, sticky="ew", pady=1)
            row += 1
            if compact and row > 8:
                self._label(parent, "나머지 스텝은 ‘크게 보기’에서 확인하세요.", wrap=500).grid(row=row, column=0, sticky="ew")
                break

    # -- selected module inspector ---------------------------------------

    def _render_core(self, body, form):
        module_id = form.get("moduleId", "")
        if self._core_module != module_id:
            self._core_child = None
            self._core_module = module_id
        self._core_selectors = []
        box = ttk.LabelFrame(body, text="실험 핵심 조건", padding=8)
        box.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        box.columnconfigure(0, weight=1)
        self._label(box, "기준용량·전압은 프로젝트 전체, 아래 조건은 선택한 구간에만 적용됩니다.").grid(row=0, column=0, sticky="ew")
        row = 1
        for setup in self._views.get("setupFields", []):
            if setup["key"] not in {"nominal_capacity_mAh", "v_max", "v_min"}:
                continue
            field = {**setup, "kind": "text", "choices": [], "hasError": bool(setup.get("issue")),
                     "issues": [setup["issue"]] if setup.get("issue") else []}
            if setup.get("numericValue") is not None:
                field["value"] = str(setup["numericValue"])
            if setup["key"] == "nominal_capacity_mAh":
                field["label"] = "기준용량 (mAh)"
            else:
                field["label"] += " (V)"
            self._field(box, field, ("setup", setup["key"]), "setCellValue", {}).grid(row=row, column=0, sticky="ew")
            row += 1
        modules = self._views.get("modules", [])
        labels = [f"{m['position']}. {m['title']}" for m in modules]
        picker = ttk.Combobox(box, state="readonly", values=labels)
        picker.grid(row=row, column=0, sticky="ew", pady=6)
        self._core_selectors.append(picker)
        if modules:
            picker.current(next((i for i, m in enumerate(modules) if m["moduleId"] == module_id), 0))
            picker.bind("<<ComboboxSelected>>", lambda _e: self.app.select(modules[picker.current()]["moduleId"]))
        row += 1
        children = self._views.get("groupChildren", [])
        chosen = next((c for c in children if c["index"] == self._core_child), None)
        if chosen is None:
            self._core_child = None
        if children:
            child_picker = ttk.Combobox(box, state="readonly", values=["그룹 전체 설정", *[f"{c['index'] + 1}. {c['form']['title']}" for c in children]])
            child_picker.current(children.index(chosen) + 1 if chosen else 0)
            child_picker.grid(row=row, column=0, sticky="ew", pady=4)
            self._core_selectors.append(child_picker)
            def choose(_event):
                self._core_child = children[child_picker.current() - 1]["index"] if child_picker.current() else None
                self.refresh()
            child_picker.bind("<<ComboboxSelected>>", choose)
            row += 1
        chosen_form = chosen["form"] if chosen else form
        for section in chosen_form.get("sections", []):
            for field in section.get("fields", []):
                if not field.get("keyCondition"):
                    continue
                key = ((module_id, "group-param", chosen["index"], field["key"]) if chosen else (module_id, "param", field["key"]))
                args = {"moduleId": module_id, **({"index": chosen["index"]} if chosen else {})}
                self._field(box, field, key, "setGroupChildParam" if chosen else "setParam", args).grid(row=row, column=0, sticky="ew")
                row += 1
        self._label(box, self._views.get("summary", {}).get("durationText", "") + " · 안전 시간제한은 예상 시간이 아닙니다.").grid(row=row, column=0, sticky="ew", pady=4)

    def _render_inspector(self) -> None:
        body = self._inspector_scroll.body
        _clear(body)
        body.columnconfigure(0, weight=1)
        form = self._views.get("form", {})
        module_id = str(form.get("moduleId", ""))
        self._render_core(body, form)
        ttk.Label(body, text="선택한 모듈 상세", font=("TkDefaultFont", 13, "bold")).grid(row=1, column=0, sticky="w", padx=9, pady=(8, 0))
        if not module_id:
            self._label(body, "흐름에서 편집할 모듈을 선택하세요.").grid(row=2, column=0, sticky="ew", padx=9, pady=8)
            self._render_tools(body, 3)
            return

        ttk.Label(body, text=str(form.get("title", "")), font=("TkDefaultFont", 11, "bold")).grid(row=2, column=0, sticky="w", padx=9)
        trust = str(form.get("trust", ""))
        limitations = _join_lines(form.get("limitations", []))
        if trust or limitations:
            self._label(body, f"검증 상태: {trust}\n{limitations}".strip(), wrap=430).grid(row=3, column=0, sticky="ew", padx=9, pady=(2, 6))
        row = 4

        actions = ttk.Frame(body)
        actions.grid(row=row, column=0, sticky="ew", padx=8, pady=3)
        self._button(actions, "프리셋 분리", lambda: self._detach_selected(module_id)).pack(side=tk.LEFT)
        self._button(actions, "내 프리셋 저장", lambda: self._save_method_dialog(module_id)).pack(side=tk.LEFT, padx=4)
        module_type = str(form.get("moduleType", ""))
        if module_type == "qc":
            self._button(actions, "QC 연동 계산", lambda: self._qc_dialog(module_id)).pack(side=tk.LEFT, padx=4)
        if module_type == "qpeed":
            self._button(actions, "QPEED 결과 불러오기", lambda: self._qpeed_dialog(module_id)).pack(side=tk.LEFT, padx=4)
        row += 1

        derived = form.get("derived", [])
        if derived:
            box = ttk.LabelFrame(body, text="자동 계산", padding=6)
            box.grid(row=row, column=0, sticky="ew", padx=8, pady=4)
            for item in derived:
                self._label(box, f"{item.get('label', '')}: {item.get('text', '')}\n{item.get('help', '')}".strip(), wrap=420).pack(anchor="w", fill=tk.X, pady=1)
            row += 1

        for section in form.get("sections", []):
            visible_fields = [f for f in section.get("fields", []) if self._core_child is not None or not f.get("keyCondition")]
            if not visible_fields:
                continue
            box = ttk.LabelFrame(body, text=str(section.get("title", "조건")), padding=6)
            box.grid(row=row, column=0, sticky="ew", padx=8, pady=4)
            box.columnconfigure(0, weight=1)
            for field_row, field in enumerate(visible_fields):
                key = (module_id, "param", field.get("key"))
                widget = self._field(box, field, key, "setParam", {"moduleId": module_id})
                widget.grid(row=field_row, column=0, sticky="ew", pady=2)
            row += 1

        for child in self._views.get("groupChildren", []):
            child_form = child.get("form", {})
            box = ttk.LabelFrame(body, text=f"그룹 내부 {int(child.get('index', 0)) + 1}. {child_form.get('title', '')}", padding=6)
            box.grid(row=row, column=0, sticky="ew", padx=8, pady=4)
            box.columnconfigure(0, weight=1)
            field_row = 0
            for section in child_form.get("sections", []):
                ttk.Label(box, text=str(section.get("title", "")), font=("TkDefaultFont", 9, "bold")).grid(row=field_row, column=0, sticky="w")
                field_row += 1
                for field in section.get("fields", []):
                    if self._core_child == child.get("index") and field.get("keyCondition"):
                        continue
                    key = (module_id, "group-param", child.get("index"), field.get("key"))
                    widget = self._field(box, field, key, "setGroupChildParam", {"moduleId": module_id, "index": child.get("index")})
                    widget.grid(row=field_row, column=0, sticky="ew", pady=2)
                    field_row += 1
            row += 1

        if self._views.get("canEditSteps"):
            row = self._render_custom_steps(body, row, module_id)
        self._render_tools(body, row)

    def _detach_selected(self, module_id: str) -> None:
        if self._views.get("canEditSteps"):
            messagebox.showinfo("프리셋 분리", "이미 개별 스텝 편집 상태입니다.", parent=self.app.root)
            return
        if messagebox.askyesno("프리셋 분리", "원본 프리셋 연결을 끊고 개별 스텝 수정으로 전환할까요?", parent=self.app.root):
            self.app.perform("detach", {"moduleId": module_id})

    def _render_custom_steps(self, body: tk.Misc, row: int, module_id: str) -> int:
        box = ttk.LabelFrame(body, text="개별 스텝 편집", padding=6)
        box.grid(row=row, column=0, sticky="ew", padx=8, pady=4)
        box.columnconfigure(0, weight=1)
        controls = ttk.Frame(box)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        ttk.Combobox(controls, textvariable=self._step_kind, values=[key for key, _label in _STEP_KINDS], state="readonly", width=17).pack(side=tk.LEFT)
        steps = self._views.get("customSteps", [])
        self._button(
            controls,
            "맨 뒤에 추가",
            lambda: self.app.perform("insertStep", {"moduleId": module_id, "index": len(steps), "kind": self._step_kind.get()}),
        ).pack(side=tk.LEFT, padx=4)
        self._label(controls, "END는 항상 마지막이며 구간을 비울 수 없습니다.", wrap=240).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        for offset, step in enumerate(steps, start=1):
            frame = ttk.LabelFrame(box, text=f"{step.get('number', offset)}. {step.get('stepType', '')} · {step.get('mode', '')}", padding=5)
            frame.grid(row=offset, column=0, sticky="ew", pady=2)
            frame.columnconfigure(0, weight=1)
            tools = ttk.Frame(frame)
            tools.grid(row=0, column=0, sticky="e")
            index = int(step.get("index", offset - 1))
            self._button(tools, "↑", lambda idx=index: self.app.perform("moveStep", {"moduleId": module_id, "index": idx, "delta": -1}), width=3).pack(side=tk.LEFT)
            self._button(tools, "↓", lambda idx=index: self.app.perform("moveStep", {"moduleId": module_id, "index": idx, "delta": 1}), width=3).pack(side=tk.LEFT)
            self._button(tools, "삭제", lambda idx=index: self.app.perform("removeStep", {"moduleId": module_id, "index": idx})).pack(side=tk.LEFT, padx=(3, 0))
            for field_row, field in enumerate(step.get("fields", []), start=1):
                normalized = dict(field)
                normalized.setdefault("value", normalized.get("text", ""))
                normalized.setdefault("numericValues", None)
                normalized.setdefault("choices", [])
                normalized.setdefault("checked", False)
                key = (module_id, "custom-step", index, field.get("key"))
                widget = self._field(frame, normalized, key, "setStepField", {"moduleId": module_id, "index": index})
                widget.grid(row=field_row, column=0, sticky="ew", pady=1)
        return row + 1

    def _save_method_dialog(self, module_id: str) -> None:
        window = tk.Toplevel(self.app.root)
        window.title("내 프리셋으로 저장")
        window.transient(self.app.root)
        window.columnconfigure(1, weight=1)
        name = tk.StringVar()
        description = tk.StringVar(value="사용자 실험 프리셋")
        ttk.Label(window, text="이름").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(window, textvariable=name, width=42).grid(row=0, column=1, sticky="ew", padx=8, pady=6)
        ttk.Label(window, text="설명").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(window, textvariable=description).grid(row=1, column=1, sticky="ew", padx=8, pady=6)

        def save() -> None:
            captured_name = name.get().strip()
            captured_description = description.get().strip()
            if not captured_name:
                messagebox.showerror("저장", "프리셋 이름을 입력하세요.", parent=window)
                return
            def saved(_result: Any) -> None:
                if not _alive(window):
                    return
                window.destroy()
                self.app.status("선택한 모듈을 내 프리셋에 저장했습니다.")

            accepted = self.app.submit(
                lambda: self.app.controller.save_method(captured_name, captured_description, [module_id]),
                on_success=saved,
                message="프리셋을 저장하는 중…",
            )
            if accepted:
                save_button.configure(state="disabled")

        save_button = ttk.Button(window, text="저장", command=save)
        save_button.grid(row=2, column=0, columnspan=2, pady=8)

    # -- campaign, period and QC tools -----------------------------------

    def _render_tools(self, body: tk.Misc, row: int) -> None:
        tools = ttk.LabelFrame(body, text="프로토콜 도구", padding=7)
        tools.grid(row=row, column=0, sticky="ew", padx=8, pady=(10, 12))
        self._button(tools, "사이클 + RPT 캠페인", self._campaign_dialog).pack(fill=tk.X, pady=2)
        self._button(tools, "기간 기준 사이클 계산", self._budget_dialog).pack(fill=tk.X, pady=2)

    def _campaign_dialog(self) -> None:
        window = tk.Toplevel(self.app.root)
        window.title("사이클 + RPT 캠페인")
        window.geometry("620x620")
        window.transient(self.app.root)
        defaults = {
            "totalCycles": "200", "rptEvery": "50", "chargeCRate": "0.5",
            "dischargeCRate": "0.5", "dcirRates": "1.5", "referenceCRate": "0.3333333333",
            "startSoc": "100", "preparationPolicy": "아직 확인하지 않음",
        }
        variables = {key: tk.StringVar(value=value) for key, value in defaults.items()}
        baseline = tk.BooleanVar(value=True)
        policies = {
            "아직 확인하지 않음": "unconfirmed_entry",
            "입력한 시작 SOC를 직접 확인함": "user_confirmed_start_soc",
            "각 RPT 앞에 완충·휴지 준비 구간 추가": "charge_to_full",
        }
        labels = (
            ("총 사이클 (회)", "totalCycles"), ("RPT 주기 (사이클)", "rptEvery"), ("충전율 (C)", "chargeCRate"),
            ("방전율 (C)", "dischargeCRate"), ("DC-IR 펄스 전류 (C · 한 개)", "dcirRates"),
            ("RPT 기준 방전율 (C)", "referenceCRate"), ("RPT 시작 SOC (%)", "startSoc"),
        )
        window.columnconfigure(1, weight=1)
        for row, (label, key) in enumerate(labels):
            ttk.Label(window, text=label).grid(row=row, column=0, sticky="w", padx=9, pady=4)
            ttk.Entry(window, textvariable=variables[key]).grid(row=row, column=1, sticky="ew", padx=9, pady=4)
        ttk.Label(window, text="RPT 진입 상태").grid(row=7, column=0, sticky="w", padx=9, pady=4)
        policy = ttk.Combobox(
            window,
            textvariable=variables["preparationPolicy"],
            state="readonly",
            values=tuple(policies),
        )
        policy.grid(row=7, column=1, sticky="ew", padx=9, pady=4)
        ttk.Checkbutton(window, text="시작 전 기준 RPT 포함", variable=baseline).grid(
            row=8, column=0, columnspan=2, sticky="w", padx=9, pady=4,
        )
        ttk.Label(window, text="완충 준비 구간을 추가할 때 시작 SOC는 100%입니다. C는 입력 기준용량에 대한 충·방전율입니다.",
                  wraplength=590).grid(row=9, column=0, columnspan=2, sticky="w", padx=9, pady=4)
        notice = tk.StringVar()
        ttk.Label(window, textvariable=notice, wraplength=590).grid(row=11, column=0, columnspan=2, sticky="w", padx=9)
        preview_text = tk.Text(window, height=12, wrap=tk.WORD, state="disabled")
        preview_text.grid(row=12, column=0, columnspan=2, sticky="nsew", padx=9, pady=8)
        window.rowconfigure(12, weight=1)

        def collect() -> Json | None:
            try:
                args = {
                    "totalCycles": int(variables["totalCycles"].get()),
                    "rptEvery": int(variables["rptEvery"].get()),
                    "chargeCRate": float(variables["chargeCRate"].get()),
                    "dischargeCRate": float(variables["dischargeCRate"].get()),
                    "dcirRates": [float(variables["dcirRates"].get())],
                    "referenceCRate": float(variables["referenceCRate"].get()),
                    "startSoc": float(variables["startSoc"].get()) / 100.0,
                    "preparationPolicy": policies[variables["preparationPolicy"].get()],
                    "baselineRpt": baseline.get(),
                }
                if not all(math.isfinite(args[key]) for key in ("chargeCRate", "dischargeCRate", "referenceCRate", "startSoc")) or not math.isfinite(args["dcirRates"][0]):
                    raise ValueError("finite numbers required")
                return args
            except ValueError:
                messagebox.showerror("캠페인", "숫자 입력을 확인하세요.", parent=window)
                return None

        def show(result: Json) -> None:
            blocks = "\n".join(f"· {item.get('title', '')}" for item in result.get("blocks", []))
            text = "\n".join(part for part in (blocks, _join_lines(result.get("warnings")), _join_lines(result.get("errors"))) if part)
            preview_text.configure(state="normal")
            preview_text.delete("1.0", tk.END)
            preview_text.insert("1.0", text or "추가할 블록이 없습니다.")
            preview_text.configure(state="disabled")

        def preview() -> None:
            if self.app.busy:
                return
            ticket = guard.begin()
            args = collect()
            if args is not None:
                self._submit_plan(
                    "campaign", args,
                    lambda result: guard.accept(ticket, args if result.get("ok") and result.get("blocks") else None, lambda: show(result)),
                    "캠페인을 검토하는 중…",
                )

        buttons = ttk.Frame(window)
        buttons.grid(row=10, column=0, columnspan=2, pady=5)
        ttk.Button(buttons, text="미리보기", command=preview).pack(side=tk.LEFT)
        apply_button = ttk.Button(buttons, text="추가", command=lambda: guard.apply("addCampaign"), state="disabled")
        apply_button.pack(side=tk.LEFT, padx=5)
        guard = _DialogPreview(self, window, apply_button,
                               lambda: (*[variable.get() for variable in variables.values()], baseline.get()), notice)
        for variable in (*variables.values(), baseline):
            guard.watch(variable)

    def _qc_dialog(self, module_id: str) -> None:
        window = tk.Toplevel(self.app.root)
        window.title("QC 급속충전 연동 계산")
        window.geometry("560x380")
        window.transient(self.app.root)
        ttk.Label(window, text="단계별 충전율 (C · 쉼표 구분, 예: 4, 3, 2)").pack(anchor="w", padx=9, pady=(9, 3))
        rates_var = tk.StringVar()
        ttk.Entry(window, textvariable=rates_var).pack(fill=tk.X, padx=9)
        result_box = tk.Text(window, height=12, wrap=tk.WORD, state="disabled")
        result_box.pack(fill=tk.BOTH, expand=True, padx=9, pady=8)
        notice = tk.StringVar()
        ttk.Label(window, textvariable=notice, wraplength=530).pack(anchor="w", padx=9)

        def parse_rates() -> list[float] | None:
            try:
                rates = [float(item.strip()) for item in rates_var.get().split(",")]
            except ValueError:
                rates = []
            if not rates or any(not math.isfinite(rate) or rate <= 0 for rate in rates):
                messagebox.showerror("QC", "0보다 큰 충전율을 쉼표로 구분해 입력하세요.", parent=window)
                return None
            return rates

        def show(result: Json) -> None:
            text = _join_lines(result.get("notes"))
            if result.get("times"):
                text += "\n시간: " + " · ".join(str(value) for value in result["times"]) + " 초"
            warnings = _join_lines(result.get("warnings"))
            if warnings:
                text += "\n\n" + warnings
            if result.get("errors"):
                text += "\n\n" + _join_lines(result["errors"])
            result_box.configure(state="normal")
            result_box.delete("1.0", tk.END)
            result_box.insert("1.0", text.strip())
            result_box.configure(state="disabled")

        def preview() -> None:
            if self.app.busy:
                return
            ticket = guard.begin()
            rates = parse_rates()
            if rates is not None:
                args = {"moduleId": module_id, "rates": rates}
                self._submit_plan(
                    "qcFastCharge", args,
                    lambda result: guard.accept(ticket, args if result.get("ok") else None, lambda: show(result)),
                    "QC 조건을 계산하는 중…",
                )

        buttons = ttk.Frame(window)
        buttons.pack(pady=(0, 9))
        ttk.Button(buttons, text="미리보기", command=preview).pack(side=tk.LEFT)
        apply_button = ttk.Button(buttons, text="적용", command=lambda: guard.apply("applyQcFastCharge"), state="disabled")
        apply_button.pack(side=tk.LEFT, padx=5)
        guard = _DialogPreview(self, window, apply_button, rates_var.get, notice)
        guard.watch(rates_var)

    def _budget_dialog(self) -> None:
        modules = self._views.get("modules", [])
        selected = str(self._views.get("selectedModule", ""))
        target = next((item for item in modules if item.get("moduleId") == selected and item.get("moduleType") in {"cycle_life", "insitu_cycle"}), None)
        target = target or next((item for item in modules if item.get("moduleType") in {"cycle_life", "insitu_cycle"}), None)
        if target is None:
            messagebox.showinfo("기간 기준 사이클", "먼저 수명 사이클 프로토콜을 추가하세요.", parent=self.app.root)
            return
        window = tk.Toplevel(self.app.root)
        window.title("기간 기준 사이클 계산")
        window.transient(self.app.root)
        days = tk.StringVar(value="14")
        step = tk.StringVar(value="50")
        ttk.Label(window, text=f"대상: {target.get('title', '')}").grid(row=0, column=0, columnspan=2, sticky="w", padx=9, pady=7)
        ttk.Label(window, text="기간 (일)").grid(row=1, column=0, sticky="w", padx=9, pady=4)
        ttk.Entry(window, textvariable=days).grid(row=1, column=1, padx=9, pady=4)
        ttk.Label(window, text="사이클 간격 (회)").grid(row=2, column=0, sticky="w", padx=9, pady=4)
        ttk.Entry(window, textvariable=step).grid(row=2, column=1, padx=9, pady=4)
        result_var = tk.StringVar()
        self._label(window, "", wrap=420).grid(row=4, column=0, columnspan=2, sticky="ew", padx=9, pady=7)
        result_label = window.grid_slaves(row=4, column=0)[0]
        notice = tk.StringVar()
        ttk.Label(window, textvariable=notice, wraplength=420).grid(row=5, column=0, columnspan=2, sticky="w", padx=9, pady=4)

        def preview() -> None:
            if self.app.busy:
                return
            ticket = guard.begin()
            try:
                args = {"days": float(days.get()), "step": int(step.get()), "moduleId": target.get("moduleId")}
                if not math.isfinite(args["days"]) or args["days"] <= 0 or args["step"] <= 0:
                    raise ValueError("positive period and interval required")
            except ValueError:
                messagebox.showerror("기간 계산", "기간과 사이클 간격을 확인하세요.", parent=window)
                return

            def show(result: Json) -> None:
                result_var.set(str(result.get("text", "")))
                result_label.configure(textvariable=result_var)

            self._submit_plan(
                "cycleBudget", args,
                lambda result: guard.accept(
                    ticket, {"moduleId": args["moduleId"], "count": result["totalCycles"]}
                    if result.get("ok") and result.get("totalCycles") else None, lambda: show(result),
                ),
                "가능한 사이클 수를 계산하는 중…",
            )

        buttons = ttk.Frame(window)
        buttons.grid(row=3, column=0, columnspan=2, pady=6)
        ttk.Button(buttons, text="계산", command=preview).pack(side=tk.LEFT)
        apply_button = ttk.Button(buttons, text="사이클 수 적용", command=lambda: guard.apply("setCycleCount"), state="disabled")
        apply_button.pack(side=tk.LEFT, padx=5)
        guard = _DialogPreview(self, window, apply_button, lambda: (days.get(), step.get()), notice)
        guard.watch(days)
        guard.watch(step)

    # -- QPEED CSV/TSV mapping -------------------------------------------

    def _qpeed_dialog(self, module_id: str) -> None:
        window = tk.Toplevel(self.app.root)
        window.title("QPEED SOC setting 결과 불러오기")
        window.geometry("760x700")
        window.transient(self.app.root)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(4, weight=1)
        path_var = tk.StringVar()
        use_capacity = tk.BooleanVar(value=False)
        ttk.Label(window, text="CSV/TSV의 셀·스텝 끝 행을 직접 선택합니다. 전압으로 SOC를 자동 추정하지 않습니다.", wraplength=720).grid(row=0, column=0, sticky="w", padx=9, pady=(9, 4))
        file_row = ttk.Frame(window)
        file_row.grid(row=1, column=0, sticky="ew", padx=9)
        file_row.columnconfigure(0, weight=1)
        ttk.Entry(file_row, textvariable=path_var, state="readonly").grid(row=0, column=0, sticky="ew")
        ttk.Button(file_row, text="파일 선택", command=lambda: self._choose_qpeed_file(path_var, window)).grid(row=0, column=1, padx=(5, 0))
        ttk.Checkbutton(window, text="SOC 열이 없으면 충전용량 ÷ 입력 기준용량 사용", variable=use_capacity).grid(row=2, column=0, sticky="w", padx=9, pady=4)
        mapping_frame = ttk.LabelFrame(window, text="열 대응", padding=6)
        mapping_frame.grid(row=3, column=0, sticky="ew", padx=9, pady=5)
        mapping_frame.columnconfigure(1, weight=1)
        result_frame = ttk.Frame(window)
        result_frame.grid(row=4, column=0, sticky="nsew", padx=9, pady=5)
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(1, weight=1)
        summary_var = tk.StringVar()
        ttk.Label(result_frame, textvariable=summary_var).grid(row=0, column=0, sticky="w")
        candidates = tk.Listbox(result_frame, exportselection=False)
        candidates.grid(row=1, column=0, sticky="nsew")
        detail_var = tk.StringVar()
        ttk.Label(result_frame, textvariable=detail_var, wraplength=700, justify=tk.LEFT).grid(row=2, column=0, sticky="w", pady=4)
        state: Json = {
            "headers": [], "mapping": {}, "preview": None, "text": "", "fileName": "",
            "candidateIds": [], "useReferenceCapacity": False,
        }
        mapping_vars: dict[str, tk.StringVar] = {}
        unit_labels = {
            "voltageUnit": {"단위 확인 필요": "", "V": "V", "mV": "mV"},
            "socUnit": {"단위 확인 필요": "", "0–100%": "%", "0–1 비율": "fraction"},
        }
        mapping_labels = (
            ("voltageColumn", "전압 열"), ("socColumn", "SOC 열 (선택)"), ("stepColumn", "스텝 열 (선택)"),
            ("cellColumn", "셀/채널 열 (선택)"), ("cycleColumn", "사이클 열 (선택)"),
            ("capacityColumn", "충전용량(mAh) 열 (선택)"),
        )

        def render_mapping(headers: list[str], mapping: Json) -> None:
            guard.unwatch(mapping_vars.values())
            _clear(mapping_frame)
            mapping_vars.clear()
            for row, (key, label) in enumerate(mapping_labels):
                ttk.Label(mapping_frame, text=label).grid(row=row, column=0, sticky="w", pady=2)
                var = tk.StringVar(value=str(mapping.get(key, "")))
                mapping_vars[key] = var
                guard.watch(var)
                ttk.Combobox(mapping_frame, textvariable=var, values=["", *headers], state="readonly").grid(row=row, column=1, sticky="ew", padx=5, pady=2)
            for offset, (key, label) in enumerate((
                ("voltageUnit", "전압 단위"),
                ("socUnit", "SOC 단위"),
            ), start=len(mapping_labels)):
                ttk.Label(mapping_frame, text=label).grid(row=offset, column=0, sticky="w", pady=2)
                values = unit_labels[key]
                var = tk.StringVar(value=next(label for label, value in values.items() if value == mapping.get(key, "")))
                mapping_vars[key] = var
                guard.watch(var)
                ttk.Combobox(mapping_frame, textvariable=var, values=tuple(values), state="readonly").grid(row=offset, column=1, sticky="ew", padx=5, pady=2)

        def current_mapping() -> Json:
            return {key: unit_labels[key][var.get()] if key in unit_labels else var.get() for key, var in mapping_vars.items()}

        def show_preview(result: Json, text: str, file_name: str, capacity: bool) -> None:
            if not _alive(window):
                return
            state.update(
                headers=list(result.get("headers", [])), mapping=dict(result.get("mapping", {})),
                preview=result, text=text, fileName=file_name, useReferenceCapacity=capacity,
            )
            render_mapping(state["headers"], state["mapping"])
            rows = list(result.get("candidates", []))
            candidates.delete(0, tk.END)
            ids: list[str] = []
            for item in rows:
                ids.append(str(item.get("id", "")))
                soc = "" if item.get("socPercent") is None else f" · SOC {float(item['socPercent']):.2f}%"
                candidates.insert(tk.END, f"{item.get('cellId') or '셀 미지정'} · 스텝 {item.get('step') or '미지정'} · {item.get('row')}행 · {float(item.get('voltageV', 0)):.4f} V{soc}")
            state["candidateIds"] = ids
            summary_var.set(f"{result.get('rowCount', 0)}행 · 제외 {result.get('invalidRows', 0)}행 · 후보 {len(rows)}개\n{_join_lines(result.get('warnings'))}")
            detail_var.set("")
            apply_button.configure(state="disabled")

        def preview() -> None:
            if self.app.busy:
                return
            ticket = guard.begin()
            path = path_var.get()
            if not path:
                messagebox.showerror("QPEED", "CSV/TSV 파일을 선택하세요.", parent=window)
                return
            mapping = current_mapping()
            capacity = bool(use_capacity.get())

            def work() -> Json:
                file_path = Path(path)
                with file_path.open("rb") as source:
                    data = source.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise ValueError("2 MB 이하로 결과를 내보내 주세요.")
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    text = data.decode("euc-kr")
                args = {"moduleId": module_id, "text": text, "fileName": file_path.name, "mapping": mapping, "useReferenceCapacity": capacity}
                return {
                    "preview": self.app.controller.plan("qpeedVoltage", args), "text": text,
                    "fileName": file_path.name, "useReferenceCapacity": capacity,
                }

            def loaded(result: Json) -> None:
                planned = result["preview"]
                # Preserve the exact resolved mapping signed by the shared
                # planner; adding absent optional keys would change its token.
                args = {
                    "moduleId": module_id, "text": result["text"], "fileName": result["fileName"],
                    "mapping": planned["mapping"], "useReferenceCapacity": capacity, "token": planned["token"],
                }
                guard.accept(
                    ticket, args if planned.get("ok") else None,
                    lambda: show_preview(planned, result["text"], result["fileName"], capacity), enabled=False,
                )

            self.app.submit(
                work, on_success=loaded,
                message="QPEED 결과를 읽는 중…",
            )

        def selected_candidate(_event: Any = None) -> None:
            selection = candidates.curselection()
            preview_data = state.get("preview") or {}
            rows = preview_data.get("candidates", [])
            if not selection or selection[0] >= len(rows):
                detail_var.set("")
                apply_button.configure(state="disabled")
                return
            if not guard.ready():
                return
            item = rows[selection[0]]
            soc = "SOC 정보 없음" if item.get("socPercent") is None else f"SOC {float(item['socPercent']):.2f}% ({item.get('socBasis', '')})"
            detail_var.set(f"{float(item.get('voltageV', 0)):.4f} V · {soc} · 셀 {item.get('cellId') or '미지정'} / 스텝 {item.get('step') or '미지정'} / {item.get('row')}행")
            guard.args["candidateId"] = item["id"]
            apply_button.configure(state="normal")

        def apply() -> None:
            selection = candidates.curselection()
            preview_data = state.get("preview") or {}
            if not selection or not preview_data:
                return
            if guard.ready() and guard.args.get("candidateId") == state["candidateIds"][selection[0]]:
                guard.apply("applyQpeedVoltage")

        candidates.bind("<<ListboxSelect>>", selected_candidate)
        buttons = ttk.Frame(window)
        buttons.grid(row=5, column=0, pady=(2, 9))
        ttk.Button(buttons, text="전압 데이터 미리보기", command=preview).pack(side=tk.LEFT)
        apply_button = ttk.Button(buttons, text="선택 전압 적용", command=apply, state="disabled")
        apply_button.pack(side=tk.LEFT, padx=5)
        notice = tk.StringVar()
        ttk.Label(window, textvariable=notice, wraplength=720).grid(row=6, column=0, sticky="w", padx=9, pady=4)
        guard = _DialogPreview(
            self, window, apply_button,
            lambda: (path_var.get(), use_capacity.get(), tuple(sorted(current_mapping().items()))), notice,
        )
        guard.watch(path_var)
        guard.watch(use_capacity)

        def file_changed(*_args):
            # A new file may have different headers. Discard the old mapping
            # and row selection before its first preview.
            guard.unwatch(mapping_vars.values())
            mapping_vars.clear()
            _clear(mapping_frame)
            state.update(preview=None, candidateIds=[])
            candidates.delete(0, tk.END)
            detail_var.set("")
            summary_var.set("")

        path_var.trace_add("write", file_changed)

    @staticmethod
    def _choose_qpeed_file(path_var: tk.StringVar, parent: tk.Misc) -> None:
        path = filedialog.askopenfilename(
            parent=parent,
            title="SOC setting 결과 선택",
            filetypes=(("CSV/TSV", "*.csv *.tsv *.txt"), ("모든 파일", "*.*")),
        )
        if path:
            path_var.set(path)


__all__ = ["ProtocolPanel"]
