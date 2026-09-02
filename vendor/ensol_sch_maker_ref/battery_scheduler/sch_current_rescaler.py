"""
Scale current values in a PNE CTSPro .sch file for a new cell capacity.

Usage:
    python sch_current_rescaler.py input.sch output.sch 100 120

The tool preserves the intended C-rate by canonicalizing current-derived
C-rate values and recalculating currents from the new capacity.

It updates only:
    - CCCV charge current
    - CCCV CV cut-off current
    - CC charge current
    - CC discharge current
"""
import argparse
import os
import struct
import sys


HEADER_1632 = 1632
HEADER_1760 = 1760
STEP_SIZE = 612

TYPE_CCCV = 0x0101
TYPE_CCCH = 0x0201
TYPE_CCDI = 0x0202

OFF_IDX = 0
OFF_TYPE = 8
OFF_CURR = 16
OFF_CVCO = 32

CURRENT_DIGITS = 3
C_RATE_DIGITS = 2
ONE_THIRD_C_RATE = 1.0 / 3.0
FRACTION_C_RATE_TOLERANCE = 0.0005


def read_i32(buf, offset):
    return struct.unpack_from("<i", buf, offset)[0]


def read_f32(buf, offset):
    return struct.unpack_from("<f", buf, offset)[0]


def write_f32(buf, offset, value):
    struct.pack_into("<f", buf, offset, float(value))


def format_number(value, digits):
    """Return a compact, stable decimal string for user-facing logs."""
    if value is None:
        return "-"
    rounded = round(float(value), int(digits))
    text = ("%.*f" % (int(digits), rounded)).rstrip("0").rstrip(".")
    if text == "-0":
        return "0"
    return text


def format_mA(value, digits=CURRENT_DIGITS):
    return format_number(value, digits)


def format_c_rate(value, digits=C_RATE_DIGITS):
    return format_number(value, digits)


def format_c_rate_display(value, label=None, digits=C_RATE_DIGITS):
    if label:
        return "%sC" % label
    text = format_c_rate(value, digits)
    if text == "-":
        return text
    return "%sC" % text


def parse_capacity_list(text):
    """Parse comma-separated positive mAh capacity values."""
    if text is None or not str(text).strip():
        raise ValueError("capacity list must not be empty")
    capacities = []
    for raw_part in str(text).split(","):
        part = raw_part.strip()
        if not part:
            raise ValueError("capacity list contains an empty value")
        try:
            value = float(part)
        except ValueError:
            raise ValueError("invalid capacity value: %s" % part)
        if value <= 0:
            raise ValueError("capacity values must be greater than zero")
        capacities.append(value)
    return capacities


def format_capacity_for_filename(value):
    return format_number(value, CURRENT_DIGITS)


def build_batch_output_path(output_dir, stem, capacity_mAh):
    filename = "%s_%smAh.sch" % (stem, format_capacity_for_filename(capacity_mAh))
    return os.path.join(output_dir, filename)


def canonical_c_rate(current_mA, capacity_mAh, digits=C_RATE_DIGITS):
    if capacity_mAh <= 0:
        raise ValueError("capacity_mAh must be greater than zero")
    return round(float(current_mA) / float(capacity_mAh), int(digits))


def canonical_c_rate_info(
    current_mA,
    capacity_mAh,
    digits=C_RATE_DIGITS,
    fraction_tolerance=FRACTION_C_RATE_TOLERANCE,
):
    if capacity_mAh <= 0:
        raise ValueError("capacity_mAh must be greater than zero")
    if digits < 0:
        raise ValueError("digits must be zero or greater")
    if fraction_tolerance < 0:
        raise ValueError("fraction_tolerance must be zero or greater")

    raw = float(current_mA) / float(capacity_mAh)
    if fraction_tolerance > 0 and abs(raw - ONE_THIRD_C_RATE) <= float(fraction_tolerance):
        return {
            "raw": raw,
            "value": ONE_THIRD_C_RATE,
            "label": "1/3",
        }
    return {
        "raw": raw,
        "value": round(raw, int(digits)),
        "label": None,
    }


