"""Offline Tk workspace. All calculations use the shared application services."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import queue
import signal
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from .native_controller import NativeController
from .tk_widgets import ScrollFrame


class WorkspaceApp(ttk.Frame):
    def __init__(self, root, controller=None):
        super().__init__(root)
        self.root = root
        self.controller = controller or NativeController()
        self.busy = False
        self._closed = False
        self.exit_requested = threading.Event()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pne-native")
        self._results = queue.Queue()
        self._poll_id = None
        self._setup_signature = None
        self._setup_entries = {}
        self.panels = []
        self._style()
        root.title("PNE Scheduler · 오프라인")
        root.geometry("1280x840")
        root.minsize(960, 640)
        self.pack(fill="both", expand=True)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        top = ttk.Frame(self, padding=(16, 10))
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="PNE Scheduler", style="Title.TLabel").pack(side="left")
        ttk.Label(top, text="  오프라인 작업실 · 웹 연결 불필요", style="Muted.TLabel").pack(side="left")
        self.toolbar = []
        for label, callback in (("새 프로젝트", self.new_project), ("열기", self.open_project),
                                ("저장", self.save_project), ("되돌리기", self.undo), ("다시 실행", self.redo)):
            button = ttk.Button(top, text=label, command=callback)
            button.pack(side="left", padx=(7, 0))
            self.toolbar.append(button)
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=12)
        self.setup = ScrollFrame(self.notebook)
        self.notebook.add(self.setup, text="  셀 · 장비  ")
        from .tk_protocol import ProtocolPanel
        from .tk_resources import ExportPanel, ImportPanel, LibraryPanel
        from .tk_storage import StoragePanel
        for cls, title in ((ProtocolPanel, "프로토콜"), (LibraryPanel, "내 블록"),
                           (ExportPanel, "파일 · 배치 생성"), (ImportPanel, "기존 SCH"), (StoragePanel, "고온저장")):
            panel = cls(self.notebook, self)
            self.panels.append(panel)
            self.notebook.add(panel, text=f"  {title}  ")
        self.notebook.bind("<<NotebookTabChanged>>", self._tab_changed)
        bottom = ttk.Frame(self, padding=(16, 8))
        bottom.grid(row=2, column=0, sticky="ew")
        self.status_var = tk.StringVar(value="준비됨 · 숫자 입력 후 Enter 또는 적용 버튼을 누르세요.")
        ttk.Label(bottom, textvariable=self.status_var, wraplength=960).pack(side="left", fill="x", expand=True)
        self.progress = ttk.Progressbar(bottom, mode="indeterminate", length=110)
        self.progress.pack(side="right")
        self._menu()
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()
        self._poll_id = self.after(40, self._poll)

    @property
    def revision(self):
        return self.controller.revision

    @property
    def project(self):
        return self.controller.project

    @property
    def selected(self):
        return self.controller.selected

    def _style(self):
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", font=("TkDefaultFont", 11), background="#f5f7f6", foreground="#243c34")
        style.configure("TButton", padding=(9, 6))
        style.configure("TEntry", padding=5, fieldbackground="#ffffff")
        style.configure("TCombobox", padding=5)
        style.configure("TNotebook.Tab", padding=(8, 8))
        style.configure("Title.TLabel", font=("TkDefaultFont", 17, "bold"))
        style.configure("Heading.TLabel", font=("TkDefaultFont", 14, "bold"))
        style.configure("Muted.TLabel", foreground="#61736b")
        style.configure("Treeview", rowheight=28, fieldbackground="#ffffff")
        style.map("TButton", background=[("active", "#dcebe2")])

    def _menu(self):
        bar = tk.Menu(self.root)
        file = tk.Menu(bar, tearoff=False)
        for name, command in (("새 프로젝트", self.new_project), ("열기…", self.open_project),
                              ("저장", self.save_project), ("다른 이름으로 저장…", lambda: self.save_project(save_as=True)),
                              ("자동 복구 기록…", self.show_recovery), ("종료", self.close)):
            file.add_command(label=name, command=command)
        bar.add_cascade(label="파일", menu=file)
        self.root.configure(menu=bar)
        modifier = "Command" if self.root.tk.call("tk", "windowingsystem") == "aqua" else "Control"
        for key, callback in (("s", self.save_project), ("o", self.open_project), ("z", self.undo), ("y", self.redo)):
            self.root.bind(f"<{modifier}-{key}>", lambda e, fn=callback: (fn(), "break")[1])

    def status(self, text):
        self.status_var.set(str(text))

    def _set_busy(self, value):
        self.busy = value
        for button in self.toolbar:
            button.state(["disabled"] if value else ["!disabled"])
        for entry in self._setup_entries.values():
            entry.state(["disabled"] if value else ["!disabled"])
        for panel in self.panels:
            panel.set_busy(value)
        if value:
            self.progress.start(12)
        else:
            self.progress.stop()
            self.toolbar[3].state(["!disabled"] if self.controller.document.can_undo else ["disabled"])
            self.toolbar[4].state(["!disabled"] if self.controller.document.can_redo else ["disabled"])

    def submit(self, work: Callable, on_success=None, message=""):
        if self.busy or self._closed:
            return False
        self._set_busy(True)
        self.status(message or "처리 중…")
        future = self._pool.submit(work)
        # Future callbacks run in the worker: only Queue is touched here.
        future.add_done_callback(lambda result: self._results.put((result, on_success, message)))
        return True

    def _poll(self):
        if self._closed:
            return
        try:
            future, callback, message = self._results.get_nowait()
        except queue.Empty:
            pass
        else:
            self._set_busy(False)
            try:
                result = future.result()
                if callback:
                    callback(result)
                else:
                    self.refresh()
                if not self.busy:
                    self.status(self.controller.notice or (message + " · 완료" if message else "완료"))
            except Exception as exc:
                self.status(f"처리하지 못했습니다: {exc}")
                messagebox.showerror("작업 확인", str(exc), parent=self.root)
        if not self._closed:
            if self.exit_requested.is_set() and not self.busy:
                self.exit_requested.clear()
                self.close()
                if self._closed:
                    return
            self._poll_id = self.after(40, self._poll)

    def perform(self, action, args=None):
        return self.submit(lambda: self.controller.edit(action, args), message="변경 적용")

    def select(self, module_id):
        return self.submit(lambda: self.controller.select(module_id))

    def undo(self):
        return self.submit(self.controller.undo, message="되돌리기")

    def redo(self):
        return self.submit(self.controller.redo, message="다시 실행")

    def refresh(self):
        self.root.title(f"{self.controller.document.title} — PNE Scheduler · 오프라인")
        self._render_setup()
        for panel in self.panels:
            panel.refresh()
        self._set_busy(self.busy)

    def _render_setup(self):
        fields = self.controller.views.get("setupFields", [])
        signature = repr(fields)
        if signature == self._setup_signature:
            return
        self._setup_signature = signature
        for child in self.setup.body.winfo_children():
            child.destroy()
        self._setup_entries = {}
        body = self.setup.body
        body.columnconfigure(0, weight=1)
        ttk.Label(body, text="실험의 기준을 먼저 정하세요", style="Heading.TLabel").grid(row=0, column=0, sticky="w", padx=24, pady=(20, 5))
        ttk.Label(body, text="웹과 같은 .schproj 파일 · 수동 입력 기준용량으로 모든 C-rate 전류를 계산합니다.", wraplength=800).grid(row=1, column=0, sticky="w", padx=24, pady=(0, 15))
        for row, field in enumerate(fields, 2):
            frame = ttk.Frame(body, padding=(24, 7))
            frame.grid(row=row, column=0, sticky="ew")
            frame.columnconfigure(1, weight=1)
            ttk.Label(frame, text=field["label"], width=23).grid(row=0, column=0, sticky="w")
            if field.get("readOnly"):
                ttk.Label(frame, text=field["value"]).grid(row=0, column=1, sticky="w")
                continue
            var = tk.StringVar(value=field["value"])
            choices = field.get("choices")
            entry = (ttk.Combobox(frame, textvariable=var, values=choices, state="readonly") if choices else ttk.Entry(frame, textvariable=var))
            entry.grid(row=0, column=1, sticky="ew")
            self._setup_entries[field["key"]] = entry
            def commit(e=None, key=field["key"], v=var):
                return self._apply_setup(key, v.get())
            entry.bind("<Return>", commit)
            ttk.Button(frame, text="적용", command=commit).grid(row=0, column=2, padx=8)
            detail = field.get("issue") or field.get("detail", "")
            ttk.Label(frame, text=detail, wraplength=650, style="Muted.TLabel").grid(row=1, column=1, sticky="w", pady=(3, 0))

    def _apply_setup(self, key, value):
        if key == "name":
            return self.perform("setProjectName", {"name": value})
        if key == "equipment_unit":
            return self.perform("setEquipmentUnit", {"unit": value})
        return self.perform("setCellValue", {"key": key, "text": value})

    def _tab_changed(self, _event=None):
        # Disk-backed panels refresh on entry, never in a redraw loop.
        if self.busy:
            return
        selected = self.notebook.select()
        for panel in self.panels:
            if str(panel) == selected:
                if hasattr(panel, "_load_library"):
                    panel._load_library()
                elif hasattr(panel, "_request_refresh"):
                    panel._request_refresh(False)

    def _may_replace(self):
        if self.busy:
            return False
        if not self.controller.document.dirty:
            return True
        return messagebox.askyesno("프로젝트 전환", "현재 수정은 자동 복구 기록에 남습니다. 다른 프로젝트로 전환할까요?\n원본 파일에 저장하려면 취소 후 저장을 누르세요.", parent=self.root)

    def new_project(self):
        if self._may_replace():
            self.submit(self.controller.new, message="새 프로젝트")

    def open_project(self):
        if not self._may_replace():
            return
        path = filedialog.askopenfilename(parent=self.root, title="웹 또는 Tk 프로젝트 열기", filetypes=[("PNE 프로젝트", "*.schproj")])
        if path:
            self.submit(lambda: self.controller.open(Path(path)), message="프로젝트 열기")

    def save_project(self, save_as=False, after=None):
        if self.busy:
            return
        path = None if not save_as else ""
        if save_as or self.controller.document.path is None:
            path = filedialog.asksaveasfilename(parent=self.root, title="프로젝트 저장", defaultextension=".schproj", filetypes=[("PNE 프로젝트", "*.schproj")])
            if not path:
                return
        def saved(_result):
            self.refresh()
            if after:
                after()
        self.submit(lambda: self.controller.save(Path(path) if path else None), saved, "프로젝트 저장")

    def show_recovery(self):
        if self.busy:
            return
        def loaded(snapshots):
            if not snapshots:
                messagebox.showinfo("자동 복구", "복구할 기록이 없습니다.", parent=self.root)
                return
            window = tk.Toplevel(self.root)
            window.title("자동 복구 기록")
            window.geometry("800x360")
            listing = tk.Listbox(window, exportselection=False)
            listing.pack(fill="both", expand=True, padx=12, pady=12)
            for snapshot in snapshots:
                listing.insert("end", snapshot.describe())
            def restore():
                indices = listing.curselection()
                if indices and self._may_replace():
                    snapshot = snapshots[indices[0]]
                    window.destroy()
                    self.submit(lambda: self.controller.recover(snapshot), message="자동 복구")
            ttk.Button(window, text="선택한 기록 복구", command=restore).pack(pady=10)
        self.submit(self.controller.recoveries, loaded)

    def show_text(self, title, text):
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry("900x620")
        box = tk.Text(window, wrap="word", padx=16, pady=14)
        bar = ttk.Scrollbar(window, command=box.yview)
        box.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        box.pack(fill="both", expand=True)
        box.insert("1.0", str(text))
        box.configure(state="disabled")
        return window

    def close(self):
        if self.busy:
            self.status("진행 중인 작업이 끝난 후 종료해 주세요.")
            return
        if self.controller.document.dirty:
            answer = messagebox.askyesnocancel("프로젝트 저장", "수정한 프로젝트를 저장하고 종료할까요?\n‘아니요’를 선택해도 자동 복구 기록은 남습니다.", parent=self.root)
            if answer is None:
                return
            if answer:
                self.save_project(after=self._shutdown)
                return
            self.submit(self.controller.preserve_unsaved, lambda _: self._shutdown(), "자동 복구 저장 후 종료")
            return
        self._shutdown()

    def _shutdown(self):
        self._closed = True
        if self._poll_id:
            self.after_cancel(self._poll_id)
        self._pool.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


def run_event_loop(app):
    # Raising KeyboardInterrupt through Tcl's mainloop can abort some Tk9
    # runtimes. Signals only set a flag; the Tk thread performs normal closing.
    previous = signal.signal(signal.SIGINT, lambda *_: app.exit_requested.set())
    try:
        app.root.mainloop()
    finally:
        signal.signal(signal.SIGINT, previous)


def launch_workspace(initial_path=None, *, data_dir=None):
    try:
        controller = NativeController(Path(initial_path) if initial_path else None,
                                      data_dir=Path(data_dir) if data_dir else None)
        root = tk.Tk()
    except (OSError, ValueError, tk.TclError) as exc:
        import sys
        print(f"작업실을 열 수 없습니다: {exc}\nPython과 Tcl/Tk가 설치된 데스크톱 환경에서 실행하세요.", file=sys.stderr)
        return 2
    app = WorkspaceApp(root, controller)
    run_event_loop(app)
    return 0
