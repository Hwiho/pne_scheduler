"""Compare a controlled before/after SCH pair for field mapping evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from pne_scheduler.io.sch_binary import read_sch_binary
from pne_scheduler.schema.fields import SchFieldDefinition, get_step_fields


def _changed_ranges(before: bytes, after: bytes) -> list[tuple[int, int]]:
    limit = min(len(before), len(after))
    changed = [index for index in range(limit) if before[index] != after[index]]
    if len(before) != len(after):
        changed.extend(range(limit, max(len(before), len(after))))
    if not changed:
        return []

    ranges: list[tuple[int, int]] = []
    start = previous = changed[0]
    for index in changed[1:]:
        if index != previous + 1:
            ranges.append((start, previous + 1))
            start = index
        previous = index
    ranges.append((start, previous + 1))
    return ranges


def _range_payload(before: bytes, after: bytes, start: int, end: int) -> dict[str, Any]:
    return {
        "start": start,
        "end_exclusive": end,
        "length": end - start,
        "before_hex": before[start:end].hex(),
        "after_hex": after[start:end].hex(),
    }


def _decode_word(data: bytes, offset: int) -> dict[str, int | float | str] | None:
    word = data[offset : offset + 4]
    if len(word) != 4:
        return None
    return {
        "hex": word.hex(),
        "uint32": struct.unpack("<I", word)[0],
        "int32": struct.unpack("<i", word)[0],
        "float32": struct.unpack("<f", word)[0],
    }


def _decode_primary(
    data: bytes,
    field: SchFieldDefinition | None,
) -> int | float | None:
    if field is None:
        return None
    value = data[field.offset : field.offset + field.size]
    if len(value) != field.size:
        return None
    formats = {
        "uint8": "<B",
        "uint32": "<I",
        "int32": "<i",
        "float32": "<f",
    }
    return struct.unpack(formats[field.dtype], value)[0]


def _changed_words(
    before: bytes,
    after: bytes,
    ranges: list[tuple[int, int]],
    version: int,
) -> list[dict[str, Any]]:
    fields = get_step_fields(version)
    offsets = {
        word_offset
        for start, end in ranges
        for word_offset in range((start // 4) * 4, ((end + 3) // 4) * 4, 4)
    }
    words = []
    for offset in sorted(offsets):
        changed_bytes = {
            byte_offset
            for start, end in ranges
            for byte_offset in range(max(start, offset), min(end, offset + 4))
        }
        matches = [
            field
            for field in fields
            if any(
                field.offset <= byte_offset < field.offset + field.size
                for byte_offset in changed_bytes
            )
        ]
        field = matches[0] if len(matches) == 1 else None
        words.append(
            {
                "offset": offset,
                "field": field.name if field else None,
                "confidence": field.confidence.value if field else "unknown",
                "dtype": field.dtype if field else None,
                "evidence": field.evidence if field else None,
                "writer_ready": field.writer_ready if field else False,
                "primary_before": _decode_primary(before, field),
                "primary_after": _decode_primary(after, field),
                "before": _decode_word(before, offset),
                "after": _decode_word(after, offset),
            }
        )
    return words


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compare_sch_files(before_path: Path, after_path: Path) -> dict[str, Any]:
    before_path = Path(before_path)
    after_path = Path(after_path)
    before_bytes = before_path.read_bytes()
    after_bytes = after_path.read_bytes()
    before = read_sch_binary(before_path)
    after = read_sch_binary(after_path)
    layouts_match = (
        before.sch_version == after.sch_version
        and before.payload_offset == after.payload_offset
        and before.step_size == after.step_size
        and before.step_count == after.step_count
    )
    step_numbers_match = tuple(step.step_no for step in before.steps) == tuple(
        step.step_no for step in after.steps
    )
    compatible = layouts_match and step_numbers_match

    warnings = []
    if not layouts_match:
        warnings.append(
            "Layouts or step counts differ; step records were not aligned automatically."
        )
    elif not step_numbers_match:
        warnings.append(
            "Step number sequences differ; step records were not aligned automatically."
        )

    before_parsed_end = before.payload_offset + before.step_count * before.step_size
    after_parsed_end = after.payload_offset + after.step_count * after.step_size
    before_tail = before_bytes[before_parsed_end:]
    after_tail = after_bytes[after_parsed_end:]
    tail_ranges = _changed_ranges(before_tail, after_tail)
    if tail_ranges:
        warnings.append("Bytes after the parsed END record differ.")

    header_ranges = _changed_ranges(before.header, after.header)
    step_changes = []
    if compatible:
        for before_step, after_step in zip(before.steps, after.steps):
            ranges = _changed_ranges(before_step.record, after_step.record)
            if not ranges:
                continue
            step_changes.append(
                {
                    "step_no": before_step.step_no,
                    "before_type": before_step.step_type_code,
                    "after_type": after_step.step_type_code,
                    "changed_byte_count": sum(end - start for start, end in ranges),
                    "ranges": [
                        _range_payload(
                            before_step.record,
                            after_step.record,
                            start,
                            end,
                        )
                        for start, end in ranges
                    ],
                    "words": _changed_words(
                        before_step.record,
                        after_step.record,
                        ranges,
                        before.sch_version or 0,
                    ),
                }
            )

        changed_word_count = sum(len(change["words"]) for change in step_changes)
        if len(step_changes) != 1:
            warnings.append(
                "A controlled pair should change exactly one step; "
                f"found {len(step_changes)}."
            )
        if changed_word_count != 1:
            warnings.append(
                "A controlled pair should change exactly one aligned word; "
                f"found {changed_word_count}."
            )
        if header_ranges and step_changes:
            warnings.append(
                "Header bytes changed alongside the step payload; check for "
                "unrelated metadata drift."
            )
        for change in step_changes:
            if change["before_type"] != change["after_type"]:
                warnings.append(
                    f"Step {change['step_no']}: step type changed "
                    f"({change['before_type']} -> {change['after_type']})."
                )

    return {
        "schema": "pne_scheduler.sch_diff/v2",
        "before": {
            "path": str(before_path),
            "size": len(before_bytes),
            "sha256": _sha256(before_bytes),
            "version": f"0x{(before.sch_version or 0):08x}",
            "payload_offset": before.payload_offset,
            "step_size": before.step_size,
            "step_count": before.step_count,
            "parsed_end": before_parsed_end,
            "unparsed_size": len(before_tail),
        },
        "after": {
            "path": str(after_path),
            "size": len(after_bytes),
            "sha256": _sha256(after_bytes),
            "version": f"0x{(after.sch_version or 0):08x}",
            "payload_offset": after.payload_offset,
            "step_size": after.step_size,
            "step_count": after.step_count,
            "parsed_end": after_parsed_end,
            "unparsed_size": len(after_tail),
        },
        "compatible": compatible,
        "warnings": warnings,
        "header_changes": [
            _range_payload(before.header, after.header, start, end)
            for start, end in header_ranges
        ],
        "unparsed_tail_changes": [
            _range_payload(before_tail, after_tail, start, end)
            for start, end in tail_ranges
        ],
        "step_changes": step_changes,
        "summary": {
            "files_identical": before_bytes == after_bytes,
            "header_changed_byte_count": sum(
                end - start for start, end in header_ranges
            ),
            "changed_step_count": len(step_changes),
            "step_changed_byte_count": sum(
                change["changed_byte_count"] for change in step_changes
            ),
            "unparsed_changed_byte_count": sum(
                end - start for start, end in tail_ranges
            ),
            "controlled_pair_clean": compatible
            and len(step_changes) == 1
            and sum(len(change["words"]) for change in step_changes) == 1
            and not header_ranges
            and not tail_ranges,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare a controlled before/after SCH pair."
    )
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()

    report = compare_sch_files(args.before, args.after)
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(rendered, end="")
    return 0 if report["compatible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
