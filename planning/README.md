# Planning & lab evidence

Index for policies, corpus reports, equipment registry, and roadmap.

---

## Start here

| Document | Purpose |
|----------|---------|
| [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md) | Directory map, code rules, cleanup workflow |
| [`LAB_DATA_POLICY.md`](LAB_DATA_POLICY.md) | PNE##.zip only, per-unit layout, CTS build |
| [`SCH_LAYOUT_TIER_SHARING.md`](SCH_LAYOUT_TIER_SHARING.md) | 500 mA vs 20 A — shared offsets, separate evidence |
| [`ROADMAP.md`](ROADMAP.md) | SCH structure analysis & implementation roadmap |
| [`LAB_CORPUS_REPORT.md`](LAB_CORPUS_REPORT.md) | **Generated** per-cycler zip analysis (human-readable) |

## Machine-readable data

| File | Purpose |
|------|---------|
| [`EQUIPMENT_CURRENT_RATINGS.json`](EQUIPMENT_CURRENT_RATINGS.json) | Official max current tiers |
| [`EQUIPMENT_REGISTRY.json`](EQUIPMENT_REGISTRY.json) | Per-unit corpus zip, layouts, CTS |
| [`PNE_UNIT_CORPUS.json`](PNE_UNIT_CORPUS.json) | Corpus scan output |
| [`PNE_UNIT_COMPARISON.json`](PNE_UNIT_COMPARISON.json) | Cross-unit diff output |
| [`GATE_B_CORPUS_EVIDENCE.json`](GATE_B_CORPUS_EVIDENCE.json) | Corpus-inferred 612-byte field evidence |
| [`SCH_LAYOUT_TIER_SHARING.json`](SCH_LAYOUT_TIER_SHARING.json) | 500 mA vs 20 A layout comparison (fixtures) |
| [`GATE_B_VALIDATION_REPORT.json`](GATE_B_VALIDATION_REPORT.json) | Repository readiness vs actual Gate B exit |
| [`Q_NOM_POLICY.json`](Q_NOM_POLICY.json) | Explicit writer vs inferred viewer capacity contract |
| [`GOLDEN_FIXTURES_LOCKED.json`](GOLDEN_FIXTURES_LOCKED.json) | Locked golden test paths |

## Gate B / fixtures

| Document | Purpose |
|----------|---------|
| [`GOLDEN_FIXTURES.md`](GOLDEN_FIXTURES.md) | Selected golden fixtures & rules |
| [`GOLDEN_FIXTURE_INTAKE.md`](../example/gate_b_export/GOLDEN_FIXTURE_INTAKE.md) | Fillable intake form |
| [`ENSOL_SCH_MAKER_ADOPTION.md`](ENSOL_SCH_MAKER_ADOPTION.md) | Ensol offset adoption log |
| [`EQUIPMENT_CTS_FROM_PPT.md`](EQUIPMENT_CTS_FROM_PPT.md) | CTSPro builds from lab PPT |

## User & technical docs (`docs/`)

| Document | Purpose |
|----------|---------|
| [`../docs/README.md`](../docs/README.md) | CLI, protocol, resume (user guide) |
| [`../docs/GATE_B.md`](../docs/GATE_B.md) | Validation intake, ASSB, Q_nom |
| [`../docs/GATE_B_GENERATED.md`](../docs/GATE_B_GENERATED.md) | Auto-generated layout/parser annex |
| [`../docs/CURSOR_CLOUD.md`](../docs/CURSOR_CLOUD.md) | Cursor Cloud / WSL |

## Regenerate corpus report

```powershell
python tools/analyze_pne_unit_corpus.py    # JSON only
python tools/compare_pne_units.py          # JSON + LAB_CORPUS_REPORT.md
```
