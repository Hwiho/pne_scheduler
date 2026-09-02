"""Analyze PNE01/PNE02 zip corpora: filename taxonomy + binary layout summary."""

from __future__ import annotations

import json
import re
import struct
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from pne_scheduler.classify import classify_schedule_filename
from pne_scheduler.io.layout import detect_sch_layout
from pne_scheduler.schema.ensol_v612 import (
    OFF_CURRENT_MA,
    OFF_CV_CUTOFF_MA,
    OFF_STEP_TYPE,
    OFF_TIME_OR_REST_S,
    OFF_VOLT_OR_VLIM_MV,
    OFF_VOLTAGE_CUTOFF_MV,
)
from pne_scheduler.schema.enums import (
    SCH_STEP_TYPE_CC_CHARGE,
    SCH_STEP_TYPE_CC_DISCHARGE,
    SCH_STEP_TYPE_CCCV,
    SCH_STEP_TYPE_END,
    SCH_STEP_TYPE_LOOP,
    SCH_STEP_TYPE_REST,
)

TYPE_NAMES = {
    int(SCH_STEP_TYPE_REST): "REST",
    int(SCH_STEP_TYPE_CCCV): "CCCV",
    int(SCH_STEP_TYPE_CC_CHARGE): "CC_CHG",
    int(SCH_STEP_TYPE_CC_DISCHARGE): "CC_DCHG",
    int(SCH_STEP_TYPE_LOOP): "LOOP",
    int(SCH_STEP_TYPE_END): "END",
}


def _read_f32(record: bytes, offset: int) -> float:
    return struct.unpack_from("<f", record, offset)[0]


def analyze_binary(data: bytes) -> dict:
    layout = detect_sch_layout(data)
    if layout is None:
        return {"error": "layout_unknown"}
    payload = layout.payload_offset
    step_size = layout.step_size
    version = struct.unpack_from("<I", data, 4)[0] if len(data) >= 8 else None
    steps: list[dict] = []
    index = 0
    while payload + index * step_size + 12 <= len(data):
        base = payload + index * step_size
        record = data[base : base + step_size]
        step_no = struct.unpack_from("<i", record, 0)[0]
        step_type = struct.unpack_from("<i", record, OFF_STEP_TYPE)[0] & 0xFFFF
        if step_no <= 0 or step_type not in TYPE_NAMES:
            break
        entry: dict = {
            "step_no": step_no,
            "type": TYPE_NAMES[step_type],
        }
        if step_type in (
            int(SCH_STEP_TYPE_CCCV),
            int(SCH_STEP_TYPE_CC_CHARGE),
            int(SCH_STEP_TYPE_CC_DISCHARGE),
        ):
            entry["V_mV"] = round(_read_f32(record, OFF_VOLT_OR_VLIM_MV), 3)
            entry["I_mA"] = round(_read_f32(record, OFF_CURRENT_MA), 4)
            entry["T_s"] = round(_read_f32(record, OFF_TIME_OR_REST_S), 3)
            if step_type == int(SCH_STEP_TYPE_CCCV):
                entry["CV_mA"] = round(_read_f32(record, OFF_CV_CUTOFF_MA), 4)
            if step_type == int(SCH_STEP_TYPE_CC_DISCHARGE):
                entry["endV_mV"] = round(_read_f32(record, OFF_VOLTAGE_CUTOFF_MV), 3)
        steps.append(entry)
        if step_type == int(SCH_STEP_TYPE_END):
            break
        index += 1

    type_counts = Counter(s["type"] for s in steps)
    first_cccv = next((s for s in steps if s["type"] == "CCCV"), None)
    first_ccdi = next((s for s in steps if s["type"] == "CC_DCHG"), None)
    return {
        "version_hex": f"0x{version:08x}" if version is not None else None,
        "payload_offset": payload,
        "step_size": step_size,
        "file_bytes": len(data),
        "step_count": len(steps),
        "type_counts": dict(type_counts),
        "first_cccv": first_cccv,
        "first_ccdi": first_ccdi,
    }


