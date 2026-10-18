"""PNE Scheduler web API launcher (localhost only).

The lab PC holds the `.sch` originals and the CTSPro-authored templates. A server
that can read and write those must not be reachable from the network, so the
default bind is 127.0.0.1 and widening it is a deliberate argument.
"""

import sys
import argparse
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root.parent) not in sys.path:
    sys.path.insert(0, str(_root.parent))

from pne_scheduler.api.app import main


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PNE local web API")
    parser.add_argument("port", nargs="?", type=int, default=8000)
    parser.add_argument("--data-dir", type=Path, help="복원/시험용 데이터 폴더")
    args = parser.parse_args()
    raise SystemExit(main(port=args.port, data_dir=args.data_dir))
