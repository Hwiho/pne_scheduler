"""Reusable Tk presentation widgets; numeric units never alter domain rules."""
from __future__ import annotations

import math
import re
import tkinter as tk
from tkinter import ttk


class ScrollFrame(ttk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0, background="#f5f7f6", width=240)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.bar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self.body.bind("<Configure>", self._size)
        self.canvas.bind("<Configure>", self._width)
        # A per-instance bind tag works for dynamically-created descendants and
        # does not steal wheel events from other panels or combobox popups.
        self._tag = f"Scroll_{id(self)}"
        self.bind_class(self._tag, "<MouseWheel>", self._wheel)
        self.bind_class(self._tag, "<Button-4>", lambda e: self._wheel(e, -1))
        self.bind_class(self._tag, "<Button-5>", lambda e: self._wheel(e, 1))
        self.bind("<Destroy>", self._destroy, add=True)

    def _size(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        pending = [self.body]
        while pending:
            widget = pending.pop()
            if self._tag not in widget.bindtags():
                widget.bindtags((*widget.bindtags(), self._tag))
            pending.extend(widget.winfo_children())

    def _width(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)

    def _wheel(self, event, units=None):
        if self.canvas.yview() == (0.0, 1.0):
            return None
        if units is None:
            delta = event.delta
            units = -int(delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)
        self.canvas.yview_scroll(units, "units")
        return "break"

    def _destroy(self, event):
        if event.widget is self:
            for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.unbind_class(self._tag, sequence)


def unit_choices(kind):
    if kind in {"duration_s", "duration_list"}:
        return (("초", 1), ("분", 60), ("시간", 3600), ("일", 86400))
    if kind in {"voltage_v", "voltage_list"}:
        return (("V", 1), ("mV", .001))
    if kind == "current_mA":
        return (("mA", 1), ("A", 1000))
    if kind in {"fraction", "fraction_list", "soc_percent", "soc_percent_list"}:
        return (("%", .01),)
    if kind == "percent":
        return (("%", 1),)
    if kind in {"c_rate", "c_rate_list"}:
        return (("C", 1),)
    if kind == "count":
        return (("회", 1),)
    return ()


def _number(value):
    number = float(value)
    return str(int(number)) if math.isfinite(number) and number.is_integer() else repr(number)


class FieldInput(ttk.Frame):
    """Number + one unit selector; Enter or Apply commits, unit changes don't.

    Explicit apply avoids losing an unfinished field when another field is
    clicked and a background transform rebuilds the inspector. The adjacent
    button and Enter hint make the commit boundary visible.
    """
    def __init__(self, parent, field_dict, on_commit=None):
        super().__init__(parent)
        self.field = field_dict
        self.kind = field_dict.get("kind", "text")
        self.on_commit = on_commit
        self.units = unit_choices(self.kind)
        self._enabled = True
        self.columnconfigure(0, weight=1)
        self.variable = tk.StringVar()
        self.unit_variable = tk.StringVar()
        self._factor = 1.0
        self._controls = []
        choices = field_dict.get("choices") or []
        self._labels = {str(c["label"]): str(c["value"]) for c in choices}
        self._boolean = self.kind in {"bool", "boolean"}
        raw = str(field_dict.get("value", field_dict.get("text", "")))
        if self._boolean:
            self.variable.set("true" if field_dict.get("checked") else "false")
            self.entry = ttk.Checkbutton(self, variable=self.variable, onvalue="true", offvalue="false", text="사용", command=self.commit)
        elif choices:
            self.variable.set(next((k for k, v in self._labels.items() if v == raw), raw))
            self.entry = ttk.Combobox(self, textvariable=self.variable, values=tuple(self._labels), state="readonly", width=16)
        else:
            values = field_dict.get("numericValues")
            numeric = field_dict.get("numericValue")
            numbers = values if values is not None else ([numeric] if numeric is not None else [])
            if self.units:
                chosen = self.units[0]
                if self.kind.startswith("duration") and numbers and all(n > 0 for n in numbers):
                    chosen = next((unit for unit in reversed(self.units)
                                   if all(n >= unit[1] and math.isclose(n / unit[1], round(n / unit[1]), abs_tol=1e-8) for n in numbers)), chosen)
                self.unit_variable.set(chosen[0])
                self._factor = chosen[1]
            self.variable.set(", ".join(_number(n / self._factor) for n in numbers) if numbers else raw)
            self.entry = ttk.Entry(self, textvariable=self.variable, width=16)
        ttk.Label(self, text=field_dict.get("label", ""), font=("TkDefaultFont", 11, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(5, 4))
        self.entry.grid(row=1, column=0, sticky="ew")
        self.entry.bind("<Return>", self.commit)
        self._controls.append(self.entry)
        if len(self.units) > 1:
            self.unit_box = ttk.Combobox(self, textvariable=self.unit_variable, values=tuple(u[0] for u in self.units), state="readonly", width=5)
            self.unit_box.grid(row=1, column=1, padx=(5, 0))
            self.unit_box.bind("<<ComboboxSelected>>", self._change_unit)
            self._controls.append(self.unit_box)
        elif self.units:
            ttk.Label(self, text=self.units[0][0]).grid(row=1, column=1, padx=5)
        if on_commit and not self._boolean:
            self.apply_button = ttk.Button(self, text="적용", width=5, command=self.commit)
            self.apply_button.grid(row=1, column=2, padx=(5, 0))
            self._controls.append(self.apply_button)
        detail = field_dict.get("detail", "")
        if self.kind == "duration_s" and field_dict.get("numericValue") is not None:
            from ..spec.units import format_duration_ko
            if detail == format_duration_ko(field_dict["numericValue"]):
                detail = ""
        issues = field_dict.get("issues") or []
        if detail or issues:
            ttk.Label(self, text="\n".join([str(detail), *map(str, issues)]).strip(), wraplength=350, style="Muted.TLabel").grid(row=2, column=0, columnspan=3, sticky="w", pady=(3, 2))
        help_text = "\n".join(str(field_dict.get(k, "")) for k in ("help", "basis", "affects", "range") if field_dict.get(k))
        if help_text:
            self.help_label = ttk.Label(self, text=help_text, wraplength=350, style="Muted.TLabel")
            self.help_button = ttk.Button(self, text="입력 도움말 ▸", command=self._toggle_help)
            self.help_button.grid(row=3, column=0, columnspan=3, sticky="w", pady=(0, 5))
        self.bind("<Configure>", self._wrap)

    def _wrap(self, event):
        if event.width <= 1:
            return
        width = max(80, event.width - 8)
        for widget in self.winfo_children():
            if isinstance(widget, ttk.Label) and int(widget.cget("wraplength") or 0) != width:
                widget.configure(wraplength=width)

    def _toggle_help(self):
        if self.help_label.winfo_manager():
            self.help_label.grid_remove()
            self.help_button.configure(text="입력 도움말 ▸")
        else:
            self.help_label.grid(row=4, column=0, columnspan=3, sticky="w", pady=(0, 5))
            self.help_button.configure(text="입력 도움말 ▾")

    def _parts(self):
        text = self.variable.get().strip()
        return [p.strip() for p in re.split(r"[,;\n]+", text)] if self.kind.endswith("_list") or self.kind == "duration_list" else [text]

    def _change_unit(self, _event=None):
        new = dict(self.units)[self.unit_variable.get()]
        try:
            values = [float(p) for p in self._parts()]
            if not all(math.isfinite(n) for n in values):
                raise ValueError("finite number required")
        except ValueError:
            self.unit_variable.set(next(label for label, factor in self.units if factor == self._factor))
            self.bell()
            return
        self.variable.set(", ".join(_number(n * self._factor / new) for n in values))
        self._factor = new

    def get(self):
        raw = self.variable.get().strip()
        if self._labels:
            return self._labels.get(raw, raw)
        if not raw or not self.units:
            return raw
        result = []
        for part in self._parts():
            if self.kind in {"fraction", "fraction_list", "soc_percent", "soc_percent_list", "percent"}:
                result.append(part if part.endswith("%") else part + "%")
            elif self.kind in {"c_rate", "c_rate_list"}:
                result.append("C/" + part[2:] if part.startswith("1/") else part)
            else:
                try:
                    result.append(_number(float(part) * self._factor))
                except ValueError:
                    result.append(part)  # explicit units still use the shared parser
        return ", ".join(result)

    def draft(self):
        return {"text": self.variable.get(), "unit": self.unit_variable.get(),
                "source": self.field.get("value", self.field.get("text", ""))}

    def restore_draft(self, draft):
        # A different committed value (including Undo) must not be hidden by an
        # older draft. Unit selection is presentation state, not project state.
        if draft.get("source") != self.field.get("value", self.field.get("text", "")):
            return
        unit = draft.get("unit")
        if unit in dict(self.units):
            self.unit_variable.set(unit)
            self._factor = dict(self.units)[unit]
        self.variable.set(draft["text"])

    def commit(self, _event=None):
        if self._enabled and self.on_commit:
            self.on_commit(self.get())
        return "break"

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        for widget in self._controls:
            state = "disabled" if not enabled else "readonly" if isinstance(widget, ttk.Combobox) else "normal"
            widget.configure(state=state)
