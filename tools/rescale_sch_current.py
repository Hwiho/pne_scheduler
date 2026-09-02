"""CLI: rescale .sch charge/discharge currents for a new cell capacity (C-rate preserved)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pne_scheduler.io.current_rescaler import (
    C_RATE_DIGITS,
    CURRENT_DIGITS,
    FRACTION_C_RATE_TOLERANCE,
    collect_current_fields,
    scale_current_fields,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scale .sch charge/discharge current values for a new cell capacity."
    )
    parser.add_argument("input_sch", type=Path, help="Source .sch file")
    parser.add_argument("output_sch", type=Path, help="Output .sch file")
    parser.add_argument("old_capacity_mAh", type=float, help="Cell capacity used by the source .sch")
    parser.add_argument("new_capacity_mAh", type=float, help="Cell capacity for the new .sch")
    parser.add_argument("--force", action="store_true", help="Overwrite output file if it exists")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing output")
    parser.add_argument("--show-current", action="store_true", help="List current fields before scaling")
    parser.add_argument("--summary-limit", type=int, default=40, help="Max rows to print")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if not args.input_sch.is_file():
        print(f"Input file not found: {args.input_sch}", file=sys.stderr)
        return 2
    if args.output_sch.exists() and not args.force and not args.dry_run:
        print(f"Output exists; use --force: {args.output_sch}", file=sys.stderr)
        return 2

    src = args.input_sch.read_bytes()
    try:
        if args.show_current:
            summary = collect_current_fields(src, args.old_capacity_mAh)
            print(f"Header size: {summary['header_size']} bytes")
            print(f"Step count: {summary['step_count']}")
            for row in summary["fields"][: args.summary_limit]:
                c_label = row.c_rate_label or (f"{row.canonical_c_rate}C" if row.canonical_c_rate else "-")
                print(f"  step {row.step:3d}  {row.kind:12s}  {row.field:14s}  {row.value:.4g} mA  ({c_label})")
            print()

        out, result = scale_current_fields(
            src,
            args.old_capacity_mAh,
            args.new_capacity_mAh,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Scale factor: {result['factor']:.6g}")
    print(f"Changed fields: {len(result['changes'])}")
    for change in result["changes"][: args.summary_limit]:
        old_c = change.get("old_c_label") or change.get("old_c")
        new_c = change.get("new_c_label") or change.get("new_c")
        print(
            f"  step {change['step']:3d}  {change['field']:14s}  "
            f"{change['old']:.4g} -> {change['new']:.4g} mA  ({old_c} -> {new_c})"
        )

    if args.dry_run:
        print("Dry run: output not written.")
        return 0

    args.output_sch.parent.mkdir(parents=True, exist_ok=True)
    args.output_sch.write_bytes(out)
    print(f"Wrote: {args.output_sch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