def filename_tokens(name: str) -> dict:
    stem = PurePosixPath(name).stem
    tokens: dict = {}
    m = re.search(r"(\d{8})_", stem)
    if m:
        tokens["date"] = m.group(1)
    m = re.search(r"_L([0-9.]+)", stem, re.I)
    if m:
        tokens["L_level"] = m.group(1)
    m = re.search(r"(\d+\.?\d*)\s*MPa", stem, re.I)
    if m:
        tokens["pressure_MPa"] = m.group(1)
    m = re.search(r"(\d+\.?\d*)\s*mAh", stem, re.I)
    if m:
        tokens["capacity_mAh"] = m.group(1)
    m = re.search(r"(\d+\.?\d*)\s*C", stem, re.I)
    if m:
        tokens["c_rate_hint"] = m.group(1)
    if re.search(r"derating", stem, re.I):
        tokens["protocol_hint"] = "derating"
    if re.search(r"\bFM\b|_FM|formation", stem, re.I):
        tokens["protocol_hint"] = "formation"
    if re.search(r"capacheck|capa[_ ]?check", stem, re.I):
        tokens["protocol_hint"] = "capacheck"
    if re.search(r"QPEED|qpeed", stem):
        tokens["protocol_hint"] = "qpeed"
    if re.search(r"HPPC|hppc", stem, re.I):
        tokens["protocol_hint"] = "hppc"
    if re.search(r"\bRPT\b|rpt", stem, re.I):
        tokens["protocol_hint"] = "rpt"
    if re.search(r"cycle", stem, re.I):
        tokens["protocol_hint"] = tokens.get("protocol_hint") or "cycle"
    return tokens


def analyze_zip(zip_path: Path, *, sample_per_category: int = 2) -> dict:
    report: dict = {
        "zip": zip_path.name,
        "sch_count": 0,
        "categories": Counter(),
        "qpeed_variants": Counter(),
        "filename_tokens": Counter(),
        "layout_signatures": Counter(),
        "parse_errors": 0,
        "samples_by_category": defaultdict(list),
        "representative": [],
    }
    with zipfile.ZipFile(zip_path) as zf:
        sch_names = sorted(n for n in zf.namelist() if n.lower().endswith(".sch"))
        report["sch_count"] = len(sch_names)

        for name in sch_names:
            match = classify_schedule_filename(name)
            cat = match.category.value
            report["categories"][cat] += 1
            if match.qpeed_variant:
                report["qpeed_variants"][match.qpeed_variant.value] += 1

            for key, val in filename_tokens(name).items():
                report["filename_tokens"][f"{key}={val}"] += 1

            # sample binary for diversity
            bucket = cat
            if len(report["samples_by_category"][bucket]) >= sample_per_category:
                continue
            try:
                data = zf.read(name)
                binfo = analyze_binary(data)
                if "error" in binfo:
                    report["parse_errors"] += 1
                    continue
                sig = f"{binfo['version_hex']}/{binfo['step_size']}B/{binfo['step_count']}steps"
                report["layout_signatures"][sig] += 1
                report["samples_by_category"][bucket].append(
                    {
                        "path": name,
                        "filename_tokens": filename_tokens(name),
                        "classify": {
                            "category": cat,
                            "qpeed_variant": (
                                match.qpeed_variant.value if match.qpeed_variant else None
                            ),
                            "confidence": match.confidence,
                        },
                        "binary": binfo,
                    }
                )
            except Exception:
                report["parse_errors"] += 1

        # full layout scan on subset for PNE02 (too many files)
        layout_scan_limit = 500 if len(sch_names) > 200 else len(sch_names)
        layout_counter: Counter = Counter()
        version_counter: Counter = Counter()
        step_size_counter: Counter = Counter()
        for name in sch_names[:layout_scan_limit]:
            try:
                data = zf.read(name)
                binfo = analyze_binary(data)
                if "error" in binfo:
                    continue
                layout_counter[f"{binfo['version_hex']}/{binfo['step_size']}"] += 1
                if binfo["version_hex"]:
                    version_counter[binfo["version_hex"]] += 1
                step_size_counter[binfo["step_size"]] += 1
            except Exception:
                pass
        report["layout_scan"] = {
            "files_scanned": layout_scan_limit,
            "by_version_step_size": dict(layout_counter),
            "versions": dict(version_counter),
            "step_sizes": dict(step_size_counter),
        }

    report["categories"] = dict(report["categories"])
    report["qpeed_variants"] = dict(report["qpeed_variants"])
    report["filename_tokens"] = dict(
        sorted(report["filename_tokens"].items(), key=lambda x: -x[1])[:40]
    )
    report["layout_signatures"] = dict(report["layout_signatures"])
    report["samples_by_category"] = dict(report["samples_by_category"])
    return report


def main() -> None:
    zips = [Path(r"c:\PNE01.zip"), Path(r"c:\PNE02.zip")]
    out_dir = ROOT / "example" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for zp in zips:
        if not zp.is_file():
            print("missing", zp)
            continue
        print("Analyzing", zp.name, "...")
        results[zp.stem] = analyze_zip(zp, sample_per_category=3)
    out_path = out_dir / "pne01_pne02_zip_analysis.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", out_path)
    for key, rep in results.items():
        print(f"\n## {key}: {rep['sch_count']} sch files")
        print(" categories:", rep["categories"])
        print(" layout scan:", rep.get("layout_scan"))


if __name__ == "__main__":
    main()