def current_from_c_rate(c_rate, capacity_mAh, digits=CURRENT_DIGITS):
    if capacity_mAh <= 0:
        raise ValueError("capacity_mAh must be greater than zero")
    return round(float(c_rate) * float(capacity_mAh), int(digits))


def detect_header_size(data):
    candidates = []
    for header_size in (HEADER_1632, HEADER_1760):
        if len(data) >= header_size and (len(data) - header_size) % STEP_SIZE == 0:
            candidates.append(header_size)
    if not candidates:
        raise ValueError("Unsupported .sch size: cannot align header and 612-byte steps")
    if HEADER_1760 in candidates and HEADER_1632 not in candidates:
        return HEADER_1760
    return HEADER_1632


def step_kind(type_code):
    if type_code == TYPE_CCCV:
        return "CCCV"
    if type_code == TYPE_CCCH:
        return "CC Charge"
    if type_code == TYPE_CCDI:
        return "CC Discharge"
    return "Other"


def collect_current_fields(
    data,
    capacity_mAh=None,
    current_digits=CURRENT_DIGITS,
    c_rate_digits=C_RATE_DIGITS,
    fraction_tolerance=FRACTION_C_RATE_TOLERANCE,
):
    """Return existing current-bearing fields from a .sch file."""
    if capacity_mAh is not None and capacity_mAh <= 0:
        raise ValueError("capacity_mAh must be greater than zero")
    if current_digits < 0:
        raise ValueError("current_digits must be zero or greater")
    if c_rate_digits < 0:
        raise ValueError("c_rate_digits must be zero or greater")
    if fraction_tolerance < 0:
        raise ValueError("fraction_tolerance must be zero or greater")

    header_size = detect_header_size(data)
    step_count = (len(data) - header_size) // STEP_SIZE
    fields = []

    for step_index in range(step_count):
        base = header_size + step_index * STEP_SIZE
        block = memoryview(data)[base:base + STEP_SIZE]
        step_num = read_i32(block, OFF_IDX)
        type_code = read_i32(block, OFF_TYPE) & 0xFFFF

        if type_code in (TYPE_CCCV, TYPE_CCCH, TYPE_CCDI):
            current = read_f32(block, OFF_CURR)
            c_info = (
                canonical_c_rate_info(current, capacity_mAh, c_rate_digits, fraction_tolerance)
                if capacity_mAh
                else {"raw": None, "value": None, "label": None}
            )
            fields.append({
                "step": step_num,
                "field": "current_mA",
                "kind": step_kind(type_code),
                "value": current,
                "c_rate": c_info["raw"],
                "canonical_c_rate": c_info["value"],
                "c_rate_label": c_info["label"],
            })

        if type_code == TYPE_CCCV:
            cvco = read_f32(block, OFF_CVCO)
            c_info = (
                canonical_c_rate_info(cvco, capacity_mAh, c_rate_digits, fraction_tolerance)
                if capacity_mAh
                else {"raw": None, "value": None, "label": None}
            )
            fields.append({
                "step": step_num,
                "field": "cv_cutoff_mA",
                "kind": "CCCV",
                "value": cvco,
                "c_rate": c_info["raw"],
                "canonical_c_rate": c_info["value"],
                "c_rate_label": c_info["label"],
            })

    return {
        "header_size": header_size,
        "step_count": step_count,
        "current_digits": int(current_digits),
        "c_rate_digits": int(c_rate_digits),
        "fraction_tolerance": float(fraction_tolerance),
        "fields": fields,
    }


