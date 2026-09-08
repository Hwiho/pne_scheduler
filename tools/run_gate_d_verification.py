"""Run Gate D verification and write planning/GATE_D_VALIDATION_REPORT.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from pne_scheduler.validate.gate_d_verification import (  # noqa: E402
    DEFAULT_REPORT_PATH,
    run_gate_d_verification,
    write_gate_d_verification_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Output JSON path (default: planning/GATE_D_VALIDATION_REPORT.json)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print pass/fail summary",
    )
    args = parser.parse_args(argv)

    report = run_gate_d_verification()
    out = write_gate_d_verification_report(report, args.report)
    payload = report.to_dict()
    if args.quiet:
        print(f"gate_d_passed={report.gate_d_passed} report={out}")
    else:
        print(json.dumps(payload["summary"], indent=2))
        print(f"gate_d_passed={report.gate_d_passed}")
        print(f"wrote {out}")
        failed = [c for c in payload["checks"] if c["status"] == "fail"]
        if failed:
            print("failures:")
            for item in failed:
                print(f"  - {item['id']}: {item['detail']}")
    return 0 if report.gate_d_passed else 1


if __name__ == "__main__":
    sys.exit(main())
