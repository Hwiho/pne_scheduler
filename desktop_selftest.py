"""Packaged-runtime checks using disposable data, never a user's experiments."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time


def _check(condition, message):
    if not condition:
        raise RuntimeError(message)


def _exercise_gui(controller):
    # This function is called only by explicit --gui-self-test in separate CI.
    from .ui.tk_runtime import create_root
    from .ui.tk_workspace import WorkspaceApp
    root = create_root()
    root.withdraw()
    errors = []
    root.report_callback_exception = lambda *args: errors.append(str(args))
    app = WorkspaceApp(root, controller)
    try:
        _check(len(app.notebook.tabs()) == 7, "Seven desktop panels missing")
        _check(app.perform("addModule", {"moduleType": "rest"}), "UI edit was rejected")
        deadline = time.monotonic() + 30
        while app.busy and time.monotonic() < deadline:
            root.update()
            time.sleep(.01)
        _check(not app.busy, "Desktop worker timed out")
        _check(not errors, f"Tk callback failed: {errors}")
        _check(controller.project["modules"][-1]["module_type"] == "rest", "UI edit missing")
        for panel in app.panels:
            app.notebook.select(panel)
            root.update_idletasks()
    finally:
        app._shutdown()


def run_self_test(report: Path, *, gui=False):
    # Self-tests are explicit, short-lived processes. Fail if any tested path
    # attempts a network connection/listener instead of relying on local data.
    def offline_only(event, _args):
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
            raise RuntimeError(f"Offline check attempted network access: {event}")
    sys.addaudithook(offline_only)
    from .ui.native_controller import NativeController
    from .ir.project import ScheduleProject
    from .schema.equipment import load_equipment_ratings
    from .schema.equipment_registry import load_equipment_registry
    from .desktop_runtime import companion_command

    _check(bool(load_equipment_ratings()), "Equipment ratings missing from package")
    _check(bool(load_equipment_registry()), "Equipment registry missing from package")
    checks = ["network-denied", "equipment-resources"]
    with tempfile.TemporaryDirectory(prefix="pne-selftest-") as temporary:
        work = Path(temporary).resolve() / "한글 경로 with spaces"
        work.mkdir()
        controller = NativeController(data_dir=work / "data")
        controller.edit("setEquipmentUnit", {"unit": "PNE02"})
        controller.edit("addModule", {"moduleType": "formation"})
        saved = controller.save(work / "오프라인.schproj")
        _check(ScheduleProject.load(saved).to_dict() == controller.project, "Project round-trip mismatch")
        checks.append("project-save-reopen")
        controller.save_method("검사 전용 방법")
        checks.append("method-library-save")
        args = {"phase": "formation", "basis": "manual_reference", "kind": "preview", "rows": [
            {"cellId": "A01", "referenceCapacityMah": "80"},
            {"cellId": "A02", "referenceCapacityMah": "90"}]}
        plan = controller.plan("cellBatch", args)
        _check(plan["ok"], "Cell batch preview failed")
        controller.export_batch(args, plan["token"], work / "batch")
        for cell, expected in (("A01", 8), ("A02", 9)):
            with (work / "batch" / cell / "steps.csv").open(encoding="utf-8-sig") as stream:
                values = [abs(float(r["전류(mA)"])) for r in csv.DictReader(stream) if r["전류(mA)"]]
            _check(max(values) == expected, "Reference-capacity batch current mismatch")
        checks.append("80-90mAh-batch-current")
        result = controller.export("review_candidate", work / "review")
        schedule = next(Path(p) for p in result["paths"] if p.endswith(".sch"))
        digest = hashlib.sha256(schedule.read_bytes()).hexdigest()
        opened = controller.import_open(schedule)
        _check(opened["sha256"] == digest and opened["stepCount"] > 1, "SCH reopen failed")
        checks.append("analysis-only-sch-reopen")
        now = datetime.now(timezone.utc)
        record = controller.storage.add({"sample": "패키지 검사 셀", "temperatureC": 45,
            "startedAt": now.isoformat(), "targetDays": 30, "notifyEnabled": False}, now=now)
        controller.storage.set_archived(record["id"], True)
        controller.storage.set_archived(record["id"], False)
        _check(len(controller.storage.list_records()) == 1, "Storage persistence failed")
        checks.append("sqlite-storage-archive-restore")
        plan = controller.data_action("backupPreview", {"includeCurrent": True})
        backup = controller.data_action("backupCreate", {"includeCurrent": True, "token": plan["token"],
            "outputPath": str(work / "backup.zip"), "externalWritesStopped": True})
        inspection = controller.data_action("restoreInspect", {"archivePath": backup["path"]})
        restored = controller.data_action("restoreApply", {"archivePath": backup["path"], "token": inspection["token"],
            "destination": str(work / "restored")})
        restored_controller = NativeController(data_dir=Path(restored["path"]))
        _check(restored_controller.data_action("status")["companion"]["restorePaused"], "Restore did not pause alerts")
        _check(len(restored_controller.storage.list_records()) == 1, "Backup record round-trip failed")
        _check(len(restored_controller.library.methods()) == 1, "Backup method round-trip failed")
        checks.append("verified-backup-new-location-restore-paused")
        if getattr(sys, "frozen", False):
            command = companion_command(controller.storage.path)
            _check(command[:2] == [sys.executable, "--storage-companion"], "Frozen notifier command mismatch")
            checks.append("frozen-notifier-dispatch-only")
        if gui:
            _exercise_gui(controller)
            checks.append("actual-tk-seven-panels-worker-edit")
        _check("flask" not in sys.modules, "Offline package imported Flask")
    with Path(report).open("x", encoding="utf-8") as stream:
        json.dump({"ok": True, "frozen": bool(getattr(sys, "frozen", False)),
                   "platform": sys.platform, "python": sys.version.split()[0], "checks": checks,
                   "guiTested": gui, "notificationsDisplayed": False, "equipmentApproved": False},
                  stream, ensure_ascii=False, indent=2)
    return 0
