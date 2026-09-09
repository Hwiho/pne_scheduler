"""Start the workspace: API and screens, both on localhost.

The lab PC holds the `.sch` originals and the CTSPro-authored templates, so both
processes bind to 127.0.0.1 and neither is reachable from the network. Widening
that is a deliberate act, not a flag away.

The two are started together because they are one product to the person using
them, and because a half-started workspace — screens up, API down — looks like a
bug rather than a missing step.
"""

from __future__ import annotations

import atexit
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
API_PORT = 8000
WEB_PORT = 3000
# Node needs to install and compile on a cold start; the API is up in a second.
API_TIMEOUT = 30.0
WEB_TIMEOUT = 180.0


def _wait(url: str, timeout: float, what: str) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except urllib.error.HTTPError:
            return True  # answering at all is enough; the status is the app's business
        except (urllib.error.URLError, OSError):
            time.sleep(0.4)
    print(f"{what} 이(가) {timeout:.0f}초 안에 시작되지 않았습니다.", file=sys.stderr)
    return False


def main() -> int:
    if not WEB.is_dir():
        print(f"web/ 폴더가 없습니다: {WEB}", file=sys.stderr)
        return 2

    npm = shutil.which("npm")
    if npm is None:
        print(
            "npm 을 찾을 수 없습니다. Node.js 를 설치한 뒤 다시 실행하십시오.",
            file=sys.stderr,
        )
        return 2

    try:
        import flask  # noqa: F401
    except ImportError:
        print(
            '웹 API 에 Flask 가 필요합니다: pip install -e ".[web]"',
            file=sys.stderr,
        )
        return 2

    processes: list[subprocess.Popen] = []

    def spawn(command: list[str], **kwargs) -> subprocess.Popen:
        """Start a child in its own process group.

        `npm run dev` launches `next` as a grandchild, so terminating npm alone
        leaves the dev server running and the port held. Killing the whole group
        is what actually stops the thing the user started.
        """
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        process = subprocess.Popen(command, **kwargs)
        processes.append(process)
        return process

    def stop() -> None:
        for process in reversed(processes):
            if process.poll() is not None:
                continue
            try:
                if os.name == "nt":
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except (OSError, ProcessLookupError):
                process.terminate()
        for process in reversed(processes):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    if os.name != "nt":
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    else:
                        process.kill()
                except (OSError, ProcessLookupError):
                    process.kill()

    atexit.register(stop)

    def _terminated(_signum, _frame):
        # atexit does not run on SIGTERM, and a supervisor or `pkill` sends that
        # rather than Ctrl+C — without this the dev server outlives the launcher
        # and keeps holding port 3000.
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _terminated)

    print(f"API  시작 http://127.0.0.1:{API_PORT}")
    spawn([sys.executable, str(ROOT / "run_pne_scheduler_api.py"), str(API_PORT)])
    if not _wait(f"http://127.0.0.1:{API_PORT}/api/health", API_TIMEOUT, "API"):
        stop()
        return 1

    if not (WEB / "node_modules").is_dir():
        print("web/node_modules 가 없습니다. npm install 을 먼저 실행합니다…")
        if subprocess.run([npm, "install"], cwd=WEB).returncode != 0:
            stop()
            return 1

    # `next dev` reads the proxy target at request time; `next start` bakes it in
    # at build time, so dev is the mode that respects PNE_API here.
    environment = {**os.environ, "PNE_API": f"http://127.0.0.1:{API_PORT}"}
    print(f"화면 시작 http://localhost:{WEB_PORT}")
    spawn([npm, "run", "dev"], cwd=WEB, env=environment)
    if not _wait(f"http://127.0.0.1:{WEB_PORT}/", WEB_TIMEOUT, "화면"):
        stop()
        return 1

    print()
    print(f"  워크스페이스: http://localhost:{WEB_PORT}")
    print("  종료하려면 Ctrl+C")
    try:
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n종료합니다…")
    finally:
        stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
