"""Tkinter module-flow editor for .schproj projects."""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from ..engine.duration import format_duration
from ..ir.cell_profile import CellProfile
from ..ir.project import ScheduleProject
from .flow_model import FlowDurationEstimate, FlowProjectModel


class FlowEditorApp:
    def __init__(self, root: tk.Tk, initial_path: Path | None = None) -> None:
        self.root = root
        self.root.title("PNE Scheduler — Module Flow Editor")
        self.root.geometry("1280x820")
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
        self.duration_var = tk.StringVar(value="Estimated total: —")
        ttk.Label(
            self.root,
            textvariable=self.duration_var,
            padding=(10, 4),
            foreground="#245c3d",
        ).pack(fill=tk.X)

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

        columns = (
            "no",
            "type",
            "mode",
            "label",
            "c_rate",
            "voltage",
            "duration",
            "end",
        )
        self.preview_tree = ttk.Treeview(
            preview_frame,
            columns=columns,
            show="headings",
            height=8,
        )
        widths = (45, 85, 65, 230, 70, 70, 95, 120)
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
        ttk.Label(module_tab, text="Parameters (JSON)").pack(anchor=tk.W, pady=(8, 0))
        self.params_text = tk.Text(module_tab, width=35, height=24, font=("TkFixedFont", 10))
        self.params_text.pack(fill=tk.BOTH, expand=True, pady=(4, 6))
        ttk.Button(module_tab, text="Apply parameters", command=self._apply_params).pack(
            fill=tk.X
        )

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
            duration = self.model.estimate_duration()
        except ValueError as exc:
            messagebox.showerror("Preview failed", str(exc))
            return
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)
        for index, (step, step_duration) in enumerate(
            zip(steps, duration.total.steps),
            start=1,
        ):
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
                    (
                        ("~" if step_duration.approximate else "")
                        + format_duration(step_duration.seconds)
                        if step_duration.seconds is not None
                        else "unknown"
                    ),
                    end_summary,
                ),
            )
        duration_warnings = tuple(dict.fromkeys((*warnings, *duration.warnings)))
        self._set_validation(
            "\n".join(f"WARNING: {warning}" for warning in duration_warnings)
            or "Preview expanded without graph warnings."
        )
        self._set_duration_summary(duration)
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
        try:
            self._set_duration_summary(self.model.estimate_duration())
        except ValueError:
            self.duration_var.set("Estimated total: unavailable until graph errors are fixed")

    def _render_canvas(self) -> None:
        self.canvas.delete("all")
        self._canvas_items.clear()
        positions: dict[str, tuple[float, float]] = {}
        try:
            duration_by_id = {
                item.module_id: item.estimate
                for item in self.model.estimate_duration().modules
            }
        except ValueError:
            duration_by_id = {}
        for index, node in enumerate(self.model.project.modules):
            column = index % 4
            row = index // 4
            x = 45 + column * 260
            y = 45 + row * 165
            positions[node.id] = (x, y)

        for edge in self.model.project.connections:
            source = positions.get(edge.source_id)
            target = positions.get(edge.target_id)
            if source is None or target is None:
                continue
            self.canvas.create_line(
                source[0] + 200,
                source[1] + 50,
                target[0],
                target[1] + 50,
                fill="#3f6f9f",
                width=2,
                arrow=tk.LAST,
            )

        for node in self.model.project.modules:
            x, y = positions[node.id]
            selected = node.id == self.selected_id
            rectangle = self.canvas.create_rectangle(
                x,
                y,
                x + 200,
                y + 105,
                fill=(
                    "#fff3d6"
                    if "loop_count" in node.params or "cycle_count" in node.params
                    else ("#d9edff" if selected else "#ffffff")
                ),
                outline="#1677c8" if selected else "#677583",
                width=3 if selected else 1,
            )
            title = self.canvas.create_text(
                x + 12,
                y + 18,
                text=node.id,
                anchor=tk.W,
                font=("TkDefaultFont", 10, "bold"),
            )
            kind = self.canvas.create_text(
                x + 12,
                y + 46,
                text=node.module_type,
                anchor=tk.W,
                fill="#425466",
            )
            repeat_value = node.params.get(
                "loop_count",
                node.params.get("cycle_count"),
            )
            badge_text = (
                f"cycle block × {repeat_value}"
                if repeat_value is not None
                else "single block"
            )
            badge = self.canvas.create_text(
                x + 12,
                y + 68,
                text=badge_text,
                anchor=tk.W,
                fill="#8a5a00" if repeat_value is not None else "#637282",
            )
            estimate = duration_by_id.get(node.id)
            duration_text = (
                f"estimated: ~{format_duration(estimate.estimated_seconds)}"
                if estimate is not None
                else "estimated: unavailable"
            )
            duration_item = self.canvas.create_text(
                x + 12,
                y + 90,
                text=duration_text,
                anchor=tk.W,
                fill="#245c3d",
            )
            for item in (rectangle, title, kind, badge, duration_item):
                self._canvas_items[item] = node.id

    def _render_properties(self) -> None:
        self.params_text.delete("1.0", tk.END)
        if self.selected_id is None:
            self.selected_label.configure(text="No module selected")
            return
        try:
            node = self.model.get_module(self.selected_id)
        except ValueError:
            self.selected_id = None
            self.selected_label.configure(text="No module selected")
            return
        self.selected_label.configure(text=f"{node.id} [{node.module_type}]")
        self.params_text.insert(
            tk.END,
            json.dumps(node.params, indent=2, ensure_ascii=False),
        )

    def _set_validation(self, text: str) -> None:
        self.validation_text.configure(state=tk.NORMAL)
        self.validation_text.delete("1.0", tk.END)
        self.validation_text.insert(tk.END, text)
        self.validation_text.configure(state=tk.DISABLED)

    def _set_duration_summary(self, duration: FlowDurationEstimate) -> None:
        total = duration.total
        prefix = "~" if not total.is_exact else ""
        summary = f"Estimated total: {prefix}{format_duration(total.estimated_seconds)}"
        if total.unknown_step_count:
            summary += f" + {total.unknown_step_count} unknown step execution(s)"
        summary += " (nominal estimate; CV taper and equipment overhead may be excluded)"
        self.duration_var.set(summary)


def launch_flow_editor(initial_path: str | Path | None = None) -> None:
    root = tk.Tk()
    path = Path(initial_path) if initial_path is not None else None
    FlowEditorApp(root, initial_path=path)
    root.mainloop()
