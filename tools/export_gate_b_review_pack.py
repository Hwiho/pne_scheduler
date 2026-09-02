"""One-off export for Gate B user review."""
from __future__ import annotations

import json
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "example" / "gate_b_export"
PPT = Path(r"c:\260721_황화물전고체전지1PJT_PNE version.pptx")
CATALOG = ROOT / "example" / "fixtures" / "catalog.json"
FIXTURES = ROOT / "example" / "fixtures"


def extract_ppt_text(path: Path) -> list[tuple[int, list[str]]]:
    slides_out: list[tuple[int, list[str]]] = []
    with zipfile.ZipFile(path) as z:
        names = sorted(
            [n for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")],
            key=lambda s: int(re.search(r"slide(\d+)", s).group(1)),
        )
        for index, name in enumerate(names, start=1):
            root = ET.fromstring(z.read(name))
            lines = [
                t.text.strip()
                for t in root.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}t")
                if t.text and t.text.strip()
            ]
            slides_out.append((index, lines))
    return slides_out


def parse_pne_rows(lines: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    i = 0
    while i < len(lines):
        token = lines[i]
        if token == "PNE" and i + 1 < len(lines):
            unit_id = lines[i + 1]
            rest = lines[i + 2 : i + 6]
            detail = " ".join(rest).strip()
            rows.append({"unit": f"PNE {unit_id}", "detail": detail})
            i += 2
            continue
        if token.startswith("PNE ") and len(token) > 4:
            unit = token
            detail = " ".join(lines[i + 1 : i + 5]).strip()
            rows.append({"unit": unit, "detail": detail})
            i += 1
            continue
        i += 1
    return rows


def recommend_fixtures(catalog: dict) -> list[dict]:
    picks: list[dict] = []
    criteria = [
        ("formation", "612-byte formation (8-file archive)", lambda f: f["category"] == "formation" and f["layout"]["step_size"] == 612, 1),
        ("formation", "696-byte formation (lab dominant)", lambda f: f["category"] == "formation" and f["layout"]["step_size"] == 696, 1),
        ("cycle_life", "short cycle life (easy to read)", lambda f: f["category"] == "cycle_life" and f["layout"]["step_count"] <= 40, 2),
        ("cycle_life", "long cycle life (loop stress)", lambda f: f["category"] == "cycle_life" and f["layout"]["step_count"] >= 60, 1),
        ("rpt", "RPT schedule", lambda f: f["category"] == "rpt", 2),
        ("capacheck", "612-byte capacheck (B0 unit probe)", lambda f: "capacheck" in f["path"] and f["layout"]["step_size"] == 612, 1),
        ("capacheck", "696-byte capacheck", lambda f: "capacheck" in f["path"] and f["layout"]["step_size"] == 696, 1),
        ("qpeed", "QPEED (fast charge / L-level fVref)", lambda f: f["category"] == "qpeed", 2),
        ("hppc", "HPPC full range", lambda f: "hppc" in f["path"].lower(), 1),
        ("unknown", "696 unknown (lab bulk format)", lambda f: f["category"] == "unknown" and f["layout"]["step_size"] == 696, 2),
    ]
    used: set[str] = set()
    fixtures = catalog["fixtures"]
    for _, reason, pred, limit in criteria:
        matches = [f for f in fixtures if pred(f) and f["path"] not in used]
        matches.sort(key=lambda f: (f["layout"]["step_count"], f["path"]))
        for item in matches[:limit]:
            used.add(item["path"])
            picks.append(
                {
                    "reason": reason,
                    "path": item["path"],
                    "category": item["category"],
                    "version": item["layout"]["version"],
                    "step_count": item["layout"]["step_count"],
                    "step_size": item["layout"]["step_size"],
                    "equipment": item["equipment_provenance"].get("equipment"),
                    "equipment_confidence": item["equipment_provenance"].get("confidence"),
                }
            )
    return picks


def main() -> None:
    EXPORT.mkdir(parents=True, exist_ok=True)
    sch_dir = EXPORT / "recommended_sch"
    sch_dir.mkdir(exist_ok=True)

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    picks = recommend_fixtures(catalog)

    # PPT summary
    ppt_lines: list[str] = ["# PNE version notes (from PowerPoint)", ""]
    if PPT.exists():
        for slide_no, lines in extract_ppt_text(PPT):
            ppt_lines.append(f"## Slide {slide_no}")
            ppt_lines.append("")
            for line in lines:
                ppt_lines.append(f"- {line}")
            parsed = parse_pne_rows(lines)
            if parsed:
                ppt_lines.append("")
                ppt_lines.append("| Unit | Detail |")
                ppt_lines.append("|------|--------|")
                for row in parsed:
                    ppt_lines.append(f"| {row['unit']} | {row['detail']} |")
            ppt_lines.append("")
    else:
        ppt_lines.append("_PowerPoint file not found at expected path._")

    (EXPORT / "PNE_VERSION_FROM_PPT.md").write_text("\n".join(ppt_lines), encoding="utf-8")

    # Structured equipment table (best-effort from slide 1-2)
    equipment_rows = [
        {"unit": "PNE 2", "current_range": "500 mA", "software": "CYCC-1004-S01-R004-N01"},
        {"unit": "PNE 4", "current_range": "500 mA", "software": "CYCC-1004-S01-R004-N01"},
        {"unit": "PNE 5", "current_range": "500 mA", "software": "CYCC-1006-S01-R004-N01"},
        {"unit": "PNE 11", "current_range": "500 mA", "software": "CYCC-1006-S01-R006-N01 (CTSMonPro GUI)"},
        {"unit": "PNE 19", "current_range": "6 A", "software": "CYCGN-P1107-S01-R001-N026"},
        {"unit": "PNE 22", "current_range": "100 mA", "software": "CYCC-1004-S01-R004-N01"},
        {"unit": "PNE 23", "current_range": "100 mA", "software": "CYCC-1004-S01-R002-N01 (CTSMonPro GUI)"},
        {"unit": "PNE 24-1", "current_range": "100 mA", "software": "CYCC-1004-S01-R004-N01"},
        {"unit": "PNE 24-2", "current_range": "100 mA", "software": "CYCC-1004-S01-R004-N01"},
        {"unit": "PNE 25", "current_range": "6 A", "software": "CYCC-1004-S01-R004-N01"},
        {"unit": "PNE 30", "current_range": "6 A", "software": "CYCGN-P1107-S01-R001-N026 (CTSMonPro GUI)"},
        {"unit": "PNE 21", "current_range": "100 mA (ASSB 3PJT)", "software": "CYCC-1004-S01-R004-N01 (CTSMonPro GUI)"},
        {"unit": "PNE 16", "current_range": "6 A (ASSB 3PJT)", "software": "_see slide 3_"},
        {"unit": "PNE 12", "current_range": "10, 20 A (ASSB 3PJT)", "software": "_see slide 4_"},
        {"unit": "PNE 8", "current_range": "500 mA / 20 A", "software": "_see slide 5_"},
        {"unit": "PNE 3 / 17", "current_range": "6, 10 A", "software": "_see slide 6_"},
    ]
    (EXPORT / "PNE_EQUIPMENT_TABLE.json").write_text(
        json.dumps(equipment_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Recommendations markdown
    rec_lines = [
        "# Gate B — recommended golden fixture candidates",
        "",
        "Pick the files you recognize from lab practice. We will use your choices as semantic golden references.",
        "",
        "| # | Why | File | Format | Steps | Equipment (catalog) |",
        "|---|-----|------|--------|-------|---------------------|",
    ]
    for index, pick in enumerate(picks, start=1):
        name = pick["path"].split("/")[-1]
        rec_lines.append(
            f"| {index} | {pick['reason']} | `{name}` | "
            f"{pick['version']}/{pick['step_size']}B | {pick['step_count']} | "
            f"{pick['equipment'] or 'unknown'} ({pick['equipment_confidence']}) |"
        )
    rec_lines.extend(
        [
            "",
            "## Full paths",
            "",
        ]
    )
    for index, pick in enumerate(picks, start=1):
        rec_lines.append(f"{index}. `{pick['path']}`")
    (EXPORT / "GOLDEN_FIXTURE_CANDIDATES.md").write_text("\n".join(rec_lines), encoding="utf-8")
    (EXPORT / "GOLDEN_FIXTURE_CANDIDATES.json").write_text(
        json.dumps(picks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Copy SCH files
    copied: list[str] = []
    for pick in picks:
        src = FIXTURES / pick["path"].replace("/", "\\")
        if not src.exists():
            # try forward slashes on Windows
            src = FIXTURES / Path(pick["path"])
        if not src.exists():
            continue
        dst = sch_dir / src.name
        shutil.copy2(src, dst)
        copied.append(src.name)

    # Gate B docs (canonical copies live under docs/ and planning/)
    gate_b_doc = (ROOT / "docs" / "GATE_B.md").read_text(encoding="utf-8")
    (EXPORT / "README.md").write_text(
        "# Gate B export pack\n\n"
        "Canonical documentation (do not fork — edit these paths):\n\n"
        "- [`docs/GATE_B.md`](../../docs/GATE_B.md) — validation intake, Q_nom, ASSB\n"
        "- [`docs/GATE_B_GENERATED.md`](../../docs/GATE_B_GENERATED.md) — auto-generated annex\n"
        "- [`planning/GOLDEN_FIXTURES.md`](../../planning/GOLDEN_FIXTURES.md) — locked golden set\n"
        "- [`planning/EQUIPMENT_CTS_FROM_PPT.md`](../../planning/EQUIPMENT_CTS_FROM_PPT.md) — CTS builds from PPT\n\n"
        "Fillable intake form: [`GOLDEN_FIXTURE_INTAKE.md`](GOLDEN_FIXTURE_INTAKE.md)\n\n"
        "---\n\n"
        + gate_b_doc,
        encoding="utf-8",
    )

    manifest = {
        "export_dir": str(EXPORT),
        "ppt_source": str(PPT),
        "copied_sch_count": len(copied),
        "copied_sch_files": copied,
        "candidate_count": len(picks),
    }
    (EXPORT / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
