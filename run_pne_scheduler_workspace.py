"""Offline Tk workspace launcher; no browser, Node, or HTTP server required."""

import argparse
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root.parent) not in sys.path:
    sys.path.insert(0, str(_root.parent))

from pne_scheduler.ui import launch_workspace


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, nargs="?", help="웹/Tk .schproj 파일")
    parser.add_argument("--data-dir", type=Path, help="라이브러리·고온저장·자동 복구의 별도 폴더")
    args = parser.parse_args()
    raise SystemExit(launch_workspace(args.project, data_dir=args.data_dir))
