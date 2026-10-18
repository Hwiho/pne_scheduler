"""Data-care forms using the same operations as the web, without HTTP."""
from __future__ import annotations

import json
from tkinter import BooleanVar, StringVar, filedialog, ttk

from .tk_widgets import ScrollFrame


class DataSafetyPanel(ScrollFrame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._status = {}
        self._plan = None
        self._inspection = None
        self._revision = app.revision
        self._busy = False
        self._timer = None
        self._managed = []
        self.include_current = BooleanVar(value=True)
        self.extra_paths = StringVar()
        self.output_path = StringVar()
        self.archive_path = StringVar()
        self.destination = StringVar()
        self.external_stopped = BooleanVar(value=False)
        self.resume_confirmed = BooleanVar(value=False)
        self.status_text = StringVar(value="데이터 관리 탭에서 상태를 확인하세요.")
        self.result_text = StringVar()
        self.backup_text = StringVar(value="백업 내용을 먼저 확인하세요.")
        self.restore_text = StringVar(value="복원할 ZIP을 먼저 검사하세요.")
        self.body.columnconfigure(0, weight=1)
        ttk.Label(self.body, text="데이터 관리 · 원본을 보존하는 백업과 복원", style="Heading.TLabel").grid(row=0, column=0, sticky="w", padx=16, pady=14)
        runner = self._section("알림 실행기", 1)
        ttk.Label(runner, textvariable=self.status_text, wraplength=820).grid(row=0, column=0, columnspan=3, sticky="ew")
        self.start_button = self._button(runner, "Windows 알림 시작", lambda: self._run("companionStart"), 1, 0, lambda: self._companion().get("canStart"))
        self.stop_button = self._button(runner, "안전 종료 요청", self.stop, 1, 1, lambda: self._companion().get("canStop") and self._companion().get("state") != "stopping")
        self._button(runner, "상태 새로고침", self._request_refresh, 1, 2)
        ttk.Label(runner, text="창을 닫아도 실행기는 계속 동작합니다. 안전 종료는 잠금 해제까지 확인합니다. 실제 알림 표시·사용자 확인은 전송 기록과 다릅니다.", wraplength=820).grid(row=2, column=0, columnspan=3, sticky="w", pady=8)
        self.resume_check = ttk.Checkbutton(runner, text="복원된 일정·지연 알림을 검토했습니다", variable=self.resume_confirmed, command=self._states)
        self.resume_check.grid(row=3, column=0, columnspan=2, sticky="w")
        self._managed.append((self.resume_check, lambda: self._companion().get("restorePaused")))
        self.resume_button = self._button(runner, "기존 알림 설정 재개", lambda: self._run("resumeNotifications", {"confirmed": bool(self.resume_confirmed.get())}), 3, 2,
                                         lambda: self._companion().get("restorePaused") and self.resume_confirmed.get())

        backup = self._section("01 · 검증 백업", 2)
        ttk.Label(backup, text="보관 DB·알림 확인 이력·방법 라이브러리·자동 복구본을 포함합니다. 알림 실행기는 먼저 안전 종료하세요.", wraplength=820).grid(row=0, column=0, columnspan=3, sticky="w", pady=5)
        check = ttk.Checkbutton(backup, text="현재 프로젝트 포함 (미저장 변경 포함)", variable=self.include_current)
        check.grid(row=1, column=0, columnspan=3, sticky="w")
        self._managed.append((check, lambda: True))
        self._entry(backup, "추가 프로젝트 경로 (선택 버튼으로 여러 파일 지정)", self.extra_paths, 2)
        self._button(backup, "프로젝트 선택…", self._choose_projects, 3, 1)
        self.preview_button = self._button(backup, "백업 내용 미리보기", self.preview, 3, 0)
        ttk.Label(backup, textvariable=self.backup_text, wraplength=820).grid(row=4, column=0, columnspan=3, sticky="w", pady=8)
        self._entry(backup, "새 백업 ZIP 절대 경로", self.output_path, 5)
        self._button(backup, "저장 위치…", self._choose_output, 6, 1)
        check = ttk.Checkbutton(backup, text="다른 구버전 앱·외부 편집기의 데이터 쓰기를 중지했습니다", variable=self.external_stopped, command=self._states)
        check.grid(row=7, column=0, columnspan=3, sticky="w")
        self._managed.append((check, lambda: True))
        self.create_button = self._button(backup, "검증 백업 저장", self.create_backup, 8, 0,
                                          lambda: self._plan is not None and bool(self.output_path.get().strip()) and self.external_stopped.get())
        ttk.Label(backup, text="선택하지 않은 외부 원자료·SCH 출력·웹 초안·로그·설정/키 파일은 제외합니다. ZIP은 암호화되지 않으며 외부 전송은 없습니다.", wraplength=820).grid(row=9, column=0, columnspan=3, sticky="w", pady=8)

        restore = self._section("02 · 새 폴더 복원", 3)
        self._entry(restore, "백업 ZIP 절대 경로", self.archive_path, 0)
        self._button(restore, "백업 선택…", self._choose_archive, 1, 1)
        self.inspect_button = self._button(restore, "복원 전 검사", self.inspect, 1, 0, lambda: bool(self.archive_path.get().strip()))
        ttk.Label(restore, textvariable=self.restore_text, wraplength=820).grid(row=2, column=0, columnspan=3, sticky="w", pady=8)
        self._entry(restore, "새 복원 폴더 절대 경로 (아직 없는 폴더)", self.destination, 3)
        self.restore_button = self._button(restore, "원본 보존 · 새 폴더 복원", self.restore, 4, 0,
                                           lambda: self._inspection is not None and bool(self.destination.get().strip()))
        ttk.Label(restore, text="복원 후 새 폴더를 --data-dir로 지정해 다시 실행하세요. 현재 데이터는 그대로이며 복원된 알림은 검토 후 별도로 재개합니다.", wraplength=820).grid(row=5, column=0, columnspan=3, sticky="w", pady=8)
        ttk.Label(self.body, textvariable=self.result_text, wraplength=850).grid(row=4, column=0, sticky="ew", padx=16, pady=14)
        for variable in (self.include_current, self.extra_paths):
            variable.trace_add("write", lambda *_: self._invalidate_backup())
        self.archive_path.trace_add("write", lambda *_: self._invalidate_restore())
        for variable in (self.output_path, self.destination):
            variable.trace_add("write", lambda *_: self._states())
        self._states()
        self._timer = self.after(5000, self._tick)

    def _section(self, title, row):
        frame = ttk.LabelFrame(self.body, text=title, padding=12)
        frame.grid(row=row, column=0, sticky="ew", padx=16, pady=7)
        for column in range(3):
            frame.columnconfigure(column, weight=1)
        return frame

    def _button(self, parent, title, action, row, column, enabled=lambda: True):
        button = ttk.Button(parent, text=title, command=action)
        button.grid(row=row, column=column, sticky="ew", padx=(0, 6), pady=5)
        self._managed.append((button, enabled))
        return button

    def _entry(self, parent, title, variable, row):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=5)
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text=title).grid(row=0, column=0, sticky="w")
        entry = ttk.Entry(frame, textvariable=variable)
        entry.grid(row=1, column=0, sticky="ew", pady=4)
        self._managed.append((entry, lambda: True))

    def _companion(self):
        return self._status.get("companion", {})

    def _states(self):
        for widget, enabled in self._managed:
            widget.state(["!disabled"] if not self._busy and enabled() else ["disabled"])

    def set_busy(self, busy):
        self._busy = busy
        self._states()

    def refresh(self):
        if self._revision != self.app.revision:
            self._revision = self.app.revision
            self._invalidate_backup()
        self._states()

    def _invalidate_backup(self):
        self._plan = None
        self.backup_text.set("입력 변경 후 다시 미리보기 하세요.")
        self._states()

    def _invalidate_restore(self):
        self._inspection = None
        self.restore_text.set("선택한 ZIP을 다시 검사하세요.")
        self._states()

    def _run(self, action, args=None, accept=None):
        if self.app.busy:
            return
        if action != "status":
            self.result_text.set("")
        def finish(result):
            if "companion" in result:
                self._status = result
                c = result["companion"]
                self.status_text.set(f"{c['label']} · 버전 {c['version']} · 최근 확인 {c['lastHeartbeatAt'] or '없음'}\n"
                                     f"복원 알림 {'일시 정지' if c['restorePaused'] else '검토 완료/해당 없음'} · 지연 알림 {c['pendingCount']}개\n"
                                     f"DB: {result['database']}\n라이브러리: {result['library']}\n복구본: {result['recovery']}"
                                     + (f"\n마지막 오류: {c['lastError']}" if c['lastError'] else ""))
                if not c["restorePaused"]:
                    self.resume_confirmed.set(False)
            if accept:
                accept(result)
            self._states()
        self.app.submit(lambda: self.app.controller.data_action(action, args), finish,
                        message="데이터 관리", on_error=lambda exc: self.result_text.set(f"처리하지 못했습니다: {exc}"))

    def _request_refresh(self, announce=False):
        self._run("status")

    def _tick(self):
        if not self.app.busy and self.app.notebook.select() == str(self):
            self._request_refresh()
        self._timer = self.after(5000, self._tick)

    def destroy(self):
        if self._timer is not None:
            self.after_cancel(self._timer)
        super().destroy()

    def stop(self):
        self._run("companionStop", {"runId": self._companion().get("runId", "")})

    def _args(self):
        raw = self.extra_paths.get().strip()
        # A JSON list preserves commas/semicolons/spaces in selected paths.
        return {"includeCurrent": bool(self.include_current.get()), "projectPaths": json.loads(raw) if raw.startswith("[") else ([raw] if raw else [])}

    def preview(self):
        try:
            args = self._args()
        except ValueError:
            self.result_text.set("추가 프로젝트는 한 개의 절대 경로 또는 선택 버튼으로 지정하세요.")
            return
        def accept(result):
            self._plan = result
            self.backup_text.set(f"{len(result['files'])}개 파일 · {result['totalBytes'] / 1024:.1f} KiB\n" + "\n".join(f["path"] for f in result["files"]))
        self._run("backupPreview", args, accept)

    def create_backup(self):
        if not self._plan:
            return
        args = {**self._args(), "token": self._plan["token"], "outputPath": self.output_path.get(), "externalWritesStopped": bool(self.external_stopped.get())}
        def accept(result):
            self._plan = None
            self.archive_path.set(result["path"])
            self.result_text.set(f"백업 생성·검증 완료: {result['path']}\nSHA-256: {result['sha256']}")
        self._run("backupCreate", args, accept)

    def inspect(self):
        def accept(result):
            self._inspection = result
            self.restore_text.set(f"검사 통과 · {len(result['files'])}개 파일 · 보관 기록 {result['counts']['storage_records']}개\n{result['note']}\n"
                                  + "\n".join(f["path"] for f in result["files"]))
        self._run("restoreInspect", {"archivePath": self.archive_path.get()}, accept)

    def restore(self):
        if self._inspection:
            self._run("restoreApply", {"archivePath": self.archive_path.get(), "destination": self.destination.get(), "token": self._inspection["token"]}, self._restored)

    def _restored(self, result):
        self._inspection = None
        self.result_text.set(f"복원 완료: {result['path']}\n{result['note']}")

    def _choose_projects(self):
        paths = filedialog.askopenfilenames(parent=self, filetypes=[("PNE 프로젝트", "*.schproj")])
        if paths:
            self.extra_paths.set(json.dumps(list(paths), ensure_ascii=False))

    def _choose_output(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".zip", filetypes=[("백업 ZIP", "*.zip")])
        if path:
            self.output_path.set(path)

    def _choose_archive(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("백업 ZIP", "*.zip")])
        if path:
            self.archive_path.set(path)
