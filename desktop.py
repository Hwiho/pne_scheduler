"""Offline executable entry point, including opt-in isolated package checks."""
from __future__ import annotations

import argparse
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import json
from pathlib import Path
import sys
import traceback


def _run(args):
    if args.self_test or args.gui_self_test:
        from .desktop_selftest import run_self_test
        report = args.self_test or args.gui_self_test
        return run_self_test(report, gui=bool(args.gui_self_test))
    from .ui import launch_workspace
    return launch_workspace(args.project, data_dir=args.data_dir)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--storage-companion":
        from .storage_companion import main as companion_main
        return companion_main(argv[1:])
    parser = argparse.ArgumentParser(description="PNE Scheduler 오프라인 작업실")
    parser.add_argument("project", type=Path, nargs="?")
    parser.add_argument("--data-dir", type=Path, help="라이브러리·고온저장·복구 폴더")
    checks = parser.add_mutually_exclusive_group()
    checks.add_argument("--self-test", type=Path, metavar="REPORT", help="창 없는 패키지 검사, JSON 결과")
    checks.add_argument("--gui-self-test", type=Path, metavar="REPORT", help="별도 데스크톱/CI에서만 실제 Tk 검사")
    args = parser.parse_args(argv)
    report = args.self_test or args.gui_self_test
    if report:
        # Do not replace an existing report/project accidentally.
        if report.exists():
            return 2
        report.parent.mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        if sys.stdout is None or sys.stderr is None:
            base = report.parent if report else (args.data_dir or Path.home() / ".pne_scheduler")
            log = base / "logs" / "desktop.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            stream = stack.enter_context(log.open("a", encoding="utf-8"))
            if sys.stdout is None:
                stack.enter_context(redirect_stdout(stream))
            if sys.stderr is None:
                stack.enter_context(redirect_stderr(stream))
        try:
            return _run(args)
        except Exception as exc:
            traceback.print_exc()
            if report:
                with report.open("x", encoding="utf-8") as stream:
                    json.dump({"ok": False, "error": str(exc)}, stream, ensure_ascii=False, indent=2)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
