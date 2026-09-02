# Gate B — validation & binary evidence

SCH schema validation workflow, vendored ASSB parser notes, and Q_nom policy.  
Auto-generated annex: [`GATE_B_GENERATED.md`](GATE_B_GENERATED.md).

---

## Controlled pair (before/after)

A **controlled pair** is two `.sch` files from CTSPro where you changed **exactly one** UI setting (e.g. charge current 10 mA → 17 mA) and saved twice. Byte comparison maps UI values to SCH offsets. Save-only probe files are enough — no cell execution required.

`python tools/run_gate_b_validation.py` reports repository preparation separately from
actual Gate B exit:

- `repository_ready_for_controlled_pairs=true` means all checks that can run without
  CTSPro evidence are green.
- `gate_b_passed=true` additionally requires real, valid, reopen-verified intake files
  under `example/gate_b_pairs/`.
- `all_passed` is an alias of `gate_b_passed`, not merely a pytest result.

Use `--require-gate-exit` in CI once controlled-pair evidence has been added.

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

**Two paths exist, but only one is allowed to drive output:**

1. **Explicit Cell Profile** — `nominal_capacity_mAh` in `.schproj`; this is the
   authoritative writer source.
2. **Inferred** — filename + SCH; this is display/analysis-only and must never feed the
   compiler.

If these disagree, the viewer must show the discrepancy while the writer continues to use
the explicit Cell Profile value. This fail-safe contract removes inferred Q_nom from the
writer path without claiming that the inferred display value is lab-authoritative.

## Corpus-only evidence

`planning/GATE_B_CORPUS_EVIDENCE.json` records the reproducible evidence summary from all
15 checked-in PNE unit archives. It can promote fields only to `corpus_inferred`; it cannot
make a field writer-ready. In particular, the corpus strongly supports the 612-byte
`+12/+16/+20/+28/+32/+52/+384` mappings, while the 696-byte corpus remains too small to
transfer late-field semantics.

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
