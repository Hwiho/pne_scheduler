"""Tkinter schedule viewer with L-level and C-rate inference."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ..io.sch_parser import ScheduleDocument, parse_schedule_file
from ..engine.c_rate import FAST_CHARGE_MIN_C_RATE, STANDARD_C_RATE_PRESETS

FIXTURE_DIR = (
    Path(__file__).resolve().parents[1] / "example" / "fixtures" / "capacheck_zip"
)

COLUMNS = (
    "step_no",
    "step_type",
    "f_vref",
    "f_iref",
    "c_rate",
    "step_l",
    "f_end_v",
    "f_end_i",
    "f_end_c",
    "f_end_time",
)


class ScheduleViewerApp:
    def __init__(self, root: tk.Tk, initial_path: Path | None = None) -> None:
        self.root = root
        self.root.title("PNE Scheduler — Schedule Viewer")
        self.root.geometry("1280x760")
        self._document: ScheduleDocument | None = None

        self._build_ui()
        if initial_path is not None and initial_path.exists():
            self.load_file(initial_path)
        elif FIXTURE_DIR.exists():
            sch_files = sorted(FIXTURE_DIR.glob("*.sch"))
            if sch_files:
                self._populate_fixture_list(sch_files)

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self.root, padding=6)
        toolbar.pack(fill=tk.X)

        ttk.Button(toolbar, text="Open .sch…", command=self._open_file).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Reload", command=self._reload).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Label(toolbar, text="Fixtures:").pack(side=tk.LEFT, padx=(16, 4))
        self.fixture_var = tk.StringVar()
        self.fixture_combo = ttk.Combobox(
            toolbar, textvariable=self.fixture_var, width=70, state="readonly"
        )
        self.fixture_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.fixture_combo.bind("<<ComboboxSelected>>", self._on_fixture_selected)

        summary = ttk.LabelFrame(self.root, text="Summary", padding=8)
        summary.pack(fill=tk.X, padx=8, pady=(0, 6))

        self.summary_text = tk.Text(summary, height=9, wrap=tk.WORD, font=("Consolas", 10))
        self.summary_text.pack(fill=tk.X)
        self.summary_text.configure(state=tk.DISABLED)

        table_frame = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        table_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(
            table_frame,
            columns=COLUMNS,
            show="headings",
            selectmode="browse",
        )
        headings = {
            "step_no": "Step",
            "step_type": "Type",
            "f_vref": "Vref (V)",
            "f_iref": "Iref (mA)",
            "c_rate": "C-rate",
            "step_l": "Step L",
            "f_end_v": "End V",
            "f_end_i": "End I",
            "f_end_c": "End C",
            "f_end_time": "End t (s)",
        }
        widths = {
            "step_no": 50,
            "step_type": 90,
            "f_vref": 90,
            "f_iref": 90,
            "c_rate": 80,
            "step_l": 70,
            "f_end_v": 80,
            "f_end_i": 80,
            "f_end_c": 80,
            "f_end_time": 80,
        }
        for col in COLUMNS:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor=tk.CENTER)

        yscroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.status_var = tk.StringVar(value="Open a .sch file to begin.")
        ttk.Label(self.root, textvariable=self.status_var, padding=6).pack(fill=tk.X)

    def _populate_fixture_list(self, paths: list[Path]) -> None:
        self._fixture_paths = paths
        labels = [p.name for p in paths]
        self.fixture_combo["values"] = labels
        if labels:
            self.fixture_combo.current(0)

    def _on_fixture_selected(self, _event: object = None) -> None:
        index = self.fixture_combo.current()
        if index < 0:
            return
        self.load_file(self._fixture_paths[index])

    def _open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open PNE schedule",
            filetypes=[("PNE schedule", "*.sch"), ("All files", "*.*")],
        )
        if path:
            self.load_file(Path(path))

    def _reload(self) -> None:
        if self._document is None:
            return
        self.load_file(self._document.path)

    def load_file(self, path: Path) -> None:
        try:
            document = parse_schedule_file(path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Load failed", str(exc))
            return

        self._document = document
        self._render_summary(document)
        self._render_table(document)
        self.status_var.set(f"Loaded {path.name} — {len(document.steps)} steps")

    def _render_summary(self, doc: ScheduleDocument) -> None:
        cls = doc.classification
        proto = doc.protocol
        geo = doc.geometry
        stack = geo.stack_level
        fp = geo.footprint
        mode = geo.cell_mode
        cap = geo.capacity

        lines = [
            f"File: {doc.path.name}",
            f"Category: {cls.category.value}"
            + (
                f" / qpeed:{cls.qpeed_variant.value}"
                if cls.qpeed_variant is not None
                else ""
            )
            + (
                f" / {cls.protocol_variant.value}"
                if cls.protocol_variant.value != "none"
                else ""
            ),
            f"SCH version: {hex(doc.sch_version) if doc.sch_version is not None else 'n/a'}"
            f"   step_size: {doc.step_size} B   offset: {doc.payload_offset}",
        ]
        if proto is not None:
            lines.append(
                f"Protocol:  {proto.protocol.value} ({proto.confidence:.0%}) — {proto.detail}"
            )
            if proto.expected_c_rates:
                lines.append(f"  expected C: {', '.join(proto.expected_c_rates)}")
        lines.extend([
            "",
            "— Cell geometry (FP → mono/multi → L → C) —",
            f"Footprint: {fp.label}  [{fp.source}, {fp.confidence:.0%}]",
            f"Cell mode: {mode.mode.value.upper()}  K={mode.reaction_cells_k}"
            f"  ({mode.detail}, {mode.confidence:.0%})",
            f"L-level:   {stack.primary.label}  ({stack.primary.confidence:.0%})",
            f"Q_nom:     {cap.nominal_capacity_mAh:.0f} mAh   I_1C≈{cap.expected_1c_current_mA:.0f} mA",
            f"  {cap.detail}",
        ])
        if stack.filename_guess:
            lines.append(f"  L filename: {stack.filename_guess.detail}")
        if stack.fvref_guess:
            lines.append(f"  L fVref:    {stack.fvref_guess.detail}")
        if stack.current_guess:
            lines.append(f"  L current:  {stack.current_guess.detail}")

        fast_steps = [s for s in doc.steps if s.is_fast_charge and s.f_iref > 0]
        if fast_steps:
            labels = sorted({s.c_rate_label for s in fast_steps})
            lines.append("")
            lines.append(
                f"Fast-charge steps (>{FAST_CHARGE_MIN_C_RATE}C): "
                f"{len(fast_steps)} step(s) — {', '.join(labels)}"
            )
            if cls.category.value not in ("qpeed", "cycle_life"):
                lines.append(
                    "  hint: >2.5C is typical for QPEED / QC cycle experiments"
                )

        preset_labels = ", ".join(p.label for p in STANDARD_C_RATE_PRESETS)
        lines.append("")
        lines.append(f"Standard C-rates: {preset_labels}")

        self.summary_text.configure(state=tk.NORMAL)
        self.summary_text.delete("1.0", tk.END)
        self.summary_text.insert(tk.END, "\n".join(lines))
        self.summary_text.configure(state=tk.DISABLED)

    def _render_table(self, doc: ScheduleDocument) -> None:
        self.tree.delete(*self.tree.get_children())
        for step in doc.steps:
            if step.c_rate_label:
                c_rate = step.c_rate_label
            elif step.c_rate is not None:
                c_rate = f"{step.c_rate:.3f}"
            else:
                c_rate = ""
            step_l = f"{step.step_l_level:.1f}" if step.step_l_level is not None else ""
            self.tree.insert(
                "",
                tk.END,
                values=(
                    step.step_no,
                    step.step_type,
                    f"{step.f_vref:.3f}" if step.f_vref else "",
                    f"{step.f_iref:.1f}" if step.f_iref else "",
                    c_rate,
                    step_l,
                    f"{step.f_end_v:.3f}" if step.f_end_v else "",
                    f"{step.f_end_i:.3f}" if step.f_end_i else "",
                    f"{step.f_end_c:.2f}" if step.f_end_c else "",
                    f"{step.f_end_time:.0f}" if step.f_end_time else "",
                ),
            )


def launch_schedule_viewer(initial_path: str | Path | None = None) -> None:
    root = tk.Tk()
    path = Path(initial_path) if initial_path is not None else None
    ScheduleViewerApp(root, initial_path=path)
    root.mainloop()
