"""PNE Scheduler web API launcher (localhost only).

The lab PC holds the `.sch` originals and the CTSPro-authored templates. A server
that can read and write those must not be reachable from the network, so the
default bind is 127.0.0.1 and widening it is a deliberate argument.
"""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root.parent) not in sys.path:
    sys.path.insert(0, str(_root.parent))

from pne_scheduler.api.app import main


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    raise SystemExit(main(port=port))
