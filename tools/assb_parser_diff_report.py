"""Generate ASSB vs internal parser divergence report (Gate B)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from pne_scheduler.tools.compare_step_layouts import (
    build_step_layout_diff_report,
    render_step_layout_diff_markdown,
)
from pne_scheduler.validate.assb_parser_diff import (
    build_assb_parser_diff_report,
    render_assb_parser_diff_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "example" / "fixtures" / "catalog.json"
FIXTURE_ROOT = ROOT / "example" / "fixtures"
DOCS_OUT = ROOT / "docs" / "GATE_B_GENERATED.md"
JSON_OUT = ROOT / "example" / "reports" / "assb_parser_diff.json"


def _representative_fixtures() -> list[Path]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    picks: list[Path] = []
    seen_categories: set[str] = set()
    for item in catalog["fixtures"]:
        category = item["category"]
        if category in seen_categories:
            continue
        path = FIXTURE_ROOT / Path(item["path"])
        if path.exists():
            picks.append(path)
            seen_categories.add(category)
    hppc = FIXTURE_ROOT / "hppc" / "HPPC_Full range.sch"
    if hppc.exists():
        picks.append(hppc)
    return picks


def main() -> int:
    fixtures = _representative_fixtures()
    report = build_assb_parser_diff_report(fixtures)
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    layout_md = render_step_layout_diff_markdown(build_step_layout_diff_report()).replace(
        "# 612 vs 696", "## 612 vs 696", 1
    )
    assb_md = render_assb_parser_diff_markdown(report).replace("# ASSB vs", "## ASSB vs", 1)
    combined = (
        "# Gate B — auto-generated annex\n\n"
        "Regenerate: `python tools/assb_parser_diff_report.py`\n\n"
        f"{layout_md.strip()}\n\n---\n\n{assb_md.strip()}\n"
    )
    DOCS_OUT.write_text(combined, encoding="utf-8")
    print(f"Wrote {JSON_OUT}")
    print(f"Wrote {DOCS_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
