"""Native Tk high-temperature storage tracker.

This panel intentionally talks to :class:`StorageStore` directly.  It shares
the durable SQLite records with the web workspace and Windows companion, but
does not need Flask, HTTP, Node, or a browser.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tkinter import BooleanVar, StringVar, messagebox, ttk
from typing import Any, Callable

from .tk_widgets import ScrollFrame


FILTERS = {
    "current": "현재 목록",
    "active": "진행 중",
    "attention": "확인 필요",
    "completed": "완료",
    "archived": "보관함",
    "all": "전체 · 보관함 포함",
}


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _local_text(value: str | None) -> str:
    parsed = _parse_timestamp(value)
    if parsed is None:
        return "기록 없음"
    return parsed.astimezone().strftime("%Y-%m-%d %H:%M")


def _local_input(moment: datetime | None = None) -> str:
    current = (moment or datetime.now().astimezone()).astimezone()
    return current.strftime("%Y-%m-%d %H:%M")


def _duration(seconds: float) -> str:
    minutes = max(0, int(seconds // 60))
    days, remainder = divmod(minutes, 1440)
    hours, mins = divmod(remainder, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}일")
    if hours:
        parts.append(f"{hours}시간")
    if mins or not parts:
        parts.append(f"{mins}분")
    return " ".join(parts)


def _needs_attention(record: dict[str, Any], now: datetime) -> bool:
    if record.get("archivedAt") or record.get("completedAt"):
        return False
    for alert in record.get("alerts", []):
        due = _parse_timestamp(alert.get("snoozedUntil") or alert.get("dueAt"))
        if not alert.get("acknowledgedAt") and due is not None and due <= now:
            return True
    return False


class StoragePanel(ttk.Frame):
    """Durable local storage records with web-equivalent lifecycle actions."""

    def __init__(self, parent: Any, app: Any):
        super().__init__(parent, padding=8)
        self.app = app
        self._records: list[dict[str, Any]] = []
        self._companion: dict[str, Any] = {"active": False, "lastHeartbeatAt": None}
        self._loaded = False
        self._busy = False
        self._timer_id: str | None = None
        self._managed: list[tuple[Any, Callable[[], bool]]] = []

        self.sample_var = StringVar()
        self.temperature_var = StringVar(value="45")
        self.started_var = StringVar(value=_local_input())
        self.days_var = StringVar(value="30")
        self.checkpoints_var = StringVar()
        self.notify_var = BooleanVar(value=False)
        self.query_var = StringVar()
        self.filter_var = StringVar(value=FILTERS["current"])
        self.summary_var = StringVar(value="로컬 기록을 불러오는 중입니다.")
        self.companion_var = StringVar(value="Windows 알림 실행기 상태 확인 중")

        self._build()
        self.query_var.trace_add("write", lambda *_: self._render_records())
        self.filter_var.trace_add("write", lambda *_: self._render_records())
        self.after_idle(lambda: self._request_refresh(False))
        self._schedule_timer()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        form = ttk.LabelFrame(self, text="고온저장 기록 추가", padding=8)
        form.grid(row=0, column=0, sticky="ew")
        for column in range(6):
            form.columnconfigure(column, weight=1 if column in (0, 2, 4) else 0)

        ttk.Label(form, text="시료명").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.sample_var, width=20).grid(
            row=1, column=0, padx=(0, 8), sticky="ew"
        )
        ttk.Label(form, text="온도 (°C)").grid(row=0, column=1, sticky="w")
        ttk.Entry(form, textvariable=self.temperature_var, width=9).grid(
            row=1, column=1, padx=(0, 8), sticky="ew"
        )
        ttk.Label(form, text="시작 시각 (현지 시간)").grid(row=0, column=2, sticky="w")
        ttk.Entry(form, textvariable=self.started_var, width=18).grid(
            row=1, column=2, padx=(0, 8), sticky="ew"
        )
        ttk.Label(form, text="목표 일수").grid(row=0, column=3, sticky="w")
        ttk.Entry(form, textvariable=self.days_var, width=9).grid(
            row=1, column=3, padx=(0, 8), sticky="ew"
        )
        ttk.Label(form, text="중간 확인일 (쉼표 구분)").grid(row=0, column=4, sticky="w")
        ttk.Entry(form, textvariable=self.checkpoints_var, width=18).grid(
            row=1, column=4, padx=(0, 8), sticky="ew"
        )
        add_button = ttk.Button(form, text="기록 추가", command=self._add_record)
        add_button.grid(row=1, column=5, sticky="ew")
        self._manage(add_button)
        notify = ttk.Checkbutton(
            form,
            text="중간 확인일과 최종 목표일에 Windows 알림 받기 (실행기 필요)",
            variable=self.notify_var,
        )
        notify.grid(row=2, column=0, columnspan=6, pady=(7, 0), sticky="w")

        toolbar = ttk.Frame(self, padding=(0, 8, 0, 6))
        toolbar.grid(row=1, column=0, sticky="ew")
        toolbar.columnconfigure(1, weight=1)
        ttk.Label(toolbar, text="검색").grid(row=0, column=0, padx=(0, 5))
        ttk.Entry(toolbar, textvariable=self.query_var, width=24).grid(
            row=0, column=1, padx=(0, 8), sticky="ew"
        )
        ttk.Label(toolbar, text="상태").grid(row=0, column=2, padx=(0, 5))
        self.filter_box = ttk.Combobox(
            toolbar,
            textvariable=self.filter_var,
            values=list(FILTERS.values()),
            state="readonly",
            width=12,
        )
        self.filter_box.grid(row=0, column=3, padx=(0, 8))
        refresh_button = ttk.Button(toolbar, text="목록 새로고침", command=self._request_refresh)
        refresh_button.grid(row=0, column=4, padx=(0, 8))
        self._manage(refresh_button)
        if sys.platform == "win32":
            launch = ttk.Button(toolbar, text="Windows 알림 실행기 시작", command=self._launch_companion)
            launch.grid(row=0, column=5)
            self._manage(launch)

        content = ttk.Panedwindow(self, orient="vertical")
        content.grid(row=2, column=0, sticky="nsew")

        listing = ttk.Frame(content)
        listing.columnconfigure(0, weight=1)
        listing.rowconfigure(1, weight=1)
        ttk.Label(listing, textvariable=self.summary_var).grid(row=0, column=0, sticky="w")
        columns = ("sample", "state", "elapsed", "temp", "due", "notify")
        self.tree = ttk.Treeview(listing, columns=columns, show="headings", height=7)
        headings = {
            "sample": "시료명",
            "state": "상태",
            "elapsed": "경과",
            "temp": "온도",
            "due": "목표 시각",
            "notify": "알림",
        }
        widths = {"sample": 180, "state": 75, "elapsed": 105, "temp": 65, "due": 135, "notify": 120}
        for key in columns:
            self.tree.heading(key, text=headings[key])
            self.tree.column(key, width=widths[key], minwidth=55, stretch=key in ("sample", "notify"))
        self.tree.grid(row=1, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(listing, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)
        content.add(listing, weight=1)

        detail_box = ttk.Frame(content)
        detail_box.columnconfigure(0, weight=1)
        detail_box.rowconfigure(1, weight=1)
        ttk.Label(detail_box, textvariable=self.companion_var).grid(row=0, column=0, sticky="ew", pady=(4, 4))
        self.details = ScrollFrame(detail_box)
        self.details.grid(row=1, column=0, sticky="nsew")
        self.details.body.columnconfigure(0, weight=1)
        content.add(detail_box, weight=2)

    def _manage(self, widget: Any, enabled: Callable[[], bool] | None = None) -> Any:
        self._managed.append((widget, enabled or (lambda: True)))
        return widget

    def _apply_busy_state(self) -> None:
        alive: list[tuple[Any, Callable[[], bool]]] = []
        for widget, enabled in self._managed:
            try:
                widget.configure(state="normal" if not self._busy and enabled() else "disabled")
                alive.append((widget, enabled))
            except Exception:
                pass
        self._managed = alive

    def set_busy(self, busy: bool) -> None:
        self._busy = bool(busy)
        self._apply_busy_state()

    def refresh(self) -> None:
        """Redraw cached records without starting background work.

        Workspace-wide edits call every panel's refresh method.  Keeping this
        method render-only avoids resetting search/filter state and prevents a
        refresh-submit-refresh loop.
        """
        self._render_records()

    def destroy(self) -> None:
        if self._timer_id is not None:
            try:
                self.after_cancel(self._timer_id)
            except Exception:
                pass
            self._timer_id = None
        super().destroy()

    def _schedule_timer(self) -> None:
        self._timer_id = self.after(60_000, self._timer_refresh)

    def _timer_refresh(self) -> None:
        self._timer_id = None
        try:
            if self.winfo_exists() and not self.app.busy:
                self._request_refresh(False)
        finally:
            if self.winfo_exists():
                self._schedule_timer()

    def _snapshot(self) -> dict[str, Any]:
        store = self.app.controller.storage
        return {
            "records": store.list_records(include_archived=True),
            "companion": store.companion_status(),
        }

    def _request_refresh(self, announce: bool = True) -> None:
        if self.app.busy:
            return
        message = "보관 기록을 새로고침하는 중입니다." if announce else ""
        self.app.submit(self._snapshot, self._accept_snapshot, message=message)

    def _accept_snapshot(self, result: dict[str, Any]) -> None:
        self._records = list(result.get("records", []))
        self._companion = dict(result.get("companion", {}))
        self._loaded = True
        self._render_records()

    def _filter_key(self) -> str:
        selected = self.filter_var.get()
        return next((key for key, label in FILTERS.items() if label == selected), "current")

    def _visible_records(self, now: datetime) -> list[dict[str, Any]]:
        needle = self.query_var.get().strip().casefold()
        filter_key = self._filter_key()
        visible: list[dict[str, Any]] = []
        for record in self._records:
            if needle and needle not in f"{record.get('sample', '')} {record.get('id', '')}".casefold():
                continue
            archived = bool(record.get("archivedAt"))
            completed = bool(record.get("completedAt"))
            if filter_key == "archived" and not archived:
                continue
            if filter_key not in ("all", "archived") and archived:
                continue
            if filter_key == "active" and completed:
                continue
            if filter_key == "completed" and not completed:
                continue
            if filter_key == "attention" and not _needs_attention(record, now):
                continue
            visible.append(record)
        return visible

    def _render_records(self) -> None:
        if not hasattr(self, "tree"):
            return
        selected = self.tree.selection()[0] if self.tree.selection() else None
        now = datetime.now(timezone.utc)
        visible = self._visible_records(now)
        self.tree.delete(*self.tree.get_children())
        for record in visible:
            started = _parse_timestamp(record.get("startedAt")) or now
            stopped = _parse_timestamp(record.get("completedAt")) or now
            due = _parse_timestamp(record.get("dueAt")) or started
            archived = bool(record.get("archivedAt"))
            completed = bool(record.get("completedAt"))
            state = "보관함" if archived else "완료" if completed else "목표 도달" if now >= due else "보관 중"
            if archived:
                notify = "보관함 · 중지"
            elif completed:
                notify = "완료 · 중지"
            else:
                notify = "알림 켜짐" if record.get("notifyEnabled") else "알림 꺼짐"
            record_id = str(record["id"])
            self.tree.insert("", "end", iid=record_id, values=(
                record.get("sample", ""), state, _duration((stopped - started).total_seconds()),
                f"{record.get('temperatureC', 0):g}°C", _local_text(record.get("dueAt")), notify,
            ))
        if selected and self.tree.exists(selected):
            self.tree.selection_set(selected)
        elif visible:
            self.tree.selection_set(str(visible[0]["id"]))
        active_count = sum(not row.get("completedAt") and not row.get("archivedAt") for row in self._records)
        attention_count = sum(_needs_attention(row, now) for row in self._records)
        archive_count = sum(bool(row.get("archivedAt")) for row in self._records)
        if self._loaded:
            self.summary_var.set(
                f"표시 {len(visible)}개 / 전체 {len(self._records)}개 · 진행 중 {active_count}개 · "
                f"확인 필요 {attention_count}개 · 보관함 {archive_count}개"
            )
        companion_active = bool(self._companion.get("active"))
        heartbeat = self._companion.get("lastHeartbeatAt")
        if companion_active:
            self.companion_var.set(
                f"Windows 알림 실행기 연결됨 · 최근 확인 {_local_text(heartbeat)} · 실제 표시는 Windows 설정에 따름"
            )
        elif heartbeat:
            self.companion_var.set(f"Windows 알림 실행기 미연결 · 마지막 확인 {_local_text(heartbeat)}")
        else:
            self.companion_var.set("Windows 알림 실행기 미연결 · 이 화면만으로는 백그라운드 알림을 보내지 않습니다")
        self._render_detail()

    def _selection_changed(self, _event: Any = None) -> None:
        self._render_detail()

    def _selected_record(self) -> dict[str, Any] | None:
        selected = self.tree.selection()
        if not selected:
            return None
        return next((row for row in self._records if str(row.get("id")) == selected[0]), None)

    def _clear_detail(self) -> None:
        for child in self.details.body.winfo_children():
            child.destroy()

    def _render_detail(self) -> None:
        if not hasattr(self, "details"):
            return
        self._clear_detail()
        record = self._selected_record()
        if record is None:
            ttk.Label(
                self.details.body,
                text="조건에 맞는 기록이 없습니다. 검색어나 상태 필터를 바꿔 보세요.",
                padding=12,
            ).grid(row=0, column=0, sticky="w")
            return

        now = datetime.now(timezone.utc)
        started = _parse_timestamp(record.get("startedAt")) or now
        due = _parse_timestamp(record.get("dueAt")) or started
        completed_at = _parse_timestamp(record.get("completedAt"))
        archived = bool(record.get("archivedAt"))
        completed = completed_at is not None
        stopped = completed_at or now
        status = "보관함" if archived else "완료" if completed else "목표 도달" if now >= due else "보관 중"

        header = ttk.Frame(self.details.body, padding=(8, 6))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=str(record.get("sample", "")), font=("TkDefaultFont", 12, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(header, text=status).grid(row=0, column=1, padx=(8, 0), sticky="e")
        elapsed_label = "완료 시 경과" if completed else "경과"
        ttk.Label(header, text=f"{elapsed_label} {_duration((stopped - started).total_seconds())}").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(3, 0)
        )
        if archived:
            notify_text = "보관함에서 알림 중지"
        elif completed:
            notify_text = "완료되어 알림 중지"
        else:
            notify_text = "Windows 알림 요청 중" if record.get("notifyEnabled") else "알림 꺼짐"
        if record.get("notifiedAt"):
            notify_text += f" · 전송 이력 {_local_text(record.get('notifiedAt'))}"
        ttk.Label(
            header,
            text=(f"{record.get('temperatureC', 0):g}°C · {notify_text}\n"
                  f"시작 {_local_text(record.get('startedAt'))} · 목표 {_local_text(record.get('dueAt'))} "
                  f"({record.get('targetDays', 0):g}일)"),
            justify="left",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(3, 0))
        if completed:
            timing = f"완료 {_local_text(record.get('completedAt'))} · 완료 기록에는 알림을 보내지 않습니다."
        elif now >= due:
            timing = f"목표보다 {_duration((now - due).total_seconds())} 지남"
        else:
            timing = f"목표까지 {_duration((due - now).total_seconds())} 남음"
        ttk.Label(header, text=timing).grid(row=3, column=0, columnspan=2, sticky="w", pady=(3, 0))

        actions = ttk.Frame(self.details.body, padding=(8, 2, 8, 8))
        actions.grid(row=1, column=0, sticky="ew")
        complete_button = ttk.Button(
            actions,
            text="완료 취소" if completed else "완료 표시",
            command=lambda: self._toggle_complete(str(record["id"]), not completed),
        )
        complete_button.pack(side="left", padx=(0, 5))
        self._manage(complete_button, lambda: not archived)
        notify_button = ttk.Button(
            actions,
            text="Windows 알림 끄기" if record.get("notifyEnabled") else "Windows 알림 켜기",
            command=lambda: self._toggle_notifications(str(record["id"]), not bool(record.get("notifyEnabled"))),
        )
        notify_button.pack(side="left", padx=(0, 5))
        self._manage(notify_button, lambda: not archived and not completed)
        archive_button = ttk.Button(
            actions,
            text="보관함에서 복원" if archived else "보관함으로 이동",
            command=lambda: self._archive(str(record["id"]), not archived),
        )
        archive_button.pack(side="left")
        self._manage(archive_button)

        alerts_box = ttk.LabelFrame(self.details.body, text="알림 일정", padding=7)
        alerts_box.grid(row=2, column=0, padx=8, pady=(0, 7), sticky="ew")
        alerts_box.columnconfigure(0, weight=1)
        for index, alert in enumerate(record.get("alerts", [])):
            effective_due = _parse_timestamp(alert.get("snoozedUntil") or alert.get("dueAt")) or now
            alert_due = now >= effective_due
            label = (
                f"최종 목표 {record.get('targetDays', 0):g}일"
                if alert.get("kind") == "final"
                else f"중간 확인 {alert.get('checkpointDay', 0):g}일"
            )
            if alert.get("acknowledgedAt"):
                state = f"확인됨 {_local_text(alert.get('acknowledgedAt'))}"
            elif archived:
                state = "보관함 · 알림 중지"
            elif completed:
                state = "보관 완료 · 알림 중지"
            elif alert.get("snoozedUntil") and not alert_due:
                state = "다시 알림 대기"
            elif alert.get("notifiedAt"):
                state = f"알림 전송됨 {_local_text(alert.get('notifiedAt'))}"
            elif alert_due:
                state = "확인 필요"
            else:
                state = "예정"
            row = ttk.Frame(alerts_box)
            row.grid(row=index, column=0, pady=2, sticky="ew")
            row.columnconfigure(0, weight=1)
            suffix = " (다시 알림)" if alert.get("snoozedUntil") else ""
            ttk.Label(row, text=f"{label} · {state}\n{_local_text(alert.get('snoozedUntil') or alert.get('dueAt'))}{suffix}").grid(
                row=0, column=0, sticky="w"
            )
            if not archived and not completed and alert_due and not alert.get("acknowledgedAt"):
                ack = ttk.Button(
                    row,
                    text="확인",
                    command=lambda aid=str(alert["id"]), rid=str(record["id"]): self._acknowledge(rid, aid),
                )
                ack.grid(row=0, column=1, padx=(5, 3))
                self._manage(ack)
                snooze = ttk.Button(
                    row,
                    text="1일 후 다시 알림",
                    command=lambda aid=str(alert["id"]), rid=str(record["id"]): self._snooze(rid, aid),
                )
                snooze.grid(row=0, column=2)
                self._manage(snooze)

        history = list(record.get("archiveHistory") or [])
        if history:
            history_box = ttk.LabelFrame(self.details.body, text="보관함 이동·복원 이력", padding=7)
            history_box.grid(row=3, column=0, padx=8, pady=(0, 8), sticky="ew")
            for index, event in enumerate(history):
                action = "보관함 이동" if event.get("action") == "archived" else "복원"
                ttk.Label(history_box, text=f"{action} · {_local_text(event.get('at'))}").grid(
                    row=index, column=0, sticky="w"
                )
        self._apply_busy_state()

    def _submit_mutation(self, work: Callable[[], Any], success: str) -> None:
        def finish(result: dict[str, Any]) -> None:
            self._accept_snapshot(result)
            self.app.status(success)

        self.app.submit(work, finish, message=success)

    def _add_record(self) -> None:
        sample = self.sample_var.get().strip()
        temperature_text = self.temperature_var.get().strip()
        started_text = self.started_var.get().strip()
        days_text = self.days_var.get().strip()
        checkpoints_text = self.checkpoints_var.get().strip()
        notify_enabled = bool(self.notify_var.get())
        try:
            temperature = float(temperature_text)
            target_days = float(days_text)
            local_start = datetime.fromisoformat(started_text)
            if local_start.tzinfo is None:
                local_start = local_start.astimezone()
            started_at = local_start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            checkpoints = (
                [float(value.strip()) for value in checkpoints_text.split(",") if value.strip()]
                if checkpoints_text else []
            )
        except ValueError:
            messagebox.showerror(
                "입력 확인",
                "시작 시각은 YYYY-MM-DD HH:MM 형식, 온도·목표 일수·중간 확인일은 숫자로 입력하세요.",
                parent=self,
            )
            return
        store = self.app.controller.storage
        payload = {
            "sample": sample,
            "temperatureC": temperature,
            "startedAt": started_at,
            "targetDays": target_days,
            "checkpointDays": checkpoints,
            "notifyEnabled": notify_enabled,
        }

        def work() -> dict[str, Any]:
            store.add(payload)
            return {"records": store.list_records(include_archived=True), "companion": store.companion_status()}

        def finish(result: dict[str, Any]) -> None:
            self.sample_var.set("")
            self.started_var.set(_local_input())
            self.checkpoints_var.set("")
            self._accept_snapshot(result)
            self.app.status("보관 기록을 이 컴퓨터에 저장했습니다.")

        self.app.submit(work, finish, message="보관 기록을 저장하는 중입니다.")

    def _toggle_complete(self, record_id: str, completed: bool) -> None:
        store = self.app.controller.storage

        def work() -> dict[str, Any]:
            store.complete(record_id, completed=completed)
            return {"records": store.list_records(include_archived=True), "companion": store.companion_status()}

        message = "보관 기록을 완료로 표시했습니다." if completed else "보관 기록을 다시 진행 중으로 표시했습니다."
        self._submit_mutation(work, message)

    def _toggle_notifications(self, record_id: str, enabled: bool) -> None:
        store = self.app.controller.storage

        def work() -> dict[str, Any]:
            store.set_notifications(record_id, enabled)
            return {"records": store.list_records(include_archived=True), "companion": store.companion_status()}

        message = (
            "Windows 알림을 켰습니다. 실행기가 확인 전 알림을 처리합니다."
            if enabled else "Windows 알림을 껐습니다. 일정과 확인 이력은 보존했습니다."
        )
        self._submit_mutation(work, message)

    def _acknowledge(self, record_id: str, alert_id: str) -> None:
        store = self.app.controller.storage

        def work() -> dict[str, Any]:
            store.acknowledge_alert(record_id, alert_id)
            return {"records": store.list_records(include_archived=True), "companion": store.companion_status()}

        self._submit_mutation(work, "알림을 확인했습니다.")

    def _snooze(self, record_id: str, alert_id: str) -> None:
        until = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace("+00:00", "Z")
        store = self.app.controller.storage

        def work() -> dict[str, Any]:
            store.snooze_alert(record_id, alert_id, until)
            return {"records": store.list_records(include_archived=True), "companion": store.companion_status()}

        self._submit_mutation(work, "알림을 1일 미뤘습니다.")

    def _archive(self, record_id: str, archived: bool) -> None:
        if archived:
            text = "삭제하지 않고 보관함으로 옮깁니다. 일정과 확인 이력은 유지되고 새 알림은 중지됩니다."
            title = "보관함으로 이동"
        else:
            text = "원래 일정과 확인 이력을 유지해 복원합니다. 기한이 지난 미확인 알림이 발송될 수 있습니다."
            title = "보관함에서 복원"
        if not messagebox.askokcancel(title, text, parent=self):
            return
        store = self.app.controller.storage

        def work() -> dict[str, Any]:
            store.set_archived(record_id, archived)
            return {"records": store.list_records(include_archived=True), "companion": store.companion_status()}

        message = (
            "보관함으로 옮겼습니다. 기록·일정·확인 이력은 보존했습니다."
            if archived else "보관함에서 복원했습니다. 원래 알림 설정과 이력을 유지했습니다."
        )
        self._submit_mutation(work, message)

    def _launch_companion(self) -> None:
        if sys.platform != "win32":
            messagebox.showerror("Windows 알림", "알림 실행기는 Windows 사용자 세션에서만 시작할 수 있습니다.", parent=self)
            return
        executable = Path(sys.executable)
        pythonw = executable.with_name("pythonw.exe")
        if not pythonw.is_file():
            messagebox.showerror(
                "Windows 알림 실행기 없음",
                f"현재 Python 환경에서 pythonw.exe를 찾을 수 없습니다.\n{pythonw}",
                parent=self,
            )
            return
        store = self.app.controller.storage
        db_path = str(store.path)
        package_parent = str(Path(__file__).resolve().parents[2])

        def work() -> dict[str, Any]:
            flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            subprocess.Popen(
                [str(pythonw), "-m", "pne_scheduler.storage_companion", "--db", db_path, "--poll-seconds", "30"],
                cwd=package_parent,
                creationflags=flags,
                close_fds=True,
            )
            return {"records": store.list_records(include_archived=True), "companion": store.companion_status()}

        self._submit_mutation(
            work,
            "Windows 알림 실행기를 시작했습니다. 연결 표시는 다음 heartbeat 후 갱신됩니다.",
        )


__all__ = ["StoragePanel"]
