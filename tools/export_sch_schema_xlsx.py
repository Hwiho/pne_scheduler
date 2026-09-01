"""Export PNE official SCH structure workbook to JSON for tooling."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

_REF = Path(__file__).resolve().parent.parent / "schema" / "reference"
DEFAULT_XLSX = _REF / "sch_file_structure_20250211.xlsx"
DEFAULT_OUT = _REF / "sch_file_structure_20250211.json"

_FIELD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*;?\s*$")


def _clean_name(raw: str) -> str | None:
    raw = raw.strip()
    if not raw:
        return None
    m = _FIELD_RE.match(raw)
    return m.group(1) if m else None


def _parse_sheet(df: pd.DataFrame) -> dict:
    sections: list[dict] = []
    current: dict | None = None
    offset = 0

    for _, row in df.iterrows():
        cells = [str(x).strip() if pd.notna(x) else "" for x in row]
        section_label = cells[1] if len(cells) > 1 else ""
        repeat = cells[2] if len(cells) > 2 else ""
        dtype = cells[3] if len(cells) > 3 else ""
        field_raw = cells[4] if len(cells) > 4 else ""

        if section_label and section_label not in {"nan"}:
            if current:
                current["size_bytes"] = offset - current["offset_start"]
                sections.append(current)
            current = {
                "name": section_label,
                "repeat": repeat or None,
                "offset_start": offset,
                "fields": [],
            }

        name = _clean_name(field_raw)
        if not name or current is None:
            continue

        size = _dtype_size(dtype, name)
        field = {
            "name": name,
            "offset": offset,
            "dtype": dtype or None,
            "size": size,
        }
        current["fields"].append(field)
        offset += size

    if current:
        current["size_bytes"] = offset - current["offset_start"]
        sections.append(current)

    step = next((s for s in sections if s["name"] == "FILE_STEP_CONDITION"), None)
    return {
        "sections": sections,
        "step_record_size": step["size_bytes"] if step else None,
        "step_field_count": len(step["fields"]) if step else 0,
    }


def _dtype_size(dtype: str, name: str) -> int:
    dtype = dtype.upper()
    if "CHAR" in dtype and "[" in name:
        m = re.search(r"\[(\d+)\]", name)
        return int(m.group(1)) if m else 1
    if dtype in {"BYTE", "CHAR", "BOOL"}:
        return 1
    if dtype == "WORD":
        return 2
    if dtype in {"UINT", "INT", "LONG", "FLOAT"}:
        return 4
    if dtype == "DOUBLE":
        return 8
    return 4


def export_workbook(xlsx: Path, out: Path) -> dict:
    xl = pd.ExcelFile(xlsx)
    layouts = {}
    for sheet in xl.sheet_names:
        df = pd.read_excel(xlsx, sheet_name=sheet, header=None)
        layouts[sheet] = _parse_sheet(df)

    payload = {
        "source": xlsx.name,
        "source_note": "PNE official SCH file structure specification (2025-02-11).",
        "layouts": layouts,
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    payload = export_workbook(args.xlsx, args.output)
    for sheet, layout in payload["layouts"].items():
        print(
            f"{sheet}: step_size={layout['step_record_size']} "
            f"fields={layout['step_field_count']}"
        )
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
