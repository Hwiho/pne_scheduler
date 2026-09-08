"""Mine secured fixtures for OCV / Impedance / Balance / Pattern step layouts."""

from __future__ import annotations

import json
import struct
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEARCH_ROOTS = [
    ROOT / "example" / "fixtures",
    ROOT / "example" / "gate_b_pairs",
]

TYPE_NAMES = {
    3: "REST",
    4: "OCV",
    5: "IMPEDANCE",
    6: "END",
    7: "CYCLE",
    8: "LOOP",
    9: "PATTERN",
    10: "BALANCE",
    257: "CCCV",
    513: "CC_CHARGE",
    514: "CC_DISCHARGE",
}

TARGET_TYPES = {4, 5, 9, 10}


def _iter_sch_paths() -> list[Path]:
    paths: list[Path] = []
    for root in SEARCH_ROOTS:
        if root.exists():
            paths.extend(root.rglob("*.sch"))
    return paths


def _detect_layout(data: bytes) -> tuple[int, int, int] | None:
    for payload_off, step_size in ((1760, 612), (1760, 696), (1844, 696), (1632, 612)):
        rem = len(data) - payload_off
        if rem <= 0 or rem % step_size != 0:
            continue
        nsteps = rem // step_size
        if 1 <= nsteps <= 500:
            return payload_off, step_size, nsteps
    return None


def _nonzero_floats(record: bytes, limit: int = 128) -> list[tuple[int, float]]:
    out: list[tuple[int, float]] = []
    for off in range(0, min(limit, len(record) - 3), 4):
        value = struct.unpack_from("<f", record, off)[0]
        if abs(value) > 1e-6:
            out.append((off, round(value, 6)))
    return out


def main() -> None:
    counts: Counter[int] = Counter()
    samples: dict[int, list[dict]] = defaultdict(list)

    for path in _iter_sch_paths():
        data = path.read_bytes()
        layout = _detect_layout(data)
        if layout is None:
            continue
        payload_off, step_size, nsteps = layout
        version = struct.unpack_from("<I", data, 4)[0]
        for index in range(nsteps):
            start = payload_off + index * step_size
            record = data[start : start + step_size]
            step_type = struct.unpack_from("<I", record, 8)[0]
            counts[step_type] += 1
            if step_type not in TARGET_TYPES or len(samples[step_type]) >= 5:
                continue
            samples[step_type].append(
                {
                    "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "step_no": index + 1,
                    "version": hex(version),
                    "step_size": step_size,
                    "type_bytes": record[8:16].hex(),
                    "volt_or_vlim_mV": struct.unpack_from("<f", record, 12)[0],
                    "current_mA": struct.unpack_from("<f", record, 16)[0],
                    "time_s": struct.unpack_from("<f", record, 20)[0],
                    "endV_mV": struct.unpack_from("<f", record, 28)[0],
                    "endI_mA": struct.unpack_from("<f", record, 32)[0],
                    "record_dV_mV": (
                        struct.unpack_from("<f", record, 332)[0] if step_size > 336 else None
                    ),
                    "record_time_s": (
                        struct.unpack_from("<f", record, 340)[0] if step_size > 344 else None
                    ),
                    "nonzero_floats_0_128": _nonzero_floats(record),
                }
            )

    report = {
        "type_counts": {
            TYPE_NAMES.get(key, str(key)): count for key, count in counts.most_common()
        },
        "target_samples": {
            TYPE_NAMES.get(key, str(key)): values for key, values in sorted(samples.items())
        },
        "notes": [
            "Type codes match schema/enums.py StepType (OCV=4, IMPEDANCE=5, PATTERN=9, BALANCE=10).",
            "Field meaning beyond type code is corpus_inferred until controlled pairs exist.",
            "Shared Ensol prefix offsets (+12/+16/+20/+28/+32/+332/+340) are reused when nonzero.",
        ],
    }
    out = ROOT / "planning" / "STEP_TYPES_OCV_IMP_BALANCE.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("wrote", out)
    print("target sample counts:", {k: len(v) for k, v in report["target_samples"].items()})
    for name, values in report["target_samples"].items():
        print(name, "n=", len(values))
        if values:
            print("  first", values[0]["file"], "t=", values[0]["time_s"], "I=", values[0]["current_mA"])


if __name__ == "__main__":
    main()
