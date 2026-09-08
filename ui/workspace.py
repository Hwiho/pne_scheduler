"""One workspace: 설정 → 프로토콜 → 절차 → 검증 → 내보내기.

Replaces the four separate windows (viewer, flow editor, bulk editor, resume)
as the primary entry point.  The flow canvas is still available from the menu
as an advanced view, but a linear procedure is the default because a PNE
schedule is linear.
"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ..edit.diff import StepDiff
from ..protocol.recipes import ExperimentGoal
from ..spec import units
from ..spec.form import FormField
from .document import ProjectDocument
from .workspace_model import TRUST_LABELS_KO, ValidationRow, WorkspaceModel

BG = "#f6f1ea"
PANEL = "#fffdfa"
INK = "#3b2f27"
MUTED = "#7a6452"
ACCENT = "#245c3d"
DANGER = "#b03a2e"
WARN = "#9a5b00"

AUTOSAVE_INTERVAL_MS = 30_000
FILE_TYPES = [("PNE 스케줄 프로젝트", "*.schproj"), ("모든 파일", "*.*")]


class WorkspaceApp:
    def __init__(self, root: tk.Tk, initial_path: Path | None = None) -> None:
        self.root = root
        self.model = WorkspaceModel()
        self.selected_module: str | None = None
        self._field_widgets: dict[str, tuple[FormField, tk.Variable, ttk.Widget, ttk.Label]] = {}
        self._drag_from: str | None = None

        root.title("PNE 스케줄 워크스페이스")
        root.geometry("1400x900")
        root.configure(bg=BG)
        self._configure_style()
        self._build_menu()
        self._build_header()
        self._build_tabs()
        self._build_status()
        self._bind_keys()

        if initial_path is not None and Path(initial_path).exists():
            self.open_path(Path(initial_path))
        else:
            self._offer_recovery()
        self.refresh_all()
        self.root.after(AUTOSAVE_INTERVAL_MS, self._autosave_tick)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------ chrome

    @staticmethod
    def _configure_style() -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL, relief="flat")
        style.configure("TLabel", background=BG, foreground=INK)
        style.configure("Panel.TLabel", background=PANEL, foreground=INK)
        style.configure("Head.TLabel", font=("TkDefaultFont", 15, "bold"), foreground=INK)
        style.configure("Sub.TLabel", foreground=MUTED, font=("TkDefaultFont", 10))
        style.configure("Hint.TLabel", background=PANEL, foreground=MUTED, font=("TkDefaultFont", 9))
        style.configure("Field.TLabel", background=PANEL, foreground=INK, font=("TkDefaultFont", 10, "bold"))
        style.configure("Good.TLabel", foreground=ACCENT, font=("TkDefaultFont", 10, "bold"))
        style.configure("Warn.TLabel", foreground=WARN)
        style.configure("Bad.TLabel", foreground=DANGER)
        style.configure("BadPanel.TLabel", background=PANEL, foreground=DANGER, font=("TkDefaultFont", 9))
        style.configure("Group.TLabelframe", background=PANEL)
        style.configure("Group.TLabelframe.Label", background=PANEL, foreground=ACCENT, font=("TkDefaultFont", 11, "bold"))
        style.configure("TNotebook.Tab", padding=(18, 8), font=("TkDefaultFont", 11))
        style.configure("Treeview", rowheight=24)

    def _build_menu(self) -> None:
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=0)
        file_menu.add_command(label="새로 만들기", accelerator="Ctrl+N", command=self.new_project)
        file_menu.add_command(label="열기…", accelerator="Ctrl+O", command=self.open_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="저장", accelerator="Ctrl+S", command=self.save)
        file_menu.add_command(label="다른 이름으로 저장…", command=self.save_as)
        file_menu.add_separator()
        file_menu.add_command(label="종료", command=self._on_close)
        menu.add_cascade(label="파일", menu=file_menu)

        edit_menu = tk.Menu(menu, tearoff=0)
        edit_menu.add_command(label="실행 취소", accelerator="Ctrl+Z", command=self.undo)
        edit_menu.add_command(label="다시 실행", accelerator="Ctrl+Y", command=self.redo)
        menu.add_cascade(label="편집", menu=edit_menu)

        advanced = tk.Menu(menu, tearoff=0)
        advanced.add_command(label="플로우 캔버스 (고급)", command=self._open_flow_editor)
        advanced.add_command(label="SCH 뷰어", command=self._open_viewer)
        advanced.add_command(label="일괄 편집기", command=self._open_bulk_editor)
        advanced.add_command(label="중단 실험 재개", command=self._open_resume)
        menu.add_cascade(label="고급 도구", menu=advanced)

        help_menu = tk.Menu(menu, tearoff=0)
        help_menu.add_command(label="단축키", command=self._show_shortcuts)
        menu.add_cascade(label="도움말", menu=help_menu)
        self.root.config(menu=menu)

    def _build_header(self) -> None:
        header = ttk.Frame(self.root, padding=(14, 10, 14, 4))
        header.pack(fill=tk.X)

        self.title_var = tk.StringVar(value="새 스케줄")
        ttk.Label(header, textvariable=self.title_var, style="Head.TLabel").pack(side=tk.LEFT)

        self.stage_var = tk.StringVar(value="초안")
        self.stage_label = ttk.Label(header, textvariable=self.stage_var, style="Good.TLabel")
        self.stage_label.pack(side=tk.RIGHT)

        toolbar = ttk.Frame(self.root, padding=(14, 0, 14, 6))
        toolbar.pack(fill=tk.X)
        for label, command in (
            ("새로 만들기", self.new_project),
            ("열기", self.open_dialog),
            ("저장", self.save),
            ("실행 취소", self.undo),
            ("다시 실행", self.redo),
        ):
            ttk.Button(toolbar, text=label, command=command).pack(side=tk.LEFT, padx=(0, 6))
        self.summary_var = tk.StringVar(value="")
        ttk.Label(toolbar, textvariable=self.summary_var, style="Sub.TLabel").pack(
            side=tk.LEFT, padx=12
        )

    def _build_tabs(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))
        self.setup_tab = ttk.Frame(self.notebook, padding=12)
        self.protocol_tab = ttk.Frame(self.notebook, padding=8)
        self.procedure_tab = ttk.Frame(self.notebook, padding=8)
        self.validate_tab = ttk.Frame(self.notebook, padding=8)
        self.export_tab = ttk.Frame(self.notebook, padding=12)
        for frame, label in (
            (self.setup_tab, "1. 설정"),
            (self.protocol_tab, "2. 프로토콜"),
            (self.procedure_tab, "3. 절차"),
            (self.validate_tab, "4. 검증"),
            (self.export_tab, "5. 내보내기"),
        ):
            self.notebook.add(frame, text=label)
        self._build_setup(self.setup_tab)
        self._build_protocol(self.protocol_tab)
        self._build_procedure(self.procedure_tab)
        self._build_validate(self.validate_tab)
        self._build_export(self.export_tab)
        self.notebook.bind("<<NotebookTabChanged>>", lambda _event: self.refresh_all())

    def _build_status(self) -> None:
        bar = ttk.Frame(self.root, padding=(14, 4))
        bar.pack(fill=tk.X)
        self.status_var = tk.StringVar(value="준비됨")
        ttk.Label(bar, textvariable=self.status_var, style="Sub.TLabel").pack(side=tk.LEFT)
        self.autosave_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.autosave_var, style="Sub.TLabel").pack(side=tk.RIGHT)

    def _bind_keys(self) -> None:
        self.root.bind_all("<Control-s>", lambda _e: self.save())
        self.root.bind_all("<Control-n>", lambda _e: self.new_project())
        self.root.bind_all("<Control-o>", lambda _e: self.open_dialog())
        self.root.bind_all("<Control-z>", lambda _e: self.undo())
        self.root.bind_all("<Control-y>", lambda _e: self.redo())
        self.root.bind_all("<Control-Shift-Z>", lambda _e: self.redo())
        self.root.bind_all("<F5>", lambda _e: self.refresh_all())
        for index in range(5):
            self.root.bind_all(
                f"<Control-Key-{index + 1}>",
                lambda _e, position=index: self.notebook.select(position),
            )

    # ------------------------------------------------------------- setup

    def _build_setup(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent,
            text="이 스케줄이 어떤 장비에서, 어떤 셀로 도는지 먼저 정합니다.",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(0, 10))
        self.setup_body = ttk.Frame(parent, style="Panel.TFrame", padding=14)
        self.setup_body.pack(fill=tk.BOTH, expand=True)
        self.setup_vars: dict[str, tk.StringVar] = {}

    def _render_setup(self) -> None:
        for child in self.setup_body.winfo_children():
            child.destroy()
        self.setup_vars.clear()
        for row, item in enumerate(self.model.setup_fields()):
            ttk.Label(self.setup_body, text=item.label, style="Field.TLabel").grid(
                row=row * 2, column=0, sticky="w", pady=(8, 0), padx=(0, 12)
            )
            variable = tk.StringVar(value=item.value)
            self.setup_vars[item.key] = variable
            if item.key == "equipment_unit":
                widget = ttk.Combobox(
                    self.setup_body,
                    textvariable=variable,
                    values=("",) + self.model.unit_choices(),
                    width=28,
                    state="readonly",
                )
                widget.bind(
                    "<<ComboboxSelected>>",
                    lambda _e: self._commit_setup("equipment_unit"),
                )
            elif item.key in {"ctspro_build", "sch_layout"}:
                widget = ttk.Entry(self.setup_body, textvariable=variable, width=30, state="readonly")
            else:
                widget = ttk.Entry(self.setup_body, textvariable=variable, width=30)
                widget.bind("<Return>", lambda _e, key=item.key: self._commit_setup(key))
                widget.bind("<FocusOut>", lambda _e, key=item.key: self._commit_setup(key))
            widget.grid(row=row * 2, column=1, sticky="w", pady=(8, 0))
            detail = item.detail + (f"   ⚠ {item.issue}" if item.issue else "")
            ttk.Label(
                self.setup_body,
                text=detail,
                style="BadPanel.TLabel" if item.issue else "Hint.TLabel",
            ).grid(row=row * 2 + 1, column=1, sticky="w")
        self.setup_body.columnconfigure(2, weight=1)

    def _commit_setup(self, key: str) -> None:
        variable = self.setup_vars.get(key)
        if variable is None:
            return
        text = variable.get()
        try:
            if key == "name":
                if text.strip() == self.model.project.name:
                    return
                self.model.set_project_name(text)
            elif key == "equipment_unit":
                current = self.model.project.equipment
                if (current.unit if current else "") == text.strip():
                    return
                self.model.set_equipment_unit(text)
            else:
                self.model.set_cell_value(key, text)
        except (units.UnitParseError, ValueError) as exc:
            messagebox.showerror("입력을 확인하세요", str(exc), parent=self.root)
            self._render_setup()
            return
        self._set_status(f"설정 변경: {key}")
        self.refresh_all()
        self._warn_on_current_breach(key)

    def _warn_on_current_breach(self, key: str) -> None:
        """Changing capacity or the unit rescales every current — say so loudly."""
        if key not in {"nominal_capacity_mAh", "equipment_unit", "max_current_mA"}:
            return
        breaches = self.model.current_limit_breaches()
        if not breaches:
            return
        messagebox.showwarning(
            "전류 한계를 넘습니다",
            f"이 설정에서는 {len(breaches)}개 스텝이 허용 전류를 넘습니다.\n\n"
            + "\n".join(f"· {row.location}: {row.message}" for row in breaches[:5])
            + ("\n· …" if len(breaches) > 5 else "")
            + "\n\n검증 탭에서 전체 목록을 볼 수 있습니다. 저장은 계속 가능합니다.",
            parent=self.root,
        )

    # ---------------------------------------------------------- protocol

    def _build_protocol(self, parent: ttk.Frame) -> None:
        panes = ttk.Panedwindow(parent, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(panes, padding=6)
        middle = ttk.Frame(panes, padding=6)
        right = ttk.Frame(panes, padding=6)
        panes.add(left, weight=2)
        panes.add(middle, weight=2)
        panes.add(right, weight=3)

        ttk.Label(left, text="무엇을 알고 싶으신가요?", style="Field.TLabel").pack(anchor="w")
        self.goal_query = tk.StringVar()
        search = ttk.Entry(left, textvariable=self.goal_query)
        search.pack(fill=tk.X, pady=(4, 6))
        search.bind("<KeyRelease>", lambda _e: self._render_goals())
        self.goal_list = tk.Listbox(left, height=16, activestyle="none", exportselection=False)
        self.goal_list.pack(fill=tk.BOTH, expand=True)
        self.goal_list.bind("<<ListboxSelect>>", lambda _e: self._render_goal_detail())
        self.goal_list.bind("<Double-Button-1>", lambda _e: self._add_selected_goal())
        self.goal_detail = tk.StringVar(value="")
        ttk.Label(left, textvariable=self.goal_detail, style="Sub.TLabel", wraplength=280).pack(
            anchor="w", pady=6
        )
        ttk.Button(left, text="이 실험 추가", command=self._add_selected_goal).pack(fill=tk.X)

        ttk.Label(middle, text="현재 스케줄 구성", style="Field.TLabel").pack(anchor="w")
        self.module_list = ttk.Treeview(
            middle, columns=("steps", "trust"), show="tree headings", height=16
        )
        self.module_list.heading("#0", text="구간")
        self.module_list.heading("steps", text="스텝")
        self.module_list.heading("trust", text="검증")
        self.module_list.column("#0", width=220)
        self.module_list.column("steps", width=70, anchor="center")
        self.module_list.column("trust", width=110)
        self.module_list.pack(fill=tk.BOTH, expand=True, pady=(4, 6))
        self.module_list.bind("<<TreeviewSelect>>", lambda _e: self._on_module_selected())
        buttons = ttk.Frame(middle)
        buttons.pack(fill=tk.X)
        for label, command in (
            ("복제", self._duplicate_module),
            ("삭제", self._remove_module),
        ):
            ttk.Button(buttons, text=label, command=command).pack(side=tk.LEFT, padx=(0, 6))

        self.form_title = tk.StringVar(value="구간을 선택하세요")
        ttk.Label(right, textvariable=self.form_title, style="Field.TLabel").pack(anchor="w")
        self.form_trust = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.form_trust, style="Sub.TLabel").pack(anchor="w")

        canvas_wrap = ttk.Frame(right)
        canvas_wrap.pack(fill=tk.BOTH, expand=True, pady=6)
        self.form_canvas = tk.Canvas(canvas_wrap, bg=PANEL, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_wrap, orient=tk.VERTICAL, command=self.form_canvas.yview)
        self.form_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.form_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.form_body = ttk.Frame(self.form_canvas, style="Panel.TFrame", padding=10)
        self.form_window = self.form_canvas.create_window((0, 0), window=self.form_body, anchor="nw")
        self.form_body.bind(
            "<Configure>",
            lambda _e: self.form_canvas.configure(scrollregion=self.form_canvas.bbox("all")),
        )
        self.form_canvas.bind(
            "<Configure>",
            lambda event: self.form_canvas.itemconfigure(self.form_window, width=event.width),
        )

        self.impact_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.impact_var, style="Sub.TLabel", wraplength=460).pack(
            anchor="w"
        )

    def _render_goals(self) -> None:
        self._goals: tuple[ExperimentGoal, ...] = self.model.goal_rows(self.goal_query.get())
        self.goal_list.delete(0, tk.END)
        for goal in self._goals:
            self.goal_list.insert(tk.END, f"{goal.title} — {goal.question}")
        if not self._goals:
            self.goal_detail.set("검색 결과가 없습니다.")

    def _render_goal_detail(self) -> None:
        goal = self._selected_goal()
        if goal is None:
            self.goal_detail.set("")
            return
        parts = [f"결과로 얻는 것: {goal.outcome}", f"검증 상태: {TRUST_LABELS_KO.get(goal.trust_status, goal.trust_status)}"]
        if goal.note:
            parts.append(goal.note)
        self.goal_detail.set("\n".join(parts))

    def _selected_goal(self) -> ExperimentGoal | None:
        selection = self.goal_list.curselection()
        if not selection or not getattr(self, "_goals", ()):
            return None
        return self._goals[selection[0]]

    def _add_selected_goal(self) -> None:
        goal = self._selected_goal()
        if goal is None:
            messagebox.showinfo("실험 선택", "왼쪽 목록에서 실험 목적을 먼저 고르세요.", parent=self.root)
            return
        module_id = self.model.add_goal(goal.goal_id)
        self.selected_module = module_id
        self._set_status(f"{goal.title} 추가됨 — 값은 오른쪽에서 바로 고칠 수 있습니다.")
        self.refresh_all()

    def _duplicate_module(self) -> None:
        if not self.selected_module:
            return
        self.selected_module = self.model.duplicate_module(self.selected_module)
        self.refresh_all()

    def _remove_module(self) -> None:
        if not self.selected_module:
            return
        if not messagebox.askyesno("삭제", f"{self.selected_module} 구간을 삭제할까요?", parent=self.root):
            return
        self.model.remove_module(self.selected_module)
        self.selected_module = None
        self.refresh_all()

    def _on_module_selected(self) -> None:
        selection = self.module_list.selection()
        self.selected_module = selection[0] if selection else None
        self._render_form()

    def _render_modules(self) -> None:
        selection = self.selected_module
        self.module_list.delete(*self.module_list.get_children())
        for position, row in enumerate(self.model.module_rows(), start=1):
            text = f"{position}. {row.title}"
            if row.subtitle:
                text += f" — {row.subtitle}"
            self.module_list.insert(
                "", tk.END, iid=row.module_id, text=text,
                values=(row.step_count or "!", row.trust),
            )
        if selection and self.module_list.exists(selection):
            self.module_list.selection_set(selection)
        elif self.module_list.get_children():
            first = self.module_list.get_children()[0]
            self.module_list.selection_set(first)
            self.selected_module = first
        else:
            self.selected_module = None

    def _render_form(self) -> None:
        for child in self.form_body.winfo_children():
            child.destroy()
        self._field_widgets.clear()
        if not self.selected_module:
            self.form_title.set("왼쪽에서 실험을 추가하거나 가운데에서 구간을 선택하세요")
            self.form_trust.set("")
            return
        form = self.model.form(self.selected_module)
        self.form_title.set(f"{form.title} · {self.selected_module}")
        trust = TRUST_LABELS_KO.get(form.trust_status, form.trust_status)
        self.form_trust.set(
            f"검증 상태: {trust}" + (f" · {form.limitations[0]}" if form.limitations else "")
        )

        sibling_count = len(self.model.modules_of_type(form.module_type))
        if form.derived:
            box = ttk.Labelframe(self.form_body, text="자동 계산", style="Group.TLabelframe", padding=8)
            box.pack(fill=tk.X, pady=(0, 10))
            for value in form.derived:
                style = {"error": "BadPanel.TLabel", "warning": "Warn.TLabel"}.get(
                    value.severity, "Panel.TLabel"
                )
                ttk.Label(box, text=f"{value.label}: {value.text}", style=style).pack(anchor="w")

        for section in form.sections:
            group = ttk.Labelframe(
                self.form_body, text=section.title, style="Group.TLabelframe", padding=8
            )
            group.pack(fill=tk.X, pady=(0, 10))
            for form_field in section.fields:
                self._render_field(group, form_field, sibling_count)

    def _render_field(
        self, parent: ttk.Widget, form_field: FormField, sibling_count: int = 1
    ) -> None:
        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill=tk.X, pady=4)
        header = ttk.Frame(row, style="Panel.TFrame")
        header.pack(fill=tk.X)
        label = form_field.spec.label
        if form_field.spec.risk == "critical":
            label += " ⚠"
        ttk.Label(header, text=label, style="Field.TLabel", width=22).pack(side=tk.LEFT)

        spec = form_field.spec
        variable: tk.Variable
        if spec.kind == "bool":
            variable = tk.BooleanVar(value=bool(form_field.value))
            widget = ttk.Checkbutton(
                header, variable=variable,
                command=lambda key=spec.key: self._commit_field(key),
            )
        elif spec.kind == "choice":
            variable = tk.StringVar(value=form_field.view.text)
            widget = ttk.Combobox(
                header, textvariable=variable, state="readonly", width=26,
                values=[choice.label for choice in spec.choices],
            )
            widget.bind("<<ComboboxSelected>>", lambda _e, key=spec.key: self._commit_field(key))
        else:
            variable = tk.StringVar(value=form_field.view.text)
            widget = ttk.Entry(header, textvariable=variable, width=28)
            widget.bind("<Return>", lambda _e, key=spec.key: self._commit_field(key))
            widget.bind("<FocusOut>", lambda _e, key=spec.key: self._commit_field(key))
        widget.pack(side=tk.LEFT)
        if spec.unit_label and spec.kind not in {"choice", "bool"}:
            ttk.Label(header, text=spec.unit_label, style="Hint.TLabel").pack(side=tk.LEFT, padx=6)

        if sibling_count > 1:
            ttk.Button(
                header,
                text=f"같은 실험 {sibling_count}개에 모두 적용",
                command=lambda key=spec.key: self._apply_to_all(key),
            ).pack(side=tk.LEFT, padx=6)

        detail = ttk.Label(
            row,
            text="\n".join(form_field.detail_lines()),
            style="BadPanel.TLabel" if form_field.has_error else "Hint.TLabel",
            wraplength=430,
            justify="left",
        )
        detail.pack(anchor="w", padx=(6, 0))
        self._field_widgets[spec.key] = (form_field, variable, widget, detail)

    def _commit_field(self, key: str) -> None:
        if not self.selected_module:
            return
        entry = self._field_widgets.get(key)
        if entry is None:
            return
        form_field, variable, _widget, detail = entry
        raw = variable.get()
        if isinstance(raw, bool):
            raw = "예" if raw else "아니오"
        if str(raw) == form_field.view.text:
            return
        try:
            diff: StepDiff = self.model.set_param(self.selected_module, key, raw)
        except (units.UnitParseError, ValueError) as exc:
            detail.configure(text=f"오류: {exc}", style="BadPanel.TLabel")
            return
        self.impact_var.set(f"{form_field.spec.label} 변경 → {diff.headline()}")
        self._set_status(f"{form_field.spec.label} 변경됨 · {diff.headline()}")
        self.refresh_all()

    def _apply_to_all(self, key: str) -> None:
        if not self.selected_module:
            return
        entry = self._field_widgets.get(key)
        if entry is None:
            return
        form_field, variable, _widget, detail = entry
        raw = variable.get()
        if isinstance(raw, bool):
            raw = "예" if raw else "아니오"
        module_type = self.model.form(self.selected_module).module_type
        targets = self.model.modules_of_type(module_type)
        if not messagebox.askyesno(
            "모두 적용",
            f"{form_field.spec.label} 값을 같은 종류의 구간 {len(targets)}개에 모두 적용할까요?",
            parent=self.root,
        ):
            return
        try:
            count, diff = self.model.apply_to_all_of_type(module_type, key, raw)
        except (units.UnitParseError, ValueError) as exc:
            detail.configure(text=f"오류: {exc}", style="BadPanel.TLabel")
            return
        self._set_status(f"{count}개 구간에 적용됨 · {diff.headline()}")
        self.refresh_all()

    # --------------------------------------------------------- procedure

    def _build_procedure(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent,
            text="실제 실행 순서입니다. 위/아래로 옮기거나 끌어서 순서를 바꿀 수 있습니다.",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(0, 6))

        top = ttk.Frame(parent)
        top.pack(fill=tk.BOTH, expand=True)
        self.phase_tree = ttk.Treeview(
            top,
            columns=("range", "steps", "duration", "trust"),
            show="tree headings",
            height=10,
        )
        self.phase_tree.heading("#0", text="구간")
        for column, title, width in (
            ("range", "스텝 범위", 110),
            ("steps", "스텝 수", 80),
            ("duration", "예상 소요", 120),
            ("trust", "검증 상태", 140),
        ):
            self.phase_tree.heading(column, text=title)
            self.phase_tree.column(column, width=width, anchor="center")
        self.phase_tree.column("#0", width=380)
        self.phase_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.phase_tree.bind("<ButtonPress-1>", self._drag_start)
        self.phase_tree.bind("<ButtonRelease-1>", self._drag_drop)

        side = ttk.Frame(top, padding=(8, 0))
        side.pack(side=tk.LEFT, fill=tk.Y)
        for label, command in (
            ("▲ 위로", lambda: self._move_phase(-1)),
            ("▼ 아래로", lambda: self._move_phase(1)),
            ("개별 스텝으로 분리", self._detach_phase),
        ):
            ttk.Button(side, text=label, command=command).pack(fill=tk.X, pady=3)
        ttk.Label(
            side,
            text="분리하면 프리셋 보장이 사라지고\n직접 편집한 스텝이 됩니다.",
            style="Sub.TLabel",
            justify="left",
        ).pack(pady=(6, 0))

        ttk.Label(parent, text="장비 상세 보기 (읽기 전용)", style="Field.TLabel").pack(
            anchor="w", pady=(10, 4)
        )
        self.step_tree = ttk.Treeview(
            parent,
            columns=("phase", "type", "mode", "current", "voltage", "end", "loop"),
            show="headings",
            height=12,
        )
        for column, title, width in (
            ("phase", "구간", 150),
            ("type", "종류", 90),
            ("mode", "모드", 70),
            ("current", "전류", 130),
            ("voltage", "전압", 130),
            ("end", "종료 조건", 190),
            ("loop", "LOOP", 110),
        ):
            self.step_tree.heading(column, text=title)
            self.step_tree.column(column, width=width, anchor="w")
        self.step_tree.pack(fill=tk.BOTH, expand=True)

    def _selected_phase(self) -> str | None:
        selection = self.phase_tree.selection()
        return selection[0] if selection else None

    def _move_phase(self, delta: int) -> None:
        module_id = self._selected_phase()
        if not module_id:
            return
        if self.model.move(module_id, delta):
            self.selected_module = module_id
            self.refresh_all()
            if self.phase_tree.exists(module_id):
                self.phase_tree.selection_set(module_id)

    def _detach_phase(self) -> None:
        module_id = self._selected_phase() or self.selected_module
        if not module_id:
            return
        confirmed = messagebox.askyesno(
            "개별 스텝으로 분리",
            "이 구간을 지금 값 그대로 펼쳐서 개별 스텝으로 바꿉니다.\n"
            "이후에는 프리셋 검증 상태가 아니라 '직접 편집' 상태가 됩니다. 계속할까요?",
            parent=self.root,
        )
        if not confirmed:
            return
        try:
            self.model.detach(module_id)
        except ValueError as exc:
            messagebox.showerror("분리할 수 없습니다", str(exc), parent=self.root)
            return
        self._set_status(f"{module_id} 을(를) 개별 스텝으로 분리했습니다.")
        self.refresh_all()

    def _drag_start(self, event: tk.Event) -> None:
        self._drag_from = self.phase_tree.identify_row(event.y) or None

    def _drag_drop(self, event: tk.Event) -> None:
        source = self._drag_from
        self._drag_from = None
        target = self.phase_tree.identify_row(event.y)
        if not source or not target or source == target:
            return
        order = [row for row in self.phase_tree.get_children()]
        order.remove(source)
        order.insert(order.index(target), source)
        try:
            self.model.reorder(order)
        except ValueError as exc:
            messagebox.showerror("순서를 바꿀 수 없습니다", str(exc), parent=self.root)
            return
        self._set_status("구간 순서를 바꿨습니다.")
        self.refresh_all()

    def _render_procedure(self) -> None:
        selection = self._selected_phase()
        self.phase_tree.delete(*self.phase_tree.get_children())
        for position, row in enumerate(self.model.module_rows(), start=1):
            text = f"{position}. {row.title}"
            if row.subtitle:
                text += f" — {row.subtitle}"
            if row.error:
                text += f"  ⚠ {row.error}"
            self.phase_tree.insert(
                "", tk.END, iid=row.module_id, text=text,
                values=(row.step_range, row.step_count, row.duration, row.trust),
            )
        if selection and self.phase_tree.exists(selection):
            self.phase_tree.selection_set(selection)

        self.step_tree.delete(*self.step_tree.get_children())
        for row in self.model.step_rows():
            current = ""
            if row["c_rate"] is not None:
                current = units.format_c_rate(row["c_rate"])
                capacity = self.model.project.cell_profile.nominal_capacity_mAh
                current += f" ({units.format_current_mA(row['c_rate'] * capacity)})"
            voltage = ""
            if row["voltage_v"] is not None:
                voltage = f"한계 {units.format_voltage(row['voltage_v'])}"
            if row["end_voltage_v"] is not None:
                voltage += f" · 종료 {units.format_voltage(row['end_voltage_v'])}"
            end_parts = []
            if row["end_time_s"] is not None:
                end_parts.append(units.format_duration_ko(row["end_time_s"]))
            if row["dod_percent"] is not None:
                end_parts.append(f"DOD {row['dod_percent']:g}%")
            loop = ""
            if row["loop_goto_step"] is not None:
                loop = f"→ {row['loop_goto_step']} × {row['loop_count']}"
            self.step_tree.insert(
                "", tk.END,
                values=(
                    row["phase"], row["step_type"], row["mode"], current, voltage,
                    " · ".join(end_parts), loop,
                ),
                text=str(row["number"]),
            )

    # ---------------------------------------------------------- validate

    def _build_validate(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent,
            text="오류를 두 번 누르면 해당 입력 칸으로 이동합니다. 오류가 있어도 저장은 언제나 됩니다.",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(0, 6))
        self.issue_tree = ttk.Treeview(
            parent, columns=("severity", "location", "message"), show="headings", height=16
        )
        for column, title, width in (
            ("severity", "구분", 80),
            ("location", "위치", 260),
            ("message", "내용", 720),
        ):
            self.issue_tree.heading(column, text=title)
            self.issue_tree.column(column, width=width, anchor="w")
        self.issue_tree.pack(fill=tk.BOTH, expand=True)
        self.issue_tree.tag_configure("error", foreground=DANGER)
        self.issue_tree.tag_configure("warning", foreground=WARN)
        self.issue_tree.bind("<Double-Button-1>", lambda _e: self._goto_issue())
        self.issue_detail = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.issue_detail, style="Sub.TLabel", wraplength=1200).pack(
            anchor="w", pady=6
        )
        self.issue_tree.bind("<<TreeviewSelect>>", lambda _e: self._show_issue_detail())

        ttk.Label(parent, text="미검증 근거", style="Field.TLabel").pack(anchor="w", pady=(8, 2))
        self.unverified = tk.Text(parent, height=6, wrap="word", bg=PANEL, relief="flat")
        self.unverified.pack(fill=tk.X)

    def _render_validation(self) -> None:
        self._issue_rows: tuple[ValidationRow, ...] = self.model.validation_rows()
        self.issue_tree.delete(*self.issue_tree.get_children())
        for index, row in enumerate(self._issue_rows):
            self.issue_tree.insert(
                "", tk.END, iid=str(index),
                values=(row.severity_label, row.location, row.message),
                tags=(row.severity,),
            )
        errors = sum(1 for row in self._issue_rows if row.severity == "error")
        warnings = len(self._issue_rows) - errors
        self.issue_detail.set(
            f"오류 {errors}건 · 경고 {warnings}건"
            + ("  — 오류가 없으면 검토용 파일을 만들 수 있습니다." if not errors else "")
        )
        self.unverified.configure(state="normal")
        self.unverified.delete("1.0", tk.END)
        self.unverified.insert(tk.END, "\n".join(self.model.unverified_notes()) or "구성된 실험이 없습니다.")
        self.unverified.configure(state="disabled")

    def _current_issue(self) -> ValidationRow | None:
        selection = self.issue_tree.selection()
        if not selection or not getattr(self, "_issue_rows", ()):
            return None
        return self._issue_rows[int(selection[0])]

    def _show_issue_detail(self) -> None:
        row = self._current_issue()
        if row is None:
            return
        parts = [f"[{row.code}] {row.message}"]
        if row.remediation:
            parts.append(f"해결: {row.remediation}")
        if row.module_id:
            parts.append(f"구간: {row.module_id}")
        if row.field_key:
            parts.append(f"입력 항목: {row.field_key}")
        self.issue_detail.set(" · ".join(parts))

    def _goto_issue(self) -> None:
        row = self._current_issue()
        if row is None or not row.module_id:
            return
        self.selected_module = row.module_id
        self.notebook.select(1)
        self.refresh_all()
        if row.field_key:
            entry = self._field_widgets.get(row.field_key)
            if entry:
                _field, _variable, widget, _detail = entry
                widget.focus_set()
                self._set_status(f"{row.module_id} · {row.field_key} 로 이동했습니다.")

    # ------------------------------------------------------------ export

    def _build_export(self, parent: ttk.Frame) -> None:
        self.ladder_var = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.ladder_var, style="Head.TLabel").pack(anchor="w")
        ttk.Label(
            parent,
            text="초안 저장은 언제나 가능합니다. 아래로 갈수록 더 많은 확인이 필요합니다.",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(0, 10))

        self.output_body = ttk.Frame(parent, style="Panel.TFrame", padding=12)
        self.output_body.pack(fill=tk.BOTH, expand=True)

        approvals = ttk.Labelframe(parent, text="확인 기록", style="Group.TLabelframe", padding=10)
        approvals.pack(fill=tk.X, pady=10)
        self.reviewer_var = tk.StringVar()
        ttk.Label(approvals, text="검토자", style="Panel.TLabel").grid(row=0, column=0, padx=(0, 8))
        ttk.Entry(approvals, textvariable=self.reviewer_var, width=18).grid(row=0, column=1)
        ttk.Button(approvals, text="CTSPro 확인 완료로 기록", command=self._record_review).grid(
            row=0, column=2, padx=8
        )
        ttk.Button(approvals, text="장비 실행 승인 기록", command=self._record_approval).grid(
            row=0, column=3
        )
        ttk.Button(approvals, text="승인 해제", command=self._clear_approvals).grid(row=0, column=4, padx=8)

        ttk.Label(parent, text="한국어 요약", style="Field.TLabel").pack(anchor="w", pady=(6, 2))
        self.summary_text = tk.Text(parent, height=10, wrap="word", bg=PANEL, relief="flat")
        self.summary_text.pack(fill=tk.BOTH, expand=True)
        ttk.Button(parent, text="요약 복사", command=self._copy_summary).pack(anchor="e", pady=4)

    def _render_export(self) -> None:
        state = self.model.release()
        self.ladder_var.set(
            "  →  ".join(
                f"{'✔ ' if reached else ''}{label}" for _stage, label, reached in state.ladder()
            )
        )
        for child in self.output_body.winfo_children():
            child.destroy()
        commands = {
            "draft_save": self.save,
            "preview": self._export_preview,
            "review_candidate": self._export_review_candidate,
            "template_patch": self._show_template_patch_help,
            "equipment_export": self._equipment_export,
        }
        for option in state.options:
            frame = ttk.Frame(self.output_body, style="Panel.TFrame", padding=(0, 6))
            frame.pack(fill=tk.X)
            head = ttk.Frame(frame, style="Panel.TFrame")
            head.pack(fill=tk.X)
            ttk.Label(
                head,
                text=f"{'🔓' if option.allowed else '🔒'} {option.title}",
                style="Field.TLabel",
            ).pack(side=tk.LEFT)
            button = ttk.Button(
                head, text="실행", command=commands.get(option.kind, lambda: None)
            )
            button.pack(side=tk.RIGHT)
            if not option.allowed:
                button.state(["disabled"])
            ttk.Label(frame, text=option.description, style="Hint.TLabel", wraplength=1000).pack(
                anchor="w"
            )
            for blocker in option.blockers[:4]:
                ttk.Label(frame, text=f"· {blocker}", style="BadPanel.TLabel", wraplength=1000).pack(
                    anchor="w", padx=(12, 0)
                )
            if len(option.blockers) > 4:
                ttk.Label(
                    frame, text=f"· 외 {len(option.blockers) - 4}건", style="BadPanel.TLabel"
                ).pack(anchor="w", padx=(12, 0))

        self.summary_text.configure(state="normal")
        self.summary_text.delete("1.0", tk.END)
        self.summary_text.insert(tk.END, self.model.summary().as_text())
        self.summary_text.configure(state="disabled")

    def _export_preview(self) -> None:
        from ..exporting import ExportBlocked, export_preview

        directory = filedialog.askdirectory(title="미리보기를 저장할 폴더")
        if not directory:
            return
        try:
            result = export_preview(self.model.project, Path(directory))
        except ExportBlocked as exc:
            messagebox.showerror("아직 내보낼 수 없습니다", str(exc), parent=self.root)
            return
        messagebox.showinfo(
            "미리보기 저장 완료",
            "\n".join([result.note, *[str(path) for path in result.paths]]),
            parent=self.root,
        )

    def _export_review_candidate(self) -> None:
        from ..exporting import ExportBlocked, export_review_candidate

        directory = filedialog.askdirectory(title="검토용 후보를 저장할 폴더")
        if not directory:
            return
        try:
            result = export_review_candidate(self.model.project, Path(directory))
        except (ExportBlocked, ValueError) as exc:
            messagebox.showerror("아직 내보낼 수 없습니다", str(exc), parent=self.root)
            return
        messagebox.showwarning(
            "검토 전용 파일 생성됨",
            "\n".join(
                [
                    result.note,
                    "",
                    "이 파일은 CTSEditorPro 에서 열어 확인하는 용도입니다.",
                    "절대 장비에서 실행하지 마세요.",
                    "",
                    *[str(path) for path in result.paths],
                ]
            ),
            parent=self.root,
        )
        self.refresh_all()

    def _show_template_patch_help(self) -> None:
        messagebox.showinfo(
            "템플릿 패치",
            "CTSPro 가 만든 원본 .sch 와 그 SHA-256 이 필요합니다.\n\n"
            "python -m pne_scheduler patch-sch 원본.sch 계획.json -o 결과.sch --allow-analysis-output\n\n"
            "검증된 필드만 바뀌고 나머지 바이트는 그대로 보존됩니다.",
            parent=self.root,
        )

    def _equipment_export(self) -> None:
        messagebox.showwarning(
            "장비 실행용 내보내기",
            "장비 실행용 경로는 아직 열려 있지 않습니다.\n"
            "CTSPro 확인과 장비 승인이 기록된 뒤에도, 실제 장비 스모크 테스트가 끝나야 사용할 수 있습니다.",
            parent=self.root,
        )

    def _record_review(self) -> None:
        reviewer = self.reviewer_var.get().strip()
        if not reviewer:
            messagebox.showinfo("검토자 필요", "검토자 이름을 입력하세요.", parent=self.root)
            return
        self.model.record_ctspro_review(
            reviewer=reviewer, reviewed_at=datetime.now().isoformat(timespec="seconds")
        )
        self._set_status("CTSPro 확인을 기록했습니다.")
        self.refresh_all()

    def _record_approval(self) -> None:
        approver = self.reviewer_var.get().strip()
        if not approver:
            messagebox.showinfo("승인자 필요", "승인자 이름을 입력하세요.", parent=self.root)
            return
        if not messagebox.askyesno(
            "장비 실행 승인",
            "이 스케줄을 장비에서 실행해도 된다고 기록합니다.\n"
            "CTSPro 에서 값이 모두 확인되었을 때만 진행하세요. 계속할까요?",
            parent=self.root,
        ):
            return
        self.model.record_equipment_approval(
            approver=approver, approved_at=datetime.now().isoformat(timespec="seconds")
        )
        self.refresh_all()

    def _clear_approvals(self) -> None:
        self.model.clear_approvals()
        self.refresh_all()

    def _copy_summary(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(self.model.summary().as_text())
        self._set_status("요약을 클립보드에 복사했습니다.")

    # ------------------------------------------------------------- files

    def new_project(self) -> None:
        if not self._confirm_discard():
            return
        self.model.new_document()
        self.selected_module = None
        self._set_status("새 프로젝트를 만들었습니다.")
        self.refresh_all()

    def open_dialog(self) -> None:
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(filetypes=FILE_TYPES)
        if path:
            self.open_path(Path(path))

    def open_path(self, path: Path) -> None:
        from ..ir.loader import ProjectLoadError

        try:
            repairs = self.model.open_path(path)
        except ProjectLoadError as exc:
            messagebox.showerror("열 수 없습니다", str(exc), parent=self.root)
            return
        self.selected_module = None
        if repairs:
            messagebox.showwarning(
                "일부 값을 고쳐서 열었습니다",
                "\n".join(f"· {item}" for item in repairs)
                + "\n\n확인 후 저장하면 고쳐진 값이 파일에 반영됩니다.",
                parent=self.root,
            )
        self._set_status(f"{path.name} 을(를) 열었습니다.")
        self.refresh_all()

    def save(self) -> None:
        if self.model.document.path is None:
            self.save_as()
            return
        path = self.model.document.save()
        self._set_status(f"저장됨: {path}")
        self.refresh_all()

    def save_as(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".schproj",
            filetypes=FILE_TYPES,
            initialfile=f"{self.model.project.name}.schproj",
        )
        if not path:
            return
        saved = self.model.document.save(Path(path))
        self._set_status(f"저장됨: {saved}")
        self.refresh_all()

    def undo(self) -> None:
        label = self.model.document.undo()
        self._set_status(f"실행 취소: {label}" if label else "되돌릴 작업이 없습니다.")
        self.refresh_all()

    def redo(self) -> None:
        label = self.model.document.redo()
        self._set_status(f"다시 실행: {label}" if label else "다시 실행할 작업이 없습니다.")
        self.refresh_all()

    def _confirm_discard(self) -> bool:
        if not self.model.document.dirty:
            return True
        answer = messagebox.askyesnocancel(
            "저장하지 않은 변경",
            "저장하지 않은 변경이 있습니다. 저장할까요?",
            parent=self.root,
        )
        if answer is None:
            return False
        if answer:
            self.save()
        return True

    def _offer_recovery(self) -> None:
        snapshots = ProjectDocument.recoveries(self.model.document.autosave_dir)
        if not snapshots:
            return
        latest = snapshots[0]
        if messagebox.askyesno(
            "복구할 작업이 있습니다",
            f"{latest.describe()}\n\n마지막 자동 저장을 복구할까요?",
            parent=self.root,
        ):
            self.model.document = ProjectDocument.recover(
                latest, autosave_dir=self.model.document.autosave_dir
            )
            self._set_status("자동 저장본을 복구했습니다. 확인 후 저장하세요.")
        else:
            for snapshot in snapshots:
                ProjectDocument.discard_recovery(snapshot)

    def _autosave_tick(self) -> None:
        try:
            path = self.model.document.autosave()
        except OSError:
            path = None
        if path:
            self.autosave_var.set(f"자동 저장됨 {datetime.now():%H:%M:%S}")
        self.root.after(AUTOSAVE_INTERVAL_MS, self._autosave_tick)

    def _on_close(self) -> None:
        if not self._confirm_discard():
            return
        self.model.document.clear_autosave()
        self.root.destroy()

    # ----------------------------------------------------------- advanced

    def _open_flow_editor(self) -> None:
        from .flow_editor import FlowEditorApp
        from .flow_model import FlowProjectModel

        window = tk.Toplevel(self.root)
        app = FlowEditorApp(window)
        app.model = FlowProjectModel(self.model.project)
        app._refresh_all()

    def _open_viewer(self) -> None:
        from .schedule_viewer import launch_schedule_viewer

        launch_schedule_viewer()

    def _open_bulk_editor(self) -> None:
        from .project_editor import launch_project_editor

        launch_project_editor(self.model.document.path)

    def _open_resume(self) -> None:
        from .resume_wizard import launch_resume_wizard

        launch_resume_wizard()

    def _show_shortcuts(self) -> None:
        messagebox.showinfo(
            "단축키",
            "Ctrl+N 새로 만들기\nCtrl+O 열기\nCtrl+S 저장\n"
            "Ctrl+Z 실행 취소 / Ctrl+Y 다시 실행\n"
            "Ctrl+1~5 탭 이동\nF5 새로 고침",
            parent=self.root,
        )

    # ------------------------------------------------------------ render

    def refresh_all(self) -> None:
        document = self.model.document
        self.title_var.set(document.title)
        summary = self.model.summary()
        self.summary_var.set(summary.headline)
        state = self.model.release()
        self.stage_var.set(f"진행 상태: {state.stage_label}")
        self._render_setup()
        self._render_goals()
        self._render_modules()
        self._render_form()
        self._render_procedure()
        self._render_validation()
        self._render_export()

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)


def launch_workspace(initial_path: Path | None = None) -> None:
    root = tk.Tk()
    WorkspaceApp(root, initial_path)
    root.mainloop()


__all__ = ["WorkspaceApp", "launch_workspace"]
