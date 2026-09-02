# PNE unit corpus zips

Per-cycler `.sch` archives for lab corpus analysis (`planning/LAB_DATA_POLICY.md`).

| File | Unit | Notes |
|------|------|-------|
| `PNE01.zip` … `PNE09.zip`, `PNE22.zip` | PNE## | Filename must be exactly `PNE##.zip` |

## Usage

Tools resolve zips in this order:

1. `example/corpus_zips/PNE##.zip` (in-repo, CI/cloud)
2. `c:\PNE##.zip` or `$PNE_CORPUS_ZIP_DIR/PNE##.zip` (lab PC)

```powershell
python tools/compare_pne_units.py   # regenerates planning/LAB_CORPUS_REPORT.md
```

Do not use these zips for golden fixture regression — use `example/fixtures/` instead.
