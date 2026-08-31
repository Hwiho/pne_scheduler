"""Tkinter module-flow editor for .schproj projects."""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from ..ir.cell_profile import CellProfile
from ..ir.project import ScheduleProject
from ..modules.composable import has_editable_recipe
from ..modules.presets import PRESETS_BY_KEY
from ..modules.recipe import RecipeUnit, charge, discharge, rest as rest_unit
from .flow_model import FlowProjectModel

_RECIPE_SECTIONS = ("setup", "repeat", "after")
_CARD_WIDTH = 300
_CARD_GAP_X = 330
_CARD_GAP_Y = 36


class FlowEditorApp:
    def __init__(self, root: tk.Tk, initial_path: Path | None = None) -> None:
        self.root = root
        self.root.title("PNE Scheduler — Module Flow Editor")
        self.root.geometry("1440x900")
        self.project_path: Path | None = None
        self.model = FlowProjectModel(self._new_project())
        self.selected_id: str | None = None
        self._canvas_items: dict[int, str] = {}

        self._build_ui()
        if initial_path is not None and initial_path.exists():
            self.load_project(initial_path)
        else:
            self._refresh_all()

    @staticmethod
    def _new_project() -> ScheduleProject:
        return ScheduleProject(
            name="Untitled schedule",
            cell_profile=CellProfile(
                nominal_capacity_mAh=80.0,
                v_max=4.2,
                v_min=2.5,
                max_current_mA=800.0,
            ),
        )

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self.root, padding=6)
        toolbar.pack(fill=tk.X)
        for label, command in (
            ("New", self._new),
            ("Open…", self._open),
            ("Save", self._save),
            ("Save As…", self._save_as),
            ("Validate", self._validate),
            ("Preview Steps", self._preview),
        ):
            ttk.Button(toolbar, text=label, command=command).pack(
                side=tk.LEFT,
                padx=(0, 5),
            )
        ttk.Label(
            toolbar,
            text="SCH export remains analysis-only; use a validated template patch plan.",
            foreground="#9a5b00",
        ).pack(side=tk.RIGHT)

        body = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        controls = ttk.Frame(body, padding=6)
        center = ttk.Frame(body, padding=6)
        properties = ttk.Frame(body, padding=6)
        body.add(controls, weight=1)
        body.add(center, weight=4)
        body.add(properties, weight=2)

        self._build_controls(controls)
        self._build_canvas(center)
        self._build_properties(properties)

        output = ttk.Notebook(self.root)
        output.pack(fill=tk.BOTH, expand=False, padx=8, pady=(0, 6))
        preview_frame = ttk.Frame(output)
        validation_frame = ttk.Frame(output)
        output.add(preview_frame, text="Step preview")
        output.add(validation_frame, text="Validation")

        columns = ("no", "type", "mode", "label", "c_rate", "voltage", "end")
        self.preview_tree = ttk.Treeview(
            preview_frame,
            columns=columns,
            show="headings",
            height=8,
        )
        widths = (45, 85, 65, 260, 75, 75, 120)
        for column, width in zip(columns, widths):
            self.preview_tree.heading(column, text=column.replace("_", " ").title())
            self.preview_tree.column(column, width=width, anchor=tk.W)
        preview_scroll = ttk.Scrollbar(
            preview_frame,
            orient=tk.VERTICAL,
            command=self.preview_tree.yview,
        )
        self.preview_tree.configure(yscrollcommand=preview_scroll.set)
        self.preview_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.validation_text = tk.Text(
            validation_frame,
            height=8,
            wrap=tk.WORD,
            state=tk.DISABLED,
        )
        self.validation_text.pack(fill=tk.BOTH, expand=True)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status_var, padding=5).pack(fill=tk.X)

    def _build_controls(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Module palette").pack(anchor=tk.W)
        self.module_type_var = tk.StringVar()
        self.module_type_combo = ttk.Combobox(
            parent,
            textvariable=self.module_type_var,
            values=self.model.module_types,
            state="readonly",
            width=24,
        )
        self.module_type_combo.pack(fill=tk.X, pady=(4, 6))
        if self.model.module_types:
            self.module_type_var.set(self.model.module_types[0])
        ttk.Button(parent, text="Add module", command=self._add_module).pack(fill=tk.X)
        ttk.Button(parent, text="Remove selected", command=self._remove_selected).pack(
            fill=tk.X,
            pady=(4, 12),
        )

        ttk.Separator(parent).pack(fill=tk.X, pady=4)
        ttk.Label(parent, text="Connections").pack(anchor=tk.W, pady=(4, 0))
        self.source_var = tk.StringVar()
        self.target_var = tk.StringVar()
        ttk.Label(parent, text="From").pack(anchor=tk.W, pady=(4, 0))
        self.source_combo = ttk.Combobox(
            parent,
            textvariable=self.source_var,
            state="readonly",
            width=24,
        )
        self.source_combo.pack(fill=tk.X)
        ttk.Label(parent, text="To").pack(anchor=tk.W, pady=(4, 0))
        self.target_combo = ttk.Combobox(
            parent,
            textvariable=self.target_var,
            state="readonly",
            width=24,
        )
        self.target_combo.pack(fill=tk.X)
        ttk.Button(parent, text="Connect", command=self._connect).pack(
            fill=tk.X,
            pady=(6, 0),
        )
        ttk.Button(parent, text="Disconnect", command=self._disconnect).pack(
            fill=tk.X,
            pady=(4, 0),
        )
        ttk.Button(parent, text="Auto-connect list order", command=self._auto_connect).pack(
            fill=tk.X,
            pady=(4, 12),
        )

        ttk.Label(parent, text="Current connections").pack(anchor=tk.W)
        self.edge_list = tk.Listbox(parent, height=9)
        self.edge_list.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.edge_list.bind("<<ListboxSelect>>", self._select_edge)

    def _build_canvas(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Flow canvas").pack(anchor=tk.W)
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.canvas = tk.Canvas(
            frame,
            background="#f5f7fa",
            highlightthickness=1,
            highlightbackground="#b7c0ca",
            scrollregion=(0, 0, 2000, 1400),
        )
        x_scroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        y_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(
            xscrollcommand=x_scroll.set,
            yscrollcommand=y_scroll.set,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.canvas.bind("<Button-1>", self._canvas_click)

    def _build_properties(self, parent: ttk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)
        module_tab = ttk.Frame(notebook, padding=6)
        cell_tab = ttk.Frame(notebook, padding=6)
        notebook.add(module_tab, text="Module")
        notebook.add(cell_tab, text="Cell profile")

        self.selected_label = ttk.Label(module_tab, text="No module selected")
        self.selected_label.pack(anchor=tk.W)

        self.preset_frame = ttk.LabelFrame(module_tab, text="Preset", padding=6)
        self.preset_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(
            self.preset_frame,
            textvariable=self.preset_var,
            state="readonly",
            width=36,
        )
        self.preset_combo.pack(fill=tk.X)
        ttk.Button(
            self.preset_frame,
            text="Rebuild from preset / knobs",
            command=self._rebuild_preset,
        ).pack(fill=tk.X, pady=(6, 0))
        self.preset_detail_var = tk.StringVar()
        ttk.Label(
            self.preset_frame,
            textvariable=self.preset_detail_var,
            wraplength=320,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(6, 0))

        self.recipe_frame = ttk.LabelFrame(
            module_tab,
            text="Inside this module",
            padding=6,
        )
        self.recipe_notebook = ttk.Notebook(self.recipe_frame)
        self.recipe_notebook.pack(fill=tk.BOTH, expand=True)
        self._recipe_trees: dict[str, ttk.Treeview] = {}
        titles = {"setup": "Setup once", "repeat": "Repeat", "after": "After"}
        for section in _RECIPE_SECTIONS:
            frame = ttk.Frame(self.recipe_notebook)
            tree = ttk.Treeview(
                frame,
                columns=("summary",),
                show="headings",
                height=8,
                selectmode="browse",
            )
            tree.heading("summary", text="Charge / discharge / rest")
            tree.column("summary", width=280, stretch=True)
            scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scroll.set)
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scroll.pack(side=tk.RIGHT, fill=tk.Y)
            tree.bind("<Double-1>", lambda _event: self._edit_selected_unit())
            self._recipe_trees[section] = tree
            self.recipe_notebook.add(frame, text=titles[section])

        count_row = ttk.Frame(self.recipe_frame)
        count_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(count_row, text="Repeat ×").pack(side=tk.LEFT)
        self.repeat_count_var = tk.StringVar(value="1")
        ttk.Entry(count_row, textvariable=self.repeat_count_var, width=6).pack(
            side=tk.LEFT,
            padx=4,
        )
        ttk.Button(
            count_row,
            text="Apply count",
            command=self._apply_repeat_count,
        ).pack(side=tk.LEFT)

        add_row = ttk.Frame(self.recipe_frame)
        add_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(add_row, text="+ Charge", command=lambda: self._add_unit("charge")).pack(
            side=tk.LEFT,
            padx=(0, 4),
        )
        ttk.Button(
            add_row,
            text="+ Discharge",
            command=lambda: self._add_unit("discharge"),
        ).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(add_row, text="+ Rest", command=lambda: self._add_unit("rest")).pack(
            side=tk.LEFT
        )

        edit_row = ttk.Frame(self.recipe_frame)
        edit_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(edit_row, text="Edit", command=self._edit_selected_unit).pack(
            side=tk.LEFT,
            padx=(0, 4),
        )
        ttk.Button(edit_row, text="Up", command=lambda: self._move_unit(-1)).pack(
            side=tk.LEFT,
            padx=(0, 4),
        )
        ttk.Button(edit_row, text="Down", command=lambda: self._move_unit(1)).pack(
            side=tk.LEFT,
            padx=(0, 4),
        )
        ttk.Button(edit_row, text="Delete", command=self._delete_unit).pack(side=tk.LEFT)

        self.json_frame = ttk.LabelFrame(module_tab, text="Advanced JSON", padding=6)
        self.json_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.params_text = tk.Text(
            self.json_frame,
            width=35,
            height=10,
            font=("TkFixedFont", 10),
        )
        self.params_text.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        ttk.Button(
            self.json_frame,
            text="Apply JSON",
            command=self._apply_params,
        ).pack(fill=tk.X)

        ttk.Label(cell_tab, text="Cell profile (JSON)").pack(anchor=tk.W)
        self.cell_text = tk.Text(cell_tab, width=35, height=24, font=("TkFixedFont", 10))
        self.cell_text.pack(fill=tk.BOTH, expand=True, pady=(4, 6))
        ttk.Button(cell_tab, text="Apply cell profile", command=self._apply_cell).pack(
            fill=tk.X
        )

    def _new(self) -> None:
        if self.model.project.modules and not messagebox.askyesno(
            "New project",
            "Discard the current in-memory project?",
        ):
            return
        self.model = FlowProjectModel(self._new_project())
        self.project_path = None
        self.selected_id = None
        self.module_type_combo.configure(values=self.model.module_types)
        self._refresh_all()

    def _open(self) -> None:
        path = filedialog.askopenfilename(
            title="Open schedule project",
            filetypes=[("Schedule project", "*.schproj"), ("All files", "*.*")],
        )
        if path:
            self.load_project(Path(path))

    def load_project(self, path: Path) -> None:
        try:
            project = ScheduleProject.load(path)
            model = FlowProjectModel(project)
            validation = model.validate()
            if validation.errors:
                raise ValueError("; ".join(validation.errors))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            messagebox.showerror("Open failed", str(exc))
            return
        self.model = model
        self.project_path = path
        self.selected_id = None
        self.module_type_combo.configure(values=self.model.module_types)
        self._refresh_all()
        self.status_var.set(f"Loaded {path.name}")

    def _save(self) -> None:
        if self.project_path is None:
            self._save_as()
            return
        try:
            validation = self.model.validate()
            if validation.errors:
                raise ValueError("; ".join(validation.errors))
            self.model.project.save(self.project_path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        self.status_var.set(f"Saved {self.project_path.name}")

    def _save_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save schedule project",
            defaultextension=".schproj",
            filetypes=[("Schedule project", "*.schproj"), ("All files", "*.*")],
        )
        if path:
            self.project_path = Path(path)
            self._save()

    def _add_module(self) -> None:
        module_type = self.module_type_var.get()
        identifier = simpledialog.askstring(
            "Module id",
            "Optional unique module id:",
            initialvalue="",
            parent=self.root,
        )
        if identifier is None:
            return
        try:
            node = self.model.add_module(
                module_type,
                module_id=identifier.strip() or None,
            )
        except ValueError as exc:
            messagebox.showerror("Add failed", str(exc))
            return
        self.selected_id = node.id
        self._refresh_all()

    def _remove_selected(self) -> None:
        if self.selected_id is None:
            messagebox.showwarning("No selection", "Select a module first.")
            return
        if not messagebox.askyesno(
            "Remove module",
            f"Remove {self.selected_id} and its connections?",
        ):
            return
        self.model.remove_module(self.selected_id)
        self.selected_id = None
        self._refresh_all()

    def _connect(self) -> None:
        try:
            self.model.connect(self.source_var.get(), self.target_var.get())
        except ValueError as exc:
            messagebox.showerror("Connect failed", str(exc))
            return
        self._refresh_all()

    def _disconnect(self) -> None:
        try:
            self.model.disconnect(self.source_var.get(), self.target_var.get())
        except ValueError as exc:
            messagebox.showerror("Disconnect failed", str(exc))
            return
        self._refresh_all()

    def _auto_connect(self) -> None:
        self.model.auto_connect()
        self._refresh_all()

    def _select_edge(self, _event: tk.Event) -> None:
        selected = self.edge_list.curselection()
        if not selected:
            return
        edge = self.model.project.connections[selected[0]]
        self.source_var.set(edge.source_id)
        self.target_var.set(edge.target_id)

    def _canvas_click(self, event: tk.Event) -> None:
        item_ids = self.canvas.find_overlapping(
            self.canvas.canvasx(event.x),
            self.canvas.canvasy(event.y),
            self.canvas.canvasx(event.x),
            self.canvas.canvasy(event.y),
        )
        for item_id in reversed(item_ids):
            module_id = self._canvas_items.get(item_id)
            if module_id is not None:
                self.selected_id = module_id
                self._refresh_all()
                return

    def _apply_params(self) -> None:
        if self.selected_id is None:
            messagebox.showwarning("No selection", "Select a module first.")
            return
        try:
            params = json.loads(self.params_text.get("1.0", tk.END))
            if not isinstance(params, dict):
                raise ValueError("Parameters must be a JSON object")
            self.model.update_params(self.selected_id, params)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            messagebox.showerror("Invalid parameters", str(exc))
            return
        self._refresh_all()

    def _apply_cell(self) -> None:
        try:
            data = json.loads(self.cell_text.get("1.0", tk.END))
            if not isinstance(data, dict):
                raise ValueError("Cell profile must be a JSON object")
            self.model.project.cell_profile = CellProfile.from_dict(data)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            messagebox.showerror("Invalid cell profile", str(exc))
            return
        self._refresh_all()

    def _validate(self) -> None:
        validation = self.model.validate()
        lines = [f"ERROR: {item}" for item in validation.errors]
        lines.extend(f"WARNING: {item}" for item in validation.warnings)
        if not lines:
            lines = ["Flow graph is valid."]
        self._set_validation("\n".join(lines))
        self.status_var.set(
            "Valid flow graph" if validation.is_valid else "Flow graph has errors"
        )

    def _preview(self) -> None:
        try:
            steps, warnings = self.model.preview_steps()
        except ValueError as exc:
            messagebox.showerror("Preview failed", str(exc))
            return
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)
        for index, step in enumerate(steps, start=1):
            end_summary = ", ".join(
                value
                for value in (
                    f"{step.end_time_s:g}s" if step.end_time_s is not None else "",
                    f"{step.end_voltage_v:g}V"
                    if step.end_voltage_v is not None
                    else "",
                    f"{step.loop_count} loops"
                    if step.loop_count is not None
                    else "",
                )
                if value
            )
            self.preview_tree.insert(
                "",
                tk.END,
                values=(
                    index,
                    step.step_type,
                    step.mode or "",
                    step.label,
                    step.c_rate if step.c_rate is not None else "",
                    step.voltage_v if step.voltage_v is not None else "",
                    end_summary,
                ),
            )
        self._set_validation(
            "\n".join(f"WARNING: {warning}" for warning in warnings)
            or "Preview expanded without graph warnings."
        )
        self.status_var.set(f"Previewed {len(steps)} step intents")

    def _refresh_all(self) -> None:
        ids = [node.id for node in self.model.project.modules]
        self.source_combo.configure(values=ids)
        self.target_combo.configure(values=ids)
        if self.source_var.get() not in ids:
            self.source_var.set(ids[0] if ids else "")
        if self.target_var.get() not in ids:
            self.target_var.set(ids[1] if len(ids) > 1 else (ids[0] if ids else ""))

        self.edge_list.delete(0, tk.END)
        for edge in self.model.project.connections:
            self.edge_list.insert(tk.END, f"{edge.source_id}  →  {edge.target_id}")

        self._render_canvas()
        self._render_properties()
        self.cell_text.delete("1.0", tk.END)
        self.cell_text.insert(
            tk.END,
            json.dumps(
                self.model.project.cell_profile.to_dict(),
                indent=2,
                ensure_ascii=False,
            ),
        )
        self._validate()

    def _render_canvas(self) -> None:
        self.canvas.delete("all")
        self._canvas_items.clear()
        nodes = list(self.model.project.modules)
        heights = [
            max(88, 40 + 16 * len(self.model.card_lines(node.id)) + 12)
            for node in nodes
        ]
        positions: dict[str, tuple[float, float, float]] = {}
        row_y = 36.0
        for index, node in enumerate(nodes):
            column = index % 3
            if column == 0 and index > 0:
                row_y += max(heights[index - 3 : index]) + _CARD_GAP_Y
            x = 36 + column * _CARD_GAP_X
            positions[node.id] = (x, row_y, heights[index])

        for edge in self.model.project.connections:
            source = positions.get(edge.source_id)
            target = positions.get(edge.target_id)
            if source is None or target is None:
                continue
            self.canvas.create_line(
                source[0] + _CARD_WIDTH,
                source[1] + source[2] / 2,
                target[0],
                target[1] + target[2] / 2,
                fill="#3f6f9f",
                width=2,
                arrow=tk.LAST,
            )

        for node in nodes:
            x, y, height = positions[node.id]
            selected = node.id == self.selected_id
            rectangle = self.canvas.create_rectangle(
                x,
                y,
                x + _CARD_WIDTH,
                y + height,
                fill="#d9edff" if selected else "#ffffff",
                outline="#1677c8" if selected else "#677583",
                width=3 if selected else 1,
            )
            title = self.canvas.create_text(
                x + 12,
                y + 16,
                text=f"{node.id}  ·  {node.module_type}",
                anchor=tk.W,
                font=("TkDefaultFont", 10, "bold"),
            )
            items = [rectangle, title]
            for line_index, line in enumerate(self.model.card_lines(node.id)):
                items.append(
                    self.canvas.create_text(
                        x + 12,
                        y + 38 + line_index * 16,
                        text=line,
                        anchor=tk.W,
                        fill="#425466",
                        font=("TkDefaultFont", 9),
                    )
                )
            for item in items:
                self._canvas_items[item] = node.id

        bottom = 36.0
        if positions:
            bottom = max(y + height for _, y, height in positions.values()) + 80
        self.canvas.configure(scrollregion=(0, 0, 1100, max(bottom, 800)))

    def _render_properties(self) -> None:
        self.params_text.delete("1.0", tk.END)
        self._clear_recipe_trees()
        if self.selected_id is None:
            self.selected_label.configure(text="No module selected")
            self._show_recipe_editors(False)
            return
        try:
            node = self.model.get_module(self.selected_id)
            instance = self.model.instantiate(self.selected_id)
        except ValueError:
            self.selected_id = None
            self.selected_label.configure(text="No module selected")
            self._show_recipe_editors(False)
            return
        self.selected_label.configure(text=f"{node.id} [{node.module_type}]")
        self.params_text.insert(
            tk.END,
            json.dumps(node.params, indent=2, ensure_ascii=False),
        )
        if has_editable_recipe(instance):
            self._show_recipe_editors(True)
            recipe = instance.recipe()
            specs = self.model.available_presets(self.selected_id)
            labels = [spec.key for spec in specs]
            if recipe.preset not in labels:
                labels = [recipe.preset, *labels]
            self.preset_combo.configure(values=labels)
            self.preset_var.set(recipe.preset)
            spec = PRESETS_BY_KEY.get(recipe.preset)
            self.preset_detail_var.set(spec.detail if spec else "Edited inside this module.")
            self.repeat_count_var.set(str(recipe.repeat_count))
            for section in _RECIPE_SECTIONS:
                tree = self._recipe_trees[section]
                for unit in getattr(recipe, section):
                    tree.insert("", tk.END, values=(unit.summary(),))
        else:
            self._show_recipe_editors(False)

    def _set_validation(self, text: str) -> None:
        self.validation_text.configure(state=tk.NORMAL)
        self.validation_text.delete("1.0", tk.END)
        self.validation_text.insert(tk.END, text)
        self.validation_text.configure(state=tk.DISABLED)

    def _show_recipe_editors(self, show: bool) -> None:
        if show:
            self.preset_frame.pack(
                fill=tk.X,
                pady=(8, 0),
                before=self.json_frame,
            )
            self.recipe_frame.pack(
                fill=tk.BOTH,
                expand=True,
                pady=(8, 0),
                before=self.json_frame,
            )
        else:
            self.preset_frame.pack_forget()
            self.recipe_frame.pack_forget()

    def _clear_recipe_trees(self) -> None:
        for tree in self._recipe_trees.values():
            for item in tree.get_children():
                tree.delete(item)

    def _selected_section(self) -> str:
        current = self.recipe_notebook.select()
        index = self.recipe_notebook.index(current)
        return _RECIPE_SECTIONS[index]

    def _selected_unit_index(self) -> int | None:
        tree = self._recipe_trees[self._selected_section()]
        selected = tree.selection()
        if not selected:
            return None
        return tree.index(selected[0])

    def _require_recipe_module(self):
        if self.selected_id is None:
            messagebox.showwarning("No selection", "Select a module first.")
            return None
        try:
            instance = self.model.instantiate(self.selected_id)
        except ValueError as exc:
            messagebox.showerror("Module error", str(exc))
            return None
        if not has_editable_recipe(instance):
            messagebox.showwarning(
                "No recipe",
                "This module is a single step. Use a sequence/QPEED/HPPC module to edit units.",
            )
            return None
        return instance.recipe()

    def _commit_recipe(self, recipe) -> None:
        if self.selected_id is None:
            return
        try:
            self.model.set_recipe(self.selected_id, recipe)
        except ValueError as exc:
            messagebox.showerror("Recipe update failed", str(exc))
            return
        self._refresh_all()

    def _rebuild_preset(self) -> None:
        if self.selected_id is None:
            messagebox.showwarning("No selection", "Select a module first.")
            return
        key = self.preset_var.get().strip()
        if not key or key == "custom":
            messagebox.showwarning("No preset", "Choose a named preset first.")
            return
        try:
            self.model.apply_preset(self.selected_id, key)
        except ValueError as exc:
            messagebox.showerror("Preset failed", str(exc))
            return
        self._refresh_all()

    def _apply_repeat_count(self) -> None:
        recipe = self._require_recipe_module()
        if recipe is None:
            return
        try:
            recipe.repeat_count = int(self.repeat_count_var.get())
        except ValueError:
            messagebox.showerror("Invalid count", "Repeat count must be an integer.")
            return
        self._commit_recipe(recipe)

    def _add_unit(self, kind: str) -> None:
        recipe = self._require_recipe_module()
        if recipe is None:
            return
        defaults = {
            "charge": charge(c_rate=1.0, mode="CCCV", end_voltage_v=4.2),
            "discharge": discharge(c_rate=1.0, end_voltage_v=2.5),
            "rest": rest_unit(600.0),
        }
        unit = self._unit_dialog(defaults[kind])
        if unit is None:
            return
        section = getattr(recipe, self._selected_section())
        index = self._selected_unit_index()
        if index is None:
            section.append(unit)
        else:
            section.insert(index + 1, unit)
        recipe.preset = "custom"
        self._commit_recipe(recipe)

    def _edit_selected_unit(self) -> None:
        recipe = self._require_recipe_module()
        if recipe is None:
            return
        index = self._selected_unit_index()
        if index is None:
            messagebox.showwarning("No unit", "Select a charge/discharge/rest row first.")
            return
        section = getattr(recipe, self._selected_section())
        unit = self._unit_dialog(section[index])
        if unit is None:
            return
        section[index] = unit
        recipe.preset = "custom"
        self._commit_recipe(recipe)

    def _move_unit(self, delta: int) -> None:
        recipe = self._require_recipe_module()
        if recipe is None:
            return
        index = self._selected_unit_index()
        if index is None:
            return
        section = getattr(recipe, self._selected_section())
        new_index = index + delta
        if new_index < 0 or new_index >= len(section):
            return
        section[index], section[new_index] = section[new_index], section[index]
        recipe.preset = "custom"
        self._commit_recipe(recipe)

    def _delete_unit(self) -> None:
        recipe = self._require_recipe_module()
        if recipe is None:
            return
        index = self._selected_unit_index()
        if index is None:
            return
        section = getattr(recipe, self._selected_section())
        del section[index]
        recipe.preset = "custom"
        self._commit_recipe(recipe)

    def _unit_dialog(self, initial: RecipeUnit) -> RecipeUnit | None:
        win = tk.Toplevel(self.root)
        win.title("Recipe unit")
        win.transient(self.root)
        win.grab_set()
        kind_var = tk.StringVar(value=initial.kind)
        mode_var = tk.StringVar(value=initial.mode or "CC")
        rate_var = tk.StringVar("" if initial.c_rate is None else str(initial.c_rate))
        voltage_var = tk.StringVar(
            "" if initial.end_voltage_v is None else str(initial.end_voltage_v)
        )
        time_var = tk.StringVar(
            "" if initial.end_time_s is None else str(initial.end_time_s)
        )
        label_var = tk.StringVar(value=initial.label)
        result: dict[str, RecipeUnit | None] = {"unit": None}
        fields: dict[str, tk.StringVar] = {
            "kind": kind_var,
            "mode": mode_var,
            "c_rate": rate_var,
            "end_voltage_v": voltage_var,
            "end_time_s": time_var,
            "label": label_var,
        }
        rows = (
            ("Kind", "kind", ("charge", "discharge", "rest", "end"), True),
            ("Mode", "mode", ("CCCV", "CC", "CV"), True),
            ("C-rate", "c_rate", None, False),
            ("End voltage (V)", "end_voltage_v", None, False),
            ("End time (s)", "end_time_s", None, False),
            ("Label", "label", None, False),
        )
        for title, key, values, combo in rows:
            frame = ttk.Frame(win, padding=(10, 4))
            frame.pack(fill=tk.X)
            ttk.Label(frame, text=title, width=16).pack(side=tk.LEFT)
            if combo:
                ttk.Combobox(
                    frame,
                    textvariable=fields[key],
                    values=values,
                    state="readonly",
                    width=18,
                ).pack(side=tk.LEFT, fill=tk.X, expand=True)
            else:
                ttk.Entry(frame, textvariable=fields[key], width=22).pack(
                    side=tk.LEFT,
                    fill=tk.X,
                    expand=True,
                )

        def _parse_float(raw: str) -> float | None:
            text = raw.strip()
            if not text:
                return None
            return float(text)

        def _ok() -> None:
            try:
                kind = kind_var.get()
                payload: dict[str, object] = {
                    "kind": kind,
                    "label": label_var.get().strip(),
                }
                if kind != "rest":
                    payload["mode"] = mode_var.get()
                    payload["c_rate"] = _parse_float(rate_var.get())
                    payload["end_voltage_v"] = _parse_float(voltage_var.get())
                payload["end_time_s"] = _parse_float(time_var.get())
                result["unit"] = RecipeUnit.from_dict(payload)
            except (TypeError, ValueError) as exc:
                messagebox.showerror("Invalid unit", str(exc), parent=win)
                return
            win.destroy()

        buttons = ttk.Frame(win, padding=10)
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text="OK", command=_ok).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="Cancel", command=win.destroy).pack(
            side=tk.RIGHT,
            padx=(0, 6),
        )
        win.wait_window()
        return result["unit"]


def launch_flow_editor(initial_path: str | Path | None = None) -> None:
    root = tk.Tk()
    path = Path(initial_path) if initial_path is not None else None
    FlowEditorApp(root, initial_path=path)
    root.mainloop()
