"""Editable native cell table, backed by the same pure operations as the web."""
from __future__ import annotations

from copy import deepcopy
import tkinter as tk
from tkinter import ttk

from ..batch import cell_table, inspect_cell_rows


class CellTable(ttk.Frame):
    def __init__(self, parent, on_change):
        super().__init__(parent)
        self.rows = []
        self.on_change = on_change
        self._loading = False
        self._enabled = True
        self._index = None
        self.columnconfigure(0, weight=1)
        self.prefix = tk.StringVar(value="A")
        self.id_var = tk.StringVar()
        self.capacity_var = tk.StringVar()
        self.notice = tk.StringVar()
        self._controls = []
        bar = ttk.Frame(self)
        bar.grid(row=0, column=0, sticky="ew")
        ttk.Label(bar, text="연번 접두어").pack(side="left")
        prefix = ttk.Entry(bar, textvariable=self.prefix, width=6)
        prefix.pack(side="left", padx=4)
        self._controls.append(prefix)
        for label, action in (("셀 추가", "add"), ("선택 복사", "duplicate"), ("선택 연번", "number"), ("선택 삭제", "remove")):
            button = ttk.Button(bar, text=label, command=lambda a=action: self.operate(a))
            button.pack(side="left", padx=2)
            self._controls.append(button)
        frame = ttk.Frame(self)
        frame.grid(row=1, column=0, sticky="ew", pady=6)
        frame.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(frame, columns=("id", "capacity", "oneC", "issue"), show="headings", height=6, selectmode="extended")
        for key, title, width in (("id", "셀 ID", 115), ("capacity", "기준용량 (mAh)", 125), ("oneC", "1C (mA)", 100), ("issue", "입력 확인", 280)):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=70)
        self.tree.grid(row=0, column=0, sticky="ew")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.tag_configure("invalid", foreground="#a32b36")
        self.tree.bind("<<TreeviewSelect>>", self._select)
        self.tree.bind("<Return>", lambda _e: self.focus_issue(self._index, "cellId"))
        self.tree.bind("<Double-1>", self._double_click)
        editor = ttk.Frame(self)
        editor.grid(row=2, column=0, sticky="ew")
        for column, (label, variable) in enumerate((("선택 셀 ID", self.id_var), ("기준용량 (mAh)", self.capacity_var))):
            editor.columnconfigure(column, weight=1)
            ttk.Label(editor, text=label).grid(row=0, column=column, sticky="w")
            entry = ttk.Entry(editor, textvariable=variable)
            entry.grid(row=1, column=column, sticky="ew", padx=(0, 6))
            self._controls.append(entry)
            if column == 0:
                self.id_entry = entry
            else:
                self.capacity_entry = entry
            variable.trace_add("write", self._edit)
        ttk.Label(self, text="행 선택 후 아래 값을 수정하세요. Ctrl/Shift로 여러 행 선택 · 전류 한도는 배치 미리보기에서 확인", wraplength=700).grid(row=3, column=0, sticky="w", pady=4)
        self.issues_frame = ttk.Frame(self)
        self.issues_frame.grid(row=4, column=0, sticky="ew")
        ttk.Label(self, text="엑셀·텍스트 추가: 셀 ID, 기준용량 두 열 (쉼표/탭)").grid(row=5, column=0, sticky="w", pady=(8, 2))
        self.paste_text = tk.Text(self, height=3, wrap="none")
        self.paste_text.grid(row=6, column=0, sticky="ew")
        self._controls.append(self.paste_text)
        paste_button = ttk.Button(self, text="표에 추가", command=lambda: self.operate("paste"))
        paste_button.grid(row=7, column=0, sticky="w", pady=4)
        self._controls.append(paste_button)
        ttk.Label(self, textvariable=self.notice, wraplength=700, foreground="#a32b36").grid(row=8, column=0, sticky="w")

    def get_rows(self):
        return deepcopy(self.rows)

    def set_rows(self, rows):
        self.rows = deepcopy(rows)
        self.tree.delete(*self.tree.get_children())
        for index in range(len(rows)):
            self.tree.insert("", "end", iid=str(index))
        self._index = None
        self._refresh_values()
        if rows:
            self.tree.selection_set("0")
            self._select()
        else:
            self._load_editor(None)
        self.on_change()

    def operate(self, action):
        if not self._enabled:
            return
        try:
            result = cell_table(self.rows, action=action, prefix=self.prefix.get(),
                                selected=[int(i) for i in self.tree.selection()],
                                text=self.paste_text.get("1.0", "end-1c"))
        except ValueError as exc:
            self.notice.set(str(exc))
            return
        self.notice.set("")
        self.set_rows(result["inputRows"])
        if action == "paste":
            self.paste_text.delete("1.0", "end")

    def _load_editor(self, index):
        self._loading = True
        self._index = index
        row = self.rows[index] if index is not None else {}
        self.id_var.set(str(row.get("cellId", "")))
        self.capacity_var.set(str(row.get("referenceCapacityMah", "")))
        self._loading = False
        self._show_issues()

    def _select(self, _event=None):
        selection = self.tree.selection()
        index = int(selection[0]) if selection else None
        if index != self._index:
            self._load_editor(index)

    def _edit(self, *_args):
        if self._loading or not self._enabled or self._index is None:
            return
        self.rows[self._index].update(cellId=self.id_var.get(), referenceCapacityMah=self.capacity_var.get())
        self._refresh_values()
        self.on_change()

    def _refresh_values(self):
        self.check = inspect_cell_rows(self.rows)
        for index, row in enumerate(self.rows):
            issues = [item["message"] for item in self.check["issues"] if item["row"] == index]
            capacity = self.check["rows"][index]["oneCmA"]
            self.tree.item(str(index), values=(row.get("cellId", ""), row.get("referenceCapacityMah", ""),
                                               f"{capacity:g}" if capacity is not None else "—", "; ".join(issues)),
                           tags=("invalid",) if issues else ())
        self._show_issues()

    def _show_issues(self):
        for widget in self.issues_frame.winfo_children():
            widget.destroy()
        for issue in getattr(self, "check", {}).get("issues", []):
            if issue["row"] != self._index or issue["row"] is None:
                continue
            text = issue["message"]
            def command(i=issue):
                self.focus_issue(i["row"], i["field"])
            if issue["field"] == "extraColumns":
                text += " · 추가 열 제거"
                command = self._remove_extra
            else:
                text += " · 바로 수정"
            button = ttk.Button(self.issues_frame, text=text, command=command)
            button.pack(anchor="w", pady=2)
            button.state(["!disabled"] if self._enabled else ["disabled"])

    def _remove_extra(self):
        if self._enabled and self._index is not None:
            row = self.rows[self._index]
            self.rows[self._index] = {"cellId": row.get("cellId", ""), "referenceCapacityMah": row.get("referenceCapacityMah", "")}
            self._refresh_values()
            self.on_change()

    def focus_issue(self, index, field):
        if index is None or not 0 <= index < len(self.rows):
            return
        self.tree.selection_set(str(index))
        self.tree.see(str(index))
        self._load_editor(index)
        entry = self.capacity_entry if field == "referenceCapacityMah" else self.id_entry
        entry.focus_set()
        entry.selection_range(0, "end")

    def _double_click(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            column = self.tree.identify_column(event.x)
            field = "referenceCapacityMah" if column == "#2" else "cellId"
            if column == "#4":
                field = next((item["field"] for item in self.check["issues"] if item["row"] == int(row)), field)
            self.focus_issue(int(row), field)

    def set_enabled(self, enabled):
        self._enabled = enabled
        for widget in self._controls:
            widget.configure(state="normal" if enabled else "disabled")
        self._show_issues()
