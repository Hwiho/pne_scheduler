"""Inspect .sch files in the capacheck example zip."""

from __future__ import annotations

import json
import struct
import zipfile
from pathlib import Path

from pne_scheduler.schema.fields import (
    OFFSET_F_END_C,
    OFFSET_F_END_I,
    OFFSET_F_END_V,
)

ROOT = Path(__file__).resolve().parents[1]
ZIP_PATH = ROOT / "example" / "archives" / "9)Bimodal_SJ1300_6040_NCN_capacheck.zip"
OUT_DIR = ROOT / "example" / "fixtures" / "capacheck_zip"

SCH_STEP_TYPES = {3, 0x0101, 0x0201, 0x0202, 6, 7, 8}
TYPE_NAMES = {
    1: "CHARGE",
    2: "DISCHARGE",
    3: "REST",
    4: "OCV",
    5: "IMP",
    6: "END",
    7: "CYCLE",
    8: "LOOP",
    0x0101: "CCCV",
    0x0201: "CC_CHG",
    0x0202: "CC_DCHG",
}


def detect_layout(data: bytes) -> tuple[int, int] | None:
    best: tuple[int, int, int] | None = None
    scan_limit = min(len(data) - 12, 5000)
    for payload_offset in range(0, scan_limit, 4):
        if len(data) < payload_offset + 12:
            break
        step_no = struct.unpack_from("<i", data, payload_offset)[0]
        step_type = struct.unpack_from("<i", data, payload_offset + 8)[0] & 0xFFFF
        if step_no != 1 or step_type not in SCH_STEP_TYPES:
            continue
        for step_size in (612, 696):
            score = 0
            for expected in range(1, 8):
                base = payload_offset + (expected - 1) * step_size
                if base + 12 > len(data):
                    break
                sn = struct.unpack_from("<i", data, base)[0]
                st = struct.unpack_from("<i", data, base + 8)[0] & 0xFFFF
                if sn == expected and st in SCH_STEP_TYPES:
                    score += 1
            if best is None or score > best[0]:
                best = (score, payload_offset, step_size)
    if best is None or best[0] < 3:
        return None
    return best[1], best[2]


def read_steps(data: bytes, payload_offset: int, step_size: int) -> list[dict]:
    steps: list[dict] = []
    index = 0
    while payload_offset + index * step_size + 12 <= len(data):
        base = payload_offset + index * step_size
        step_no = struct.unpack_from("<i", data, base)[0]
        step_type = struct.unpack_from("<i", data, base + 8)[0] & 0xFFFF
        if step_no <= 0 or step_type not in SCH_STEP_TYPES:
            break
        steps.append(
            {
                "step_no": step_no,
                "type": TYPE_NAMES.get(step_type, hex(step_type)),
                "fVref": round(struct.unpack_from("<f", data, base + 16)[0], 4),
                "fIref": round(struct.unpack_from("<f", data, base + 20)[0], 4),
                "fEndTime": round(struct.unpack_from("<f", data, base + 24)[0], 2),
                "fEndV": round(
                    struct.unpack_from("<f", data, base + OFFSET_F_END_V)[0], 4
                ),
                "fEndI": round(
                    struct.unpack_from("<f", data, base + OFFSET_F_END_I)[0], 4
                ),
                "fEndC": round(
                    struct.unpack_from("<f", data, base + OFFSET_F_END_C)[0], 4
                ),
            }
        )
        if step_type == 6:
            break
        index += 1
    return steps


from pne_scheduler.classify import classify_schedule_filename


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary: list[dict] = []

    with zipfile.ZipFile(ZIP_PATH) as zf:
        for info in zf.infolist():
            name = info.filename
            data = zf.read(name)
            dest = OUT_DIR / Path(name).name
            dest.write_bytes(data)

            layout = detect_layout(data)
            steps = []
            if layout:
                steps = read_steps(data, layout[0], layout[1])

            version = struct.unpack_from("<I", data, 4)[0] if len(data) >= 8 else None
            match = classify_schedule_filename(name)
            entry = {
                "filename": Path(name).name,
                "category": match.category.value,
                "qpeed_variant": (
                    match.qpeed_variant.value if match.qpeed_variant is not None else None
                ),
                "bytes": len(data),
                "sch_version": hex(version) if version is not None else None,
                "payload_offset": layout[0] if layout else None,
                "step_size": layout[1] if layout else None,
                "step_count": len(steps),
                "topology": [f"{s['step_no']}:{s['type']}" for s in steps],
                "steps": steps,
            }
            summary.append(entry)
            print(f"=== {entry['filename']}")
            print(f"  category: {match.category.value}", end="")
            if match.qpeed_variant is not None:
                print(f" ({match.qpeed_variant.value})", end="")
            print()
            print(f"  version: {entry['sch_version']}  steps: {len(steps)}  size: {layout}")
            print(f"  topology: {' -> '.join(entry['topology'][:25])}")

    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote {manifest_path}")


if __name__ == "__main__":
    main()
