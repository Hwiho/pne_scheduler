"""PNE Scheduler resume wizard launcher."""
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root.parent) not in sys.path:
    sys.path.insert(0, str(_root.parent))

from pne_scheduler.ui.resume_wizard import launch_resume_wizard

if __name__ == "__main__":
    launch_resume_wizard()
