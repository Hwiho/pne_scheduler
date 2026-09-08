"""PNE Scheduler workspace launcher (setup → protocol → procedure → validate → export)."""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root.parent) not in sys.path:
    sys.path.insert(0, str(_root.parent))

from pne_scheduler.ui import launch_workspace


if __name__ == "__main__":
    argument = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    raise SystemExit(launch_workspace(argument))
