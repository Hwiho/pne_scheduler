# Gate B — validation & binary evidence

SCH schema validation workflow, vendored ASSB parser notes, and Q_nom policy.  
Auto-generated annex: [`GATE_B_GENERATED.md`](GATE_B_GENERATED.md).

---

## Controlled pair (before/after)

A **controlled pair** is two `.sch` files from CTSPro where you changed **exactly one** UI setting (e.g. charge current 10 mA → 17 mA) and saved twice. Byte comparison maps UI values to SCH offsets. Save-only probe files are enough — no cell execution required.

---

## Validation data intake

This workflow turns CTSPro exports into reproducible binary-field evidence.

### Minimum data per equipment profile

For each relevant equipment profile (PNE02, PNE16, PNE21, PNE22, …), collect:

1. Equipment label and current rating.
2. CTSPro version or About-screen screenshot.
3. Channel range/profile or INI settings.
4. One baseline SCH file CTSPro can open.
5. A before/after pair with exactly one UI field changed.
6. Screenshots of the changed field and both values.

Do not infer equipment identity from a schedule filename.

### Recommended controlled pairs

Baseline schedule (save only, do not execute):

```text
REST → CC Charge → REST → CC Discharge → END
```

| Pair | Example change |
|------|----------------|
| Rest duration | 60 s → 123 s |
| Charge current | 10 mA → 17 mA |
| Discharge current | 10 mA → 19 mA |
| End voltage | 3000 mV → 3123 mV |
| CV cutoff current | 2 mA → 3 mA |
| Sampling interval | 1 s → 2 s |
| Loop count | 2 → 3 |
| Loop target | One step → another |
| Capacity termination | Disabled → nonzero |
| DCR window | One start/end → another |

### Metadata

Copy `example/validation-intake.template.json` next to each pair. `expected_field` may be null for discovery.

### Binary diff report

```powershell
python -m pne_scheduler.tools.compare_sch before.sch after.sch -o comparison.json
```

Reports SHA-256, layout, per-step byte ranges, aligned interpretations, field confidence, and uncontrolled-pair warnings.

### Evidence promotion

1. `semantic_unverified` — no controlled evidence  
2. `corpus_inferred` — pattern or one controlled pair  
3. `structural_verified` — confirmed across fixture corpus  
4. **Writer-ready** — two controlled values + CTSPro reopen + no stray byte changes  

### Applying new evidence

1. Store sensitive pairs outside public fixtures if needed.  
2. Generate and review comparison report.  
3. Update `schema/fields.py` or `schema/ensol_v612.py` (prefer ensol for I/O).  
4. Add golden test.  
5. Regenerate `example/fixtures/catalog.json` when corpus changes.  
6. Run `pytest`.  
7. Confirm CTSPro reopen before equipment execution.

---

## Q_nom (nominal capacity)

```
I (mA) = C-rate × Q_nom (mAh)
```

| C-rate | Current @ Q_nom=80 mAh |
|--------|------------------------|
| 1C | 80 mA |
| C/3 | 26.7 mA |
| 0.5C | 40 mA |

**Two sources today:**

1. **Explicit Cell Profile** — `nominal_capacity_mAh` in `.schproj` (writer path)  
2. **Inferred** — filename + SCH (viewer path)

If these disagree, C-rate display vs writer output diverges. Gate B needs a lab decision on authoritative Q_nom (stack formula vs fixed mAh vs CTSPro UI).

---

## Vendored ASSB SCH parser

In-tree copy of ASSB_Analyzer_dev `pne_converter.py` — no external `assb_analyzer` install.

| Path | Role |
|------|------|
| `vendor/assb_sch/constants.py` | Step types, layout keys, ASSB offsets |
| `vendor/assb_sch/parser.py` | `parse_sch_cycle_map_bytes` |
| `vendor/assb_sch/offset_parity.py` | vs `schema/fields.py` |
| `io/reader.py` | Thin wrapper (deprecate → `io/sch_parser.py`) |

```powershell
python -m pytest tests/test_assb_offset_parity.py -v
python tools/assb_parser_diff_report.py   # refreshes GATE_B_GENERATED.md § ASSB
```

Core end-condition offsets (16/32/36) match; later fields diverge because `pne_scheduler` re-derived from the 102-fixture corpus. Prefer `schema/ensol_v612.py` for writer/reader work.

---

## Golden fixtures

Locked set: [`planning/GOLDEN_FIXTURES.md`](../planning/GOLDEN_FIXTURES.md) + [`GOLDEN_FIXTURES_LOCKED.json`](../planning/GOLDEN_FIXTURES_LOCKED.json).  
Intake form (fillable): [`example/gate_b_export/GOLDEN_FIXTURE_INTAKE.md`](../example/gate_b_export/GOLDEN_FIXTURE_INTAKE.md).
