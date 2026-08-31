"""Tkinter project editor with module bulk-edit."""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ..edit import apply_bulk_edit, common_bulk_params, list_editable_params
from ..ir.project import ScheduleProject


class ProjectEditorApp:
    def __init__(self, root: tk.Tk, initial_path: Path | None = None) -> None:
        self.root = root
        self.root.title("PNE Scheduler — Project Editor")
        self.root.geometry("1100x720")
        self._project: ScheduleProject | None = None
        self._project_path: Path | None = None
        self._module_vars: dict[str, tk.BooleanVar] = {}

        self._build_ui()
        if initial_path is not None and initial_path.exists():
            self.load_project(initial_path)

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self.root, padding=6)
        toolbar.pack(fill=tk.X)

        ttk.Button(toolbar, text="Open .schproj…", command=self._open_project).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Save", command=self._save_project).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(toolbar, text="Save As…", command=self._save_project_as).pack(side=tk.LEFT, padx=(6, 0))

        body = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        left = ttk.LabelFrame(body, text="Modules", padding=8)
        right = ttk.LabelFrame(body, text="Bulk edit", padding=8)
        body.add(left, weight=1)
        body.add(right, weight=2)

        sel_row = ttk.Frame(left)
        sel_row.pack(fill=tk.X, pady=(0, 6))
        self.select_all_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            sel_row,
            text="Select all",
            variable=self.select_all_var,
            command=self._toggle_select_all,
        ).pack(side=tk.LEFT)
        ttk.Button(sel_row, text="Invert", command=self._invert_selection).pack(side=tk.LEFT, padx=6)

        self.module_canvas = tk.Canvas(left, highlightthickness=0)
        module_scroll = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.module_canvas.yview)
        self.module_frame = ttk.Frame(self.module_canvas)
        self.module_frame.bind(
            "<Configure>",
            lambda _e: self.module_canvas.configure(scrollregion=self.module_canvas.bbox("all")),
        )
        self.module_canvas.create_window((0, 0), window=self.module_frame, anchor="nw")
        self.module_canvas.configure(yscrollcommand=module_scroll.set)
        self.module_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        module_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Label(right, text="Parameter").grid(row=0, column=0, sticky="w")
        self.param_var = tk.StringVar(value="charge_c_rate")
        self.param_combo = ttk.Combobox(
            right,
            textvariable=self.param_var,
            values=list(common_bulk_params()),
            width=28,
        )
        self.param_combo.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        ttk.Label(right, text="Value").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.value_var = tk.StringVar(value="0.5")
        ttk.Entry(right, textvariable=self.value_var, width=30).grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0)
        )

        ttk.Label(right, text="Quick presets").grid(row=2, column=0, sticky="nw", pady=(12, 0))
        preset_frame = ttk.Frame(right)
        preset_frame.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(12, 0))
        for label, param, value in (
            ("FM 0.1C", "charge_c_rate", "0.1"),
            ("Cycle 0.5C", "charge_c_rate", "0.5"),
            ("Capa C/3", "measurement_c_rate", "C/3"),
            ("RPT C/3", "reference_c_rate", "C/3"),
        ):
            ttk.Button(
                preset_frame,
                text=label,
                command=lambda p=param, v=value: self._apply_preset(p, v),
            ).pack(side=tk.LEFT, padx=(0, 6), pady=2)

        ttk.Label(right, text="JSON patch").grid(row=3, column=0, sticky="nw", pady=(12, 0))
        self.patch_text = tk.Text(right, height=6, width=40, font=("Consolas", 10))
        self.patch_text.grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=(12, 0))
        self.patch_text.insert(
            tk.END,
            '{\n  "charge_c_rate": 0.5,\n  "discharge_c_rate": 0.5\n}',
        )

        btn_row = ttk.Frame(right)
        btn_row.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Button(btn_row, text="Apply to selected", command=self._apply_selected).pack(
            side=tk.LEFT
        )
        ttk.Button(btn_row, text="Apply to ALL modules", command=self._apply_all).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(btn_row, text="Apply JSON patch (selected)", command=self._apply_json_selected).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        ttk.Label(right, text="Log").grid(row=5, column=0, sticky="nw", pady=(12, 0))
        self.log_text = tk.Text(right, height=16, width=60, font=("Consolas", 9))
        self.log_text.grid(row=5, column=1, sticky="nsew", padx=(8, 0), pady=(12, 0))
        right.columnconfigure(1, weight=1)
        right.rowconfigure(5, weight=1)

        self.status_var = tk.StringVar(value="Open a .schproj file.")
        ttk.Label(self.root, textvariable=self.status_var, padding=6).pack(fill=tk.X)

    def _apply_preset(self, param: str, value: str) -> None:
        self.param_var.set(param)
        self.value_var.set(value)

    def _toggle_select_all(self) -> None:
        checked = self.select_all_var.get()
        for var in self._module_vars.values():
            var.set(checked)

    def _invert_selection(self) -> None:
        for var in self._module_vars.values():
            var.set(not var.get())

    def _selected_module_ids(self) -> list[str]:
        return [mid for mid, var in self._module_vars.items() if var.get()]

    def _open_project(self) -> None:
        path = filedialog.askopenfilename(
            title="Open project",
            filetypes=[("Schedule project", "*.schproj"), ("All files", "*.*")],
        )
        if path:
            self.load_project(Path(path))

    def load_project(self, path: Path) -> None:
        try:
            project = ScheduleProject.load(path)
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
            messagebox.showerror("Load failed", str(exc))
            return

        self._project = project
        self._project_path = path
        self._render_modules()
        self.status_var.set(f"Loaded {path.name} — {len(project.modules)} module(s)")
        self._log(f"Loaded {path}")

    def _render_modules(self) -> None:
        for child in self.module_frame.winfo_children():
            child.destroy()
        self._module_vars.clear()

        if self._project is None:
            return

        for node in self._project.modules:
            var = tk.BooleanVar(value=True)
            self._module_vars[node.id] = var
            params_preview = ", ".join(f"{k}={v}" for k, v in list(node.params.items())[:3])
            label = f"{node.id}  [{node.module_type}]"
            if params_preview:
                label += f"  ({params_preview})"
            ttk.Checkbutton(self.module_frame, text=label, variable=var).pack(anchor="w", pady=2)

            fields = list_editable_params(node.module_type)
            if fields:
                ttk.Label(
                    self.module_frame,
                    text=f"    editable: {', '.join(fields[:8])}{'…' if len(fields) > 8 else ''}",
                    font=("Segoe UI", 8),
                ).pack(anchor="w")

        self.select_all_var.set(True)

    def _save_project(self) -> None:
        if self._project is None:
            return
        if self._project_path is None:
            self._save_project_as()
            return
        self._project.save(self._project_path)
        self._log(f"Saved {self._project_path}")
        self.status_var.set(f"Saved {self._project_path.name}")

    def _save_project_as(self) -> None:
        if self._project is None:
            return
        path = filedialog.asksaveasfilename(
            title="Save project",
            defaultextension=".schproj",
            filetypes=[("Schedule project", "*.schproj"), ("All files", "*.*")],
        )
        if not path:
            return
        self._project_path = Path(path)
        self._save_project()

    def _apply_selected(self) -> None:
        ids = self._selected_module_ids()
        if not ids:
            messagebox.showwarning("No selection", "Select at least one module.")
            return
        self._run_bulk_edit({self.param_var.get(): self.value_var.get()}, module_ids=ids)

    def _apply_all(self) -> None:
        if self._project is None:
            return
        if not messagebox.askyesno(
            "Apply to all",
            f"Apply {self.param_var.get()}={self.value_var.get()} to ALL modules?",
        ):
            return
        self._run_bulk_edit(
            {self.param_var.get(): self.value_var.get()},
            all_modules=True,
        )

    def _apply_json_selected(self) -> None:
        ids = self._selected_module_ids()
        if not ids:
            messagebox.showwarning("No selection", "Select at least one module.")
            return
        try:
            patch = json.loads(self.patch_text.get("1.0", tk.END))
        except json.JSONDecodeError as exc:
            messagebox.showerror("Invalid JSON", str(exc))
            return
        if not isinstance(patch, dict):
            messagebox.showerror("Invalid JSON", "Patch must be a JSON object.")
            return
        self._run_bulk_edit(patch, module_ids=ids)

    def _run_bulk_edit(
        self,
        patch: dict,
        *,
        module_ids: list[str] | None = None,
        all_modules: bool = False,
    ) -> None:
        if self._project is None:
            return
        result = apply_bulk_edit(
            self._project,
            patch,
            module_ids=module_ids,
            all_modules=all_modules,
        )
        for change in result.changes:
            self._log(
                f"  {change.module_id} [{change.module_type}] "
                f"{change.key}: {change.old_value!r} → {change.new_value!r}"
            )
        for err in result.errors:
            self._log(f"  ERROR: {err}")
        if result.skipped_module_ids:
            self._log(f"  skipped (no change): {', '.join(result.skipped_module_ids)}")

        self._render_modules()
        summary = f"Updated {result.updated_count} module(s)"
        self.status_var.set(summary)
        self._log(summary)

    def _log(self, message: str) -> None:
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)


def launch_project_editor(initial_path: str | Path | None = None) -> None:
    root = tk.Tk()
    path = Path(initial_path) if initial_path is not None else None
    ProjectEditorApp(root, initial_path=path)
    root.mainloop()
