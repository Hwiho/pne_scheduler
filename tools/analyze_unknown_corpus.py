"""Scan unknown SCH filenames across all PNE unit zips."""

from __future__ import annotations

import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from pne_scheduler.classify import ScheduleCategory, classify_schedule_filename

DEFAULT_ZIPS: dict[str, Path] = {
    "PNE01": Path(r"c:\PNE01.zip"),
    "PNE02": Path(r"c:\PNE02.zip"),
    "PNE03": Path(r"c:\PNE03.zip"),
    "PNE04": Path(r"c:\PNE04.zip"),
    "PNE05": Path(r"c:\PNE05.zip"),
    "PNE22": Path(r"c:\PNE22.zip"),
}

RULE_CANDIDATES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("ch_dch_token", re.compile(r"\bCH\b|\bDCH\b|_CH_|_DCH_|\bCH\s|\bDCH\s", re.I), "charge/discharge"),
    ("c_rate_token", re.compile(r"[\d.]+'?\s*C\b", re.I), "rate_or_cycle"),
    ("initial_check", re.compile(r"initial[_\s-]*check|init[_\s-]*check", re.I), "capacheck"),
    ("capa_check", re.compile(r"capa[_\s-]*check|capcheck|capacity[_\s-]*check", re.I), "capacheck"),
    ("aging", re.compile(r"\baging\b|ageing", re.I), "storage"),
    ("swelling", re.compile(r"swell|breathing", re.I), "cycle_or_doe"),
    ("pulse", re.compile(r"\bpulse\b|pluse", re.I), "hppc_or_dcir"),
    ("preheat", re.compile(r"preheat|pre.?heat|preheating", re.I), "rest"),
    ("xrm", re.compile(r"\bxrm\b", re.I), "charge"),
    ("lt_profile", re.compile(r"LT\d+C", re.I), "cycle_life"),
    ("std_ref", re.compile(r"\bstd\b|standardiz", re.I), "rpt"),
    ("soc_only", re.compile(r"SOC\s*\d+", re.I), "soc_setting"),
    ("stack_mono", re.compile(r"\bstack\b|\bmono\b|\d+stack", re.I), "project"),
    ("copy_of", re.compile(r"^copy of", re.I), "duplicate"),
    ("wip", re.compile(r"\bwip\b", re.I), "project"),
    ("cip", re.compile(r"\bcip\d*\b", re.I), "formation?"),
    ("cont_cycle", re.compile(r"\bcont\b", re.I), "cycle_life"),
    ("sop", re.compile(r"\bsop\b", re.I), "formation"),
    ("cross_pct", re.compile(r"cross\d+%", re.I), "doe"),
)


def scan_unknown(zip_map: dict[str, Path] | None = None) -> dict:
    zip_map = zip_map or DEFAULT_ZIPS
    per_unit: dict[str, dict] = {}
    all_unknown: list[str] = []
    hits: Counter = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    unmatched: list[str] = []

    for unit, zp in sorted(zip_map.items()):
        if not zp.is_file():
            per_unit[unit] = {"error": "missing"}
            continue
        unknown: list[str] = []
        with zipfile.ZipFile(zp) as zf:
            for name in zf.namelist():
                if not name.lower().endswith(".sch"):
                    continue
                if classify_schedule_filename(name).category != ScheduleCategory.UNKNOWN:
                    continue
                stem = PurePosixPath(name).name
                unknown.append(stem)
                all_unknown.append(stem)

        per_unit[unit] = {"unknown_count": len(unknown)}
        for stem in unknown:
            matched = False
            for label, pattern, _ in RULE_CANDIDATES:
                if pattern.search(stem):
                    hits[label] += 1
                    if len(examples[label]) < 4:
                        examples[label].append(stem)
                    matched = True
                    break
            if not matched and len(unmatched) < 200:
                unmatched.append(stem)

    return {
        "total_unknown": len(all_unknown),
        "per_unit": per_unit,
        "rule_hits": dict(hits.most_common()),
        "examples": dict(examples),
        "unmatched_sample": unmatched[:80],
    }


def main() -> None:
    report = scan_unknown()
    out = ROOT / "planning" / "UNKNOWN_FILENAME_ANALYSIS.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    print("total unknown:", report["total_unknown"])
    for unit, data in report["per_unit"].items():
        print(unit, data.get("unknown_count", data.get("error")))
    print("top hits:")
    for k, v in list(report["rule_hits"].items())[:20]:
        print(f"  {v:4d} {k}")


if __name__ == "__main__":
    main()
