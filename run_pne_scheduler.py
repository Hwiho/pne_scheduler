"""PNE Scheduler CLI launcher."""
import sys
from pathlib import Path

# Allow running from repo root when package directory name is pne_scheduler.
_root = Path(__file__).resolve().parent
if str(_root.parent) not in sys.path:
    sys.path.insert(0, str(_root.parent))

from pne_scheduler.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
