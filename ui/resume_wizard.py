"""Wizard UI — load .sch + cycler data, find interruption, export resumed schedule."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ..io.sch_parser import parse_schedule_file
from ..resume import build_resume_plan, detect_checkpoint, splice_resume_schedule


class ResumeWizardApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PNE Scheduler — Resume Wizard")
        self.root.geometry("960x700")

        self.sch_path: Path | None = None
        self.data_path: Path | None = None
        self._plan = None

        self._build_ui()

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self.root, padding=8)
        toolbar.pack(fill=tk.X)

        ttk.Button(toolbar, text="Open .sch…", command=self._open_sch).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Open data (StepEnd/raw)…", command=self._open_data).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(toolbar, text="Analyze", command=self._analyze).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(toolbar, text="Export resumed .sch…", command=self._export).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        paths = ttk.LabelFrame(self.root, text="Files", padding=8)
        paths.pack(fill=tk.X, padx=8, pady=(0, 6))
        self.sch_label = ttk.Label(paths, text="Schedule: (none)")
        self.sch_label.pack(anchor="w")
        self.data_label = ttk.Label(paths, text="Data: (none)")
        self.data_label.pack(anchor="w")

        checkpoint = ttk.LabelFrame(self.root, text="Checkpoint", padding=8)
        checkpoint.pack(fill=tk.X, padx=8, pady=(0, 6))
        self.checkpoint_text = tk.Text(checkpoint, height=8, font=("Consolas", 10))
        self.checkpoint_text.pack(fill=tk.X)

        override = ttk.LabelFrame(self.root, text="Resume options", padding=8)
        override.pack(fill=tk.X, padx=8, pady=(0, 6))

        row1 = ttk.Frame(override)
        row1.pack(fill=tk.X)
        ttk.Label(row1, text="Resume SCH step").pack(side=tk.LEFT)
        self.resume_step_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.resume_step_var, width=8).pack(side=tk.LEFT, padx=(8, 16))
        ttk.Label(row1, text="Remaining loops (optional)").pack(side=tk.LEFT)
        self.remaining_loops_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.remaining_loops_var, width=8).pack(side=tk.LEFT, padx=(8, 0))

        body = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        orig = ttk.LabelFrame(body, text="Original schedule", padding=6)
        resumed = ttk.LabelFrame(body, text="Resumed preview (from splice step)", padding=6)
        body.add(orig, weight=1)
        body.add(resumed, weight=1)

        self.orig_tree = self._make_tree(orig)
        self.resume_tree = self._make_tree(resumed)

        self.status_var = tk.StringVar(value="Load a .sch and StepEnd/raw CSV to begin.")
        ttk.Label(self.root, textvariable=self.status_var, padding=6).pack(fill=tk.X)

    def _make_tree(self, parent: ttk.LabelFrame) -> ttk.Treeview:
        tree = ttk.Treeview(parent, columns=("no", "type", "iref"), show="headings", height=20)
        tree.heading("no", text="Step")
        tree.heading("type", text="Type")
        tree.heading("iref", text="Iref")
        tree.column("no", width=50, anchor=tk.CENTER)
        tree.column("type", width=90, anchor=tk.CENTER)
        tree.column("iref", width=80, anchor=tk.CENTER)
        tree.pack(fill=tk.BOTH, expand=True)
        return tree

    def _open_sch(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("PNE schedule", "*.sch")])
        if path:
            self.sch_path = Path(path)
            self.sch_label.configure(text=f"Schedule: {self.sch_path.name}")
            self._load_original_preview()

    def _open_data(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("CSV data", "*.csv"), ("All", "*.*")])
        if path:
            self.data_path = Path(path)
            self.data_label.configure(text=f"Data: {self.data_path.name}")

    def _load_original_preview(self) -> None:
        if self.sch_path is None:
            return
        try:
            doc = parse_schedule_file(self.sch_path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Load failed", str(exc))
            return
        self._fill_tree(self.orig_tree, doc.steps, highlight_from=None)

    def _analyze(self) -> None:
        if self.sch_path is None or self.data_path is None:
            messagebox.showwarning("Missing files", "Open both .sch and data CSV.")
            return
        try:
            checkpoint = detect_checkpoint(self.data_path, source_sch=self.sch_path)
            resume_override = self._optional_int(self.resume_step_var.get())
            loops_override = self._optional_int(self.remaining_loops_var.get())
            plan = build_resume_plan(
                self.sch_path,
                self.data_path,
                resume_sch_step=resume_override,
                remaining_loop_count=loops_override,
            )
        except ValueError as exc:
            messagebox.showerror("Analyze failed", str(exc))
            return

        self._plan = plan
        cp = plan.checkpoint
        lines = [
            f"Data file: {cp.data_path.name}",
            f"Last completed: CTS step {cp.last_completed_cts_step} / SCH step {cp.last_completed_sch_step}",
            f"Resume from SCH step: {plan.resume_sch_step}",
            f"Step completed: {cp.step_completed}   Finished: {cp.is_finished}",
            f"TotalCycle: {cp.total_cycle}   CycleNum: {cp.cycle_num}",
            f"Completed loops (est.): {cp.completed_loop_iterations}",
            f"Remaining loops (plan): {plan.remaining_loop_count}",
            f"Confidence: {cp.confidence}",
            f"Detail: {cp.detail}",
        ]
        if plan.warnings:
            lines.append("Warnings:")
            lines.extend(f"  - {w}" for w in plan.warnings)

        self.checkpoint_text.delete("1.0", tk.END)
        self.checkpoint_text.insert(tk.END, "\n".join(lines))

        if resume_override is None:
            self.resume_step_var.set(str(plan.resume_sch_step))
        if loops_override is None and plan.remaining_loop_count is not None:
            self.remaining_loops_var.set(str(plan.remaining_loop_count))

        try:
            doc = parse_schedule_file(self.sch_path)
            self._fill_tree(self.orig_tree, doc.steps, highlight_from=plan.resume_sch_step)
            resumed_steps = [s for s in doc.steps if s.step_no >= plan.resume_sch_step and s.step_type != "END"]
            self._fill_tree(self.resume_tree, resumed_steps, highlight_from=None)
        except (OSError, ValueError):
            pass

        self.status_var.set(f"Ready to export — {plan.splice_summary}")

    def _export(self) -> None:
        if self.sch_path is None or self.data_path is None:
            messagebox.showwarning("Missing files", "Analyze first.")
            return
        out = filedialog.asksaveasfilename(
            defaultextension=".sch",
            filetypes=[("PNE schedule", "*.sch")],
            initialfile=f"{self.sch_path.stem}_resume.sch",
        )
        if not out:
            return
        try:
            result = splice_resume_schedule(
                self.sch_path,
                self.data_path,
                out,
                resume_sch_step=self._optional_int(self.resume_step_var.get()),
                remaining_loop_count=self._optional_int(self.remaining_loops_var.get()),
            )
        except ValueError as exc:
            messagebox.showerror("Export failed", str(exc))
            return

        messagebox.showinfo(
            "Exported",
            f"Wrote {result.output_path.name}\n{result.plan.splice_summary}",
        )
        self.status_var.set(f"Exported {result.output_path}")

    def _fill_tree(self, tree: ttk.Treeview, steps, highlight_from: int | None) -> None:
        tree.delete(*tree.get_children())
        for step in steps:
            tags = ()
            if highlight_from is not None and step.step_no >= highlight_from:
                tags = ("resume",)
            tree.insert(
                "",
                tk.END,
                values=(step.step_no, step.step_type, f"{step.f_iref:.0f}" if step.f_iref else ""),
                tags=tags,
            )
        tree.tag_configure("resume", background="#e8f4e8")

    @staticmethod
    def _optional_int(text: str) -> int | None:
        text = text.strip()
        if not text:
            return None
        return int(text)


def launch_resume_wizard() -> None:
    root = tk.Tk()
    ResumeWizardApp(root)
    root.mainloop()