def scale_current_fields(
    data,
    old_capacity_mAh,
    new_capacity_mAh,
    current_digits=CURRENT_DIGITS,
    c_rate_digits=C_RATE_DIGITS,
    fraction_tolerance=FRACTION_C_RATE_TOLERANCE,
):
    if old_capacity_mAh <= 0:
        raise ValueError("old_capacity_mAh must be greater than zero")
    if new_capacity_mAh <= 0:
        raise ValueError("new_capacity_mAh must be greater than zero")
    if current_digits < 0:
        raise ValueError("current_digits must be zero or greater")
    if c_rate_digits < 0:
        raise ValueError("c_rate_digits must be zero or greater")
    if fraction_tolerance < 0:
        raise ValueError("fraction_tolerance must be zero or greater")

    factor = float(new_capacity_mAh) / float(old_capacity_mAh)
    out = bytearray(data)
    header_size = detect_header_size(out)
    step_count = (len(out) - header_size) // STEP_SIZE
    changes = []

    for step_index in range(step_count):
        base = header_size + step_index * STEP_SIZE
        block = memoryview(out)[base:base + STEP_SIZE]
        step_num = read_i32(block, OFF_IDX)
        type_code = read_i32(block, OFF_TYPE) & 0xFFFF

        if type_code in (TYPE_CCCV, TYPE_CCCH, TYPE_CCDI):
            old_current = read_f32(block, OFF_CURR)
            old_c_info = canonical_c_rate_info(
                old_current,
                old_capacity_mAh,
                c_rate_digits,
                fraction_tolerance,
            )
            new_current = current_from_c_rate(old_c_info["value"], new_capacity_mAh, current_digits)
            new_c_info = canonical_c_rate_info(
                new_current,
                new_capacity_mAh,
                c_rate_digits,
                fraction_tolerance,
            )
            write_f32(block, OFF_CURR, new_current)
            changes.append({
                "step": step_num,
                "field": "current_mA",
                "kind": step_kind(type_code),
                "old": old_current,
                "new": new_current,
                "old_c_raw": old_c_info["raw"],
                "old_c": old_c_info["value"],
                "old_c_label": old_c_info["label"],
                "new_c": new_c_info["value"],
                "new_c_label": old_c_info["label"] or new_c_info["label"],
            })

        if type_code == TYPE_CCCV:
            old_cvco = read_f32(block, OFF_CVCO)
            old_c_info = canonical_c_rate_info(
                old_cvco,
                old_capacity_mAh,
                c_rate_digits,
                fraction_tolerance,
            )
            new_cvco = current_from_c_rate(old_c_info["value"], new_capacity_mAh, current_digits)
            new_c_info = canonical_c_rate_info(
                new_cvco,
                new_capacity_mAh,
                c_rate_digits,
                fraction_tolerance,
            )
            write_f32(block, OFF_CVCO, new_cvco)
            changes.append({
                "step": step_num,
                "field": "cv_cutoff_mA",
                "kind": "CCCV",
                "old": old_cvco,
                "new": new_cvco,
                "old_c_raw": old_c_info["raw"],
                "old_c": old_c_info["value"],
                "old_c_label": old_c_info["label"],
                "new_c": new_c_info["value"],
                "new_c_label": old_c_info["label"] or new_c_info["label"],
            })

    return bytes(out), {
        "header_size": header_size,
        "step_count": step_count,
        "factor": factor,
        "current_digits": int(current_digits),
        "c_rate_digits": int(c_rate_digits),
        "fraction_tolerance": float(fraction_tolerance),
        "changes": changes,
    }


def print_current_fields(summary, limit=None):
    fields = summary["fields"]
    current_digits = summary.get("current_digits", CURRENT_DIGITS)
    c_rate_digits = summary.get("c_rate_digits", C_RATE_DIGITS)
    print("Header size: %d bytes" % summary["header_size"])
    print("Step count: %d" % summary["step_count"])
    print("Current fields: %d" % len(fields))
    print("Fraction alias: 1/3C tolerance %.12gC" % summary.get("fraction_tolerance", 0))

    shown = fields if limit is None else fields[:limit]
    if shown:
        print("")
        print(" step  kind          field              mA      C-rate")
        print(" ----  ------------  ------------  ----------  ----------")
        for item in shown:
            c_rate_value = item.get("canonical_c_rate", item.get("c_rate"))
            print(
                "%5s  %-12s  %-12s  %10s  %10s"
                % (
                    item["step"],
                    item["kind"],
                    item["field"],
                    format_mA(item["value"], current_digits),
                    format_c_rate_display(c_rate_value, item.get("c_rate_label"), c_rate_digits),
                )
            )
    if limit is not None and len(fields) > limit:
        print("")
        print("... %d more current fields" % (len(fields) - limit))


