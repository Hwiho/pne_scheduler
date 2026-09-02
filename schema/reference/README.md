# PNE official `.sch` structure reference

Canonical field layout source from PNE (2025-02-11).

| File | Description |
|------|-------------|
| [`sch_file_structure_20250211.xlsx`](sch_file_structure_20250211.xlsx) | Original workbook |
| [`sch_file_structure_20250211.json`](sch_file_structure_20250211.json) | Machine-readable export (regenerate below) |

## Sheets / versions

| Sheet | `nFileVersion` | Step fields (official) |
|-------|----------------|------------------------|
| `0x00010003` | 65539 | Primary ASSB target (`step_size=612` in corpus) |
| `0x00010004` | 65540 | Dominant lab archive layout (`step_size=696`) |
| `0x00010007` | 65543 | Latest (+ EIS `stEISSet`) |
| `0x00010002` | 65538 | Legacy |
| `Type1/Type2 0x00010001` | 65537 | Legacy Type1/Type2 |

## Regenerate JSON

```powershell
python pne_scheduler/tools/export_sch_schema_xlsx.py
```

## How this repo uses it

- `schema/fields.py` — evidence-qualified offsets used by parser/writer (may lag Excel until validated against fixtures + controlled pairs)
- `docs/GATE_B.md` — before/after `.sch` pairs to promote field confidence
- `planning/ROADMAP.md` Gate B — schema as single source of truth

> **Note:** Excel column order defines logical struct layout. Actual on-disk byte offsets must still be verified against real `.sch` fixtures and CTSPro-controlled pairs.
