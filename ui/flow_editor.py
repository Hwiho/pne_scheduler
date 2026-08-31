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
from .flow_theme import (
    CARD_GAP_X,
    CARD_GAP_Y,
    CARD_HEIGHT,
    CARD_RADIUS,
    CARD_WIDTH,
    PORT_RADIUS,
    module_style,
    rounded_rect_points,
)


class FlowEditorApp:
    def __init__(self, root: tk.Tk, initial_path: Path | None = None) -> None:
        self.root = root
        self.root.title("PNE Scheduler — Module Flow Editor")
        self.root.geometry("1280x840")
        self.root.configure(bg="#f6f1ea")
        self.project_path: Path | None = None
        self.model = FlowProjectModel(self._new_project())
        self.selected_id: str | None = None
        self.pending_source: str | None = None
        self.selected_wire: tuple[str, str] | None = None
        self._canvas_items: dict[int, str] = {}

        self._configure_style()
        self._build_ui()
        if initial_path is not None and initial_path.exists():
            self.load_project(initial_path)
        else:
            self._refresh_all()

    @staticmethod
    def _configure_style() -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background="#f6f1ea")
        style.configure("TLabel", background="#f6f1ea", foreground="#3b2f27")
        style.configure("TButton", padding=6)
        style.configure("Hint.TLabel", foreground="#7a6452", font=("TkDefaultFont", 9))
        style.configure("Duration.TLabel", foreground="#245c3d", font=("TkDefaultFont", 10, "bold"))

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
        toolbar = ttk.Frame(self.root, padding=8)
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
            style="Duration.TLabel",
            padding=(12, 4),
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
            background="#fffaf3",
            foreground="#3b2f27",
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
        ttk.Label(parent, text="Sequence wires").pack(anchor=tk.W, pady=(4, 0))
        ttk.Label(
            parent,
            text="Attach like LabVIEW: click an output port, then an input port. Click a wire to detach it.",
            style="Hint.TLabel",
            wraplength=210,
        ).pack(anchor=tk.W, pady=(4, 8))
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
        ttk.Button(parent, text="Attach", command=self._connect).pack(
            fill=tk.X,
            pady=(6, 0),
        )
        ttk.Button(parent, text="Detach wire", command=self._disconnect).pack(
            fill=tk.X,
            pady=(4, 0),
        )
        ttk.Button(parent, text="Chain in list order", command=self._auto_connect).pack(
            fill=tk.X,
            pady=(4, 12),
        )

        ttk.Label(parent, text="Current sequence").pack(anchor=tk.W)
        self.edge_list = tk.Listbox(
            parent,
            height=9,
            activestyle="dotbox",
            background="#fffaf3",
            highlightthickness=0,
        )
        self.edge_list.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.edge_list.bind("<<ListboxSelect>>", self._select_edge)

    def _build_canvas(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Flow canvas").pack(anchor=tk.W)
        ttk.Label(
            parent,
            text="Left-to-right sequence. Rounded cards are experiment blocks; dots are attach/detach ports.",
            style="Hint.TLabel",
        ).pack(anchor=tk.W)
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.canvas = tk.Canvas(
            frame,
            background="#fbf6ef",
            highlightthickness=0,
            scrollregion=(0, 0, 2400, 1400),
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
        self.canvas.bind("<Double-Button-1>", self._canvas_double_click)
        self.root.bind("<Escape>", self._cancel_pending)

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
        self.params_text = tk.Text(
            module_tab,
            width=35,
            height=24,
            font=("TkFixedFont", 10),
            background="#fffaf3",
        )
        self.params_text.pack(fill=tk.BOTH, expand=True, pady=(4, 6))
        ttk.Button(module_tab, text="Apply parameters", command=self._apply_params).pack(
            fill=tk.X
        )

        ttk.Label(cell_tab, text="Cell profile (JSON)").pack(anchor=tk.W)
        self.cell_text = tk.Text(
            cell_tab,
            width=35,
            height=24,
            font=("TkFixedFont", 10),
            background="#fffaf3",
        )
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
        self.pending_source = None
        self.selected_wire = None
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
        self.pending_source = None
        self.selected_wire = None
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
        self.pending_source = None
        self.selected_wire = None
        self._refresh_all()

    def _connect(self) -> None:
        try:
            notes = self.model.rewire(self.source_var.get(), self.target_var.get())
        except ValueError as exc:
            messagebox.showerror("Attach failed", str(exc))
            return
        self.pending_source = None
        self.selected_wire = (self.source_var.get(), self.target_var.get())
        self._refresh_all()
        self.status_var.set("  ·  ".join(notes) or "Sequence unchanged")

    def _disconnect(self) -> None:
        source = self.source_var.get()
        target = self.target_var.get()
        if self.selected_wire is not None:
            source, target = self.selected_wire
        try:
            self.model.disconnect(source, target)
        except ValueError as exc:
            messagebox.showerror("Detach failed", str(exc))
            return
        self.selected_wire = None
        self._refresh_all()
        self.status_var.set(f"Detached {source} → {target}")

    def _auto_connect(self) -> None:
        self.model.auto_connect()
        self.pending_source = None
        self._refresh_all()

    def _select_edge(self, _event: tk.Event) -> None:
        selected = self.edge_list.curselection()
        if not selected:
            return
        edge = self.model.project.connections[selected[0]]
        self.source_var.set(edge.source_id)
        self.target_var.set(edge.target_id)
        self.selected_wire = (edge.source_id, edge.target_id)
        self._render_canvas()

    def _cancel_pending(self, _event: tk.Event | None = None) -> None:
        if self.pending_source is None:
            return
        self.pending_source = None
        self._render_canvas()
        self.status_var.set("Cancelled attach")

    def _canvas_hit(self, event: tk.Event) -> tuple[str, ...]:
        item_ids = self.canvas.find_overlapping(
            self.canvas.canvasx(event.x),
            self.canvas.canvasy(event.y),
            self.canvas.canvasx(event.x),
            self.canvas.canvasy(event.y),
        )
        if not item_ids:
            return ()
        return self.canvas.gettags(item_ids[-1])

    def _canvas_click(self, event: tk.Event) -> None:
        tags = self._canvas_hit(event)
        port_out = next((tag[9:] for tag in tags if tag.startswith("port-out:")), None)
        port_in = next((tag[8:] for tag in tags if tag.startswith("port-in:")), None)
        wire = next((tag[5:] for tag in tags if tag.startswith("wire:")), None)
        module_id = next((tag[7:] for tag in tags if tag.startswith("module:")), None)

        if port_out:
            self.pending_source = port_out
            self.selected_id = port_out
            self.source_var.set(port_out)
            self._refresh_all()
            self.status_var.set(f"Click an input port to attach after {port_out}")
            return
        if port_in and self.pending_source:
            try:
                notes = self.model.rewire(self.pending_source, port_in)
            except ValueError as exc:
                messagebox.showerror("Attach failed", str(exc))
                return
            self.selected_id = port_in
            self.selected_wire = (self.pending_source, port_in)
            self.source_var.set(self.pending_source)
            self.target_var.set(port_in)
            self.pending_source = None
            self._refresh_all()
            self.status_var.set("  ·  ".join(notes))
            return
        if wire:
            source_id, target_id = wire.split(">", 1)
            self.selected_wire = (source_id, target_id)
            self.source_var.set(source_id)
            self.target_var.set(target_id)
            self.pending_source = None
            self._render_canvas()
            self.status_var.set(f"Selected wire {source_id} → {target_id}. Detach or double-click to remove.")
            return
        if module_id:
            self.selected_id = module_id
            self.pending_source = None
            self._refresh_all()
            return
        self.pending_source = None
        self._render_canvas()

    def _canvas_double_click(self, event: tk.Event) -> None:
        tags = self._canvas_hit(event)
        wire = next((tag[5:] for tag in tags if tag.startswith("wire:")), None)
        if wire is None:
            return
        source_id, target_id = wire.split(">", 1)
        try:
            self.model.disconnect(source_id, target_id)
        except ValueError as exc:
            messagebox.showerror("Detach failed", str(exc))
            return
        self.selected_wire = None
        self._refresh_all()
        self.status_var.set(f"Detached {source_id} → {target_id}")

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
        selected_index = None
        for index, edge in enumerate(self.model.project.connections):
            self.edge_list.insert(tk.END, f"{edge.source_id}  →  {edge.target_id}")
            if self.selected_wire == (edge.source_id, edge.target_id):
                selected_index = index
        if selected_index is not None:
            self.edge_list.selection_set(selected_index)

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

    def _module_positions(self) -> dict[str, tuple[float, float]]:
        positions: dict[str, tuple[float, float]] = {}
        for index, node in enumerate(self.model.ordered_modules()):
            column = index % 4
            row = index // 4
            x = 48 + column * (CARD_WIDTH + CARD_GAP_X)
            y = 48 + row * (CARD_HEIGHT + CARD_GAP_Y)
            positions[node.id] = (x, y)
        return positions

    def _draw_rounded(self, x1: float, y1: float, x2: float, y2: float, **kwargs) -> int:
        return self.canvas.create_polygon(
            *rounded_rect_points(x1, y1, x2, y2, CARD_RADIUS),
            smooth=True,
            splinesteps=28,
            **kwargs,
        )

    def _render_canvas(self) -> None:
        self.canvas.delete("all")
        self._canvas_items.clear()
        width = int(self.canvas.cget("scrollregion").split()[2])
        height = int(self.canvas.cget("scrollregion").split()[3])
        for x in range(24, width, 28):
            for y in range(24, height, 28):
                self.canvas.create_oval(x, y, x + 2, y + 2, fill="#eadfce", outline="")

        positions = self._module_positions()
        try:
            duration_by_id = {
                item.module_id: item.estimate
                for item in self.model.estimate_duration().modules
            }
        except ValueError:
            duration_by_id = {}

        for edge in self.model.project.connections:
            source = positions.get(edge.source_id)
            target = positions.get(edge.target_id)
            if source is None or target is None:
                continue
            selected = self.selected_wire == (edge.source_id, edge.target_id)
            x0, y0 = source[0] + CARD_WIDTH, source[1] + CARD_HEIGHT / 2
            x1, y1 = target[0], target[1] + CARD_HEIGHT / 2
            mid = (x0 + x1) / 2
            self.canvas.create_line(
                x0,
                y0,
                mid,
                y0,
                mid,
                y1,
                x1,
                y1,
                fill="#e08a5d" if selected else "#8b6cc9",
                width=5 if selected else 3,
                smooth=True,
                splinesteps=24,
                capstyle=tk.ROUND,
                arrow=tk.LAST,
                arrowshape=(12, 16, 6),
                tags=(f"wire:{edge.source_id}>{edge.target_id}",),
            )

        for node in self.model.project.modules:
            x, y = positions[node.id]
            style = module_style(node.module_type)
            selected = node.id == self.selected_id
            self._draw_rounded(
                x + 4,
                y + 6,
                x + CARD_WIDTH + 4,
                y + CARD_HEIGHT + 6,
                fill="#e4d5c5",
                outline="",
            )
            body = self._draw_rounded(
                x,
                y,
                x + CARD_WIDTH,
                y + CARD_HEIGHT,
                fill=style.fill_selected if selected else style.fill,
                outline=style.accent if selected else "#d7c7b6",
                width=3 if selected else 1,
                tags=(f"module:{node.id}",),
            )
            accent = self.canvas.create_rectangle(
                x + 18,
                y + 10,
                x + CARD_WIDTH - 18,
                y + 14,
                fill=style.accent,
                outline="",
                tags=(f"module:{node.id}",),
            )
            icon = self.canvas.create_text(
                x + 22,
                y + 38,
                text=style.icon,
                anchor=tk.W,
                font=("TkDefaultFont", 16),
                tags=(f"module:{node.id}",),
            )
            title = self.canvas.create_text(
                x + 52,
                y + 32,
                text=style.title,
                anchor=tk.W,
                fill=style.ink,
                font=("TkDefaultFont", 11, "bold"),
                tags=(f"module:{node.id}",),
            )
            identity = self.canvas.create_text(
                x + 52,
                y + 52,
                text=node.id,
                anchor=tk.W,
                fill=style.mute,
                font=("TkDefaultFont", 8),
                tags=(f"module:{node.id}",),
            )
            repeat_value = node.params.get(
                "loop_count",
                node.params.get("cycle_count"),
            )
            badge_text = (
                f"cycle × {repeat_value}"
                if repeat_value is not None
                else "single pass"
            )
            badge_bg = self._draw_rounded(
                x + 18,
                y + 66,
                x + 132,
                y + 90,
                fill="#fffaf3",
                outline=style.accent,
                width=1,
                tags=(f"module:{node.id}",),
            )
            badge = self.canvas.create_text(
                x + 28,
                y + 78,
                text=badge_text,
                anchor=tk.W,
                fill=style.accent,
                font=("TkDefaultFont", 8, "bold"),
                tags=(f"module:{node.id}",),
            )
            estimate = duration_by_id.get(node.id)
            duration_text = (
                f"~{format_duration(estimate.estimated_seconds)}"
                if estimate is not None
                else "time unknown"
            )
            duration_item = self.canvas.create_text(
                x + 22,
                y + 108,
                text=duration_text,
                anchor=tk.W,
                fill=style.ink,
                font=("TkDefaultFont", 9),
                tags=(f"module:{node.id}",),
            )
            in_fill = "#fffaf3"
            out_fill = "#ffe4a3" if self.pending_source == node.id else "#fffaf3"
            port_in = self.canvas.create_oval(
                x - PORT_RADIUS,
                y + CARD_HEIGHT / 2 - PORT_RADIUS,
                x + PORT_RADIUS,
                y + CARD_HEIGHT / 2 + PORT_RADIUS,
                fill=in_fill,
                outline=style.accent,
                width=2,
                tags=(f"port-in:{node.id}",),
            )
            port_out = self.canvas.create_oval(
                x + CARD_WIDTH - PORT_RADIUS,
                y + CARD_HEIGHT / 2 - PORT_RADIUS,
                x + CARD_WIDTH + PORT_RADIUS,
                y + CARD_HEIGHT / 2 + PORT_RADIUS,
                fill=out_fill,
                outline=style.accent,
                width=2,
                tags=(f"port-out:{node.id}",),
            )
            for item in (
                body,
                accent,
                icon,
                title,
                identity,
                badge_bg,
                badge,
                duration_item,
                port_in,
                port_out,
            ):
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
        style = module_style(node.module_type)
        self.selected_label.configure(text=f"{style.icon}  {style.title}  ·  {node.id}")
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
