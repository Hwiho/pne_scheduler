"""Offline Tk workspace launcher; no browser, Node, or HTTP server required."""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root.parent) not in sys.path:
    sys.path.insert(0, str(_root.parent))

from pne_scheduler.desktop import main


if __name__ == "__main__":
    raise SystemExit(main())