def print_summary(summary, limit=None):
    changes = summary["changes"]
    current_digits = summary.get("current_digits", CURRENT_DIGITS)
    c_rate_digits = summary.get("c_rate_digits", C_RATE_DIGITS)
    print("Header size: %d bytes" % summary["header_size"])
    print("Step count: %d" % summary["step_count"])
    print("Scale factor: %.12g" % summary["factor"])
    print(
        "Canonicalization: C-rate %d decimals, current %d decimals"
        % (c_rate_digits, current_digits)
    )
    print("Fraction alias: 1/3C tolerance %.12gC" % summary.get("fraction_tolerance", 0))
    print("Changed fields: %d" % len(changes))

    shown = changes if limit is None else changes[:limit]
    if shown:
        print("")
        print(" step  kind          field          old mA      new mA      C-rate")
        print(" ----  ------------  ------------  ----------  ----------  ----------")
        for ch in shown:
            print(
                "%5s  %-12s  %-12s  %10s  %10s  %s -> %s"
                % (
                    ch["step"],
                    ch["kind"],
                    ch["field"],
                    format_mA(ch["old"], current_digits),
                    format_mA(ch["new"], current_digits),
                    format_c_rate_display(ch["old_c"], ch.get("old_c_label"), c_rate_digits),
                    format_c_rate_display(ch["new_c"], ch.get("new_c_label"), c_rate_digits),
                )
            )
    if limit is not None and len(changes) > limit:
        print("")
        print("... %d more changed fields" % (len(changes) - limit))


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Scale .sch charge/discharge current values for a new cell capacity."
    )
    parser.add_argument("input_sch", help="Source .sch file")
    parser.add_argument("output_sch", help="Output .sch file")
    parser.add_argument("old_capacity_mAh", type=float, help="Cell capacity used by the source .sch")
    parser.add_argument("new_capacity_mAh", type=float, help="Cell capacity for the new .sch")
    parser.add_argument("--force", action="store_true", help="Overwrite output file if it already exists")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing output")
    parser.add_argument("--show-current", action="store_true", help="Show existing current fields before conversion")
    parser.add_argument("--summary-limit", type=int, default=80, help="Maximum changed rows to print")
    parser.add_argument(
        "--current-digits",
        type=int,
        default=CURRENT_DIGITS,
        help="Decimal places for written and displayed current values",
    )
    parser.add_argument(
        "--c-rate-digits",
        type=int,
        default=C_RATE_DIGITS,
        help="Decimal places used to canonicalize C-rate values",
    )
    parser.add_argument(
        "--fraction-tolerance",
        type=float,
        default=FRACTION_C_RATE_TOLERANCE,
        help="C-rate tolerance for recognizing 1/3C fraction alias",
    )
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)

    if not os.path.exists(args.input_sch):
        print("Input file not found: %s" % args.input_sch, file=sys.stderr)
        return 2
    if os.path.exists(args.output_sch) and not args.force and not args.dry_run:
        print("Output file already exists. Use --force to overwrite: %s" % args.output_sch, file=sys.stderr)
        return 2

    with open(args.input_sch, "rb") as f:
        src = f.read()

    try:
        if args.show_current:
            current_summary = collect_current_fields(
                src,
                args.old_capacity_mAh,
                current_digits=args.current_digits,
                c_rate_digits=args.c_rate_digits,
                fraction_tolerance=args.fraction_tolerance,
            )
            print_current_fields(current_summary, limit=args.summary_limit)
            print("")
        out, summary = scale_current_fields(
            src,
            args.old_capacity_mAh,
            args.new_capacity_mAh,
            current_digits=args.current_digits,
            c_rate_digits=args.c_rate_digits,
            fraction_tolerance=args.fraction_tolerance,
        )
    except Exception as exc:
        print("Error: %s" % exc, file=sys.stderr)
        return 1

    print_summary(summary, limit=args.summary_limit)

    if args.dry_run:
        print("")
        print("Dry run: output was not written.")
        return 0

    output_dir = os.path.dirname(os.path.abspath(args.output_sch))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(args.output_sch, "wb") as f:
        f.write(out)

    print("")
    print("Wrote: %s" % args.output_sch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
