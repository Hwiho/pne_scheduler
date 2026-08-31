"""PNE Scheduler project editor launcher."""
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root.parent) not in sys.path:
    sys.path.insert(0, str(_root.parent))

from pne_scheduler.ui.project_editor import launch_project_editor

if __name__ == "__main__":
    launch_project_editor()
