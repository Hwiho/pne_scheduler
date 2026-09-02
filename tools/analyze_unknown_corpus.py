"""Scan unknown SCH filenames across all PNE unit zips (legacy summary; see categorize_unknown_sch)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from pne_scheduler.classify.unknown_categorize import build_report  # noqa: E402
from pne_scheduler.schema.corpus_paths import default_corpus_zip_map  # noqa: E402


def main() -> None:
    zip_map = default_corpus_zip_map()
    report = build_report(zip_map)
    legacy = {
        "total_unknown": report["total_unknown"],
        "per_unit": {
            unit: {"unknown_count": detail["unknown_count"]}
            for unit, detail in report["per_unit"].items()
        },
        "resolved_suggestions": report["resolved_suggestions"],
        "resolved_pct": report["resolved_pct"],
        "suggested_categories_all": report["suggested_categories_all"],
        "top_clusters": report["top_clusters"][:20],
        "rule_hits": {
            c["rule_name"]: c["count"]
            for c in report.get("rule_promotion_candidates", [])
            if "rule_name" in c
        },
    }
    out = ROOT / "planning" / "UNKNOWN_FILENAME_ANALYSIS.json"
    out.write_text(json.dumps(legacy, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    print("total unknown:", legacy["total_unknown"], "| resolved:", legacy["resolved_pct"], "%")


if __name__ == "__main__":
    main()
