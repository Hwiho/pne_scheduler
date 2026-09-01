# Vendored ASSB SCH parser

`pne_scheduler` ships an in-tree copy of the SCH parsing rules from
[ASSB_Analyzer_dev](https://github.com/lgn0427-dev/ASSB_Analyzer_dev)
(`assb_analyzer/io/pne_converter.py`). No external `assb_analyzer` install is required.

## Modules

| Path | Role |
|------|------|
| `vendor/assb_sch/constants.py` | Step types, layout keys, ASSB field offsets |
| `vendor/assb_sch/parser.py` | `parse_sch_cycle_map_bytes`, layout detection |
| `vendor/assb_sch/offset_parity.py` | Comparison tables vs `schema/fields.py` |
| `io/reader.py` | Thin wrapper over vendored parser |

## Offset parity

ASSB and `schema/fields.py` agree on core end-condition offsets (16/32/36).
Later ASSB condition fields (`fSocRate`, `bUseDataStepNo`, …) diverge because
`pne_scheduler` re-derived offsets from the 102-fixture corpus.

Run:

```powershell
python -m pytest tests/test_assb_offset_parity.py -v
```

## Updating the vendored snapshot

1. Diff against upstream `assb_analyzer/io/pne_converter.py` (SCH sections only).
2. Update `vendor/assb_sch/constants.py` and `parser.py`.
3. Re-run `tests/test_assb_offset_parity.py` and adjust `DOCUMENTED_DIVERGENCES` if intentional.
