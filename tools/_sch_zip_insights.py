import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "example" / "analysis" / "insights_full.txt"
data = json.loads(
    (Path(__file__).resolve().parents[1] / "example" / "analysis" / "sch_zip_report.json").read_text(
        encoding="utf-8"
    )
)
files = data["files"]
lines: list[str] = []

lines.append("=== ALL FILES BY CATEGORY ===")
by_cat: dict[str, list] = {}
for f in files:
    by_cat.setdefault(f["category"], []).append(f)
for cat, grp in sorted(by_cat.items()):
    lines.append(f"\n## {cat} ({len(grp)})")
    for f in sorted(grp, key=lambda x: x["filename"]):
        lines.append(
            f"  {f['filename']}"
            f" | steps={f['step_count']} | L={f['l_label']} | maxI={f['max_current_mA']:.0f}"
            f" | C={','.join(f['c_rate_labels'][:4])}"
        )

lines.append("\n=== FORMATION (FM) ===")
for f in files:
    if f["category"] == "formation" or "FM" in f["filename"]:
        lines.append(f"  {f['filename']} | steps={f['step_count']} | C={f['c_rate_labels']}")

lines.append("\n=== EXPLICIT L FILES ===")
for f in files:
    if "L4.3" in f["filename"] or "L5.0" in f["filename"] or "L5.6" in f["filename"] or "Monocell" in f["filename"]:
        lines.append(f"  {f['filename']} | inferred L={f['l_label']} src={f['l_source']}")

lines.append("\n=== SMALL SCHEDULES (<=7 steps) ===")
for f in sorted([x for x in files if x["step_count"] <= 7], key=lambda x: x["step_count"]):
    lines.append(f"  {f['filename']} | steps={f['step_count']} | {f['c_rate_labels']}")

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote {OUT}")
