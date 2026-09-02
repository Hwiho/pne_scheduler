# Gate B controlled-pair drop location

Place real CTSPro save-only evidence here when it becomes available. The repository is
prepared to run without these files, but Gate B cannot exit until valid, reopen-verified
pairs are present.

**500 mA vs 20 A:** same step layout and offsets; separate pair directories by tier for
writer evidence. See [`planning/SCH_LAYOUT_TIER_SHARING.md`](../../planning/SCH_LAYOUT_TIER_SHARING.md).

Use one directory per pair:

```text
example/gate_b_pairs/
└── pne02-charge-current/
    ├── before.sch
    ├── after.sch
    ├── intake.json
    ├── comparison.json
    └── screenshots/
```

For each pair:

1. Open a CTSPro-authored baseline and save it as `before.sch`.
2. Change exactly one UI value and save as `after.sch`; do not execute either schedule.
3. Copy `example/validation-intake.template.json` to `intake.json` and record the CTSPro
   build, channel profile, field, values, and screenshot paths.
4. Generate `comparison.json`:

   ```bash
   python3 -m pne_scheduler compare before.sch after.sch -o comparison.json
   ```

5. Reopen the exact `after.sch` in CTSPro. Set `ctspro_reopen_verified` to `true` only
   after the displayed value and SHA-256 have been recorded.
6. Run:

   ```bash
   python3 tools/run_gate_b_validation.py --require-gate-exit
   ```

The fillable template outside this directory is never counted as evidence.

## Imported baseline pairs (2026-09-02)

`Baseline_controlled_pair.zip` was imported with:

```bash
python tools/import_baseline_controlled_pairs.py c:/Baseline_controlled_pair.zip
```

| Directory | UI change | Expected field | Clean pair |
|-----------|-----------|----------------|------------|
| `baseline-charge-current/` | 10 A → 17 A | `fVref` | yes |
| `baseline-end-voltage/` | 4000 mV → 4123 mV | `mode_value` | yes |
| `baseline-cv-cutoff/` | 2000 mA → 3000 mA | `fEndI` | yes |
| `baseline-loop-count/` | LOOP 2 → 3 | `loop_count` | yes |
| `baseline-sampling-interval/` | 60 s → 120 s | `record_time_s` | yes (method B: step2 @340 normalized) |

Layout: `0x00010002/612`. Header filename drift from CTSPro save names is normalized
to `before.sch`/`after.sch` before diff. Global sampling co-writes step 1+2 `@340`;
import keeps step-1-only diff (see `import_baseline_controlled_pairs.py`).

## Baseline golden UI (`baseline.sch`)

CTSEditorPro **CYCGN-P1107-S01-R001-N022**, list `Sample`, schedule `baseline`.
Machine-readable map: [`baseline-golden.json`](baseline-golden.json). Screenshot:
[`screenshots/baseline-ctspro-ui.png`](screenshots/baseline-ctspro-ui.png).

| CTSPro UI row | Type | On-disk step | Key values (UI → binary) |
|---------------|------|--------------|---------------------------|
| 2 | Charge CC/CV | step 1 `CCCV` | UI **4.200 V** → `mode_value@12` **4000** (confirmed), 10 A → `fVref@16` 10000 mA, I&lt;2 A → `fEndI@32` 2000 mA |
| 3 | Discharge CC | step 2 `CC_DCHG` | 2.5 V end / 9 A → `fVref@16` 9000 mA, `fEndV@28` 2500 mV |
| 4 | Loop ×2 | step 3 `LOOP` | `loop_count@52` = 2 |
| 5 | Complete | step 4 `END` | — |

\*Cycle row in CTSPro is UI-only; the file has 4 step records.

**CV voltage encoding (confirmed 2026-09-02):** CTSPro UI shows **4.200 V** but
`mode_value@12` stores **4000** (not 4200). The `baseline_4.123V` controlled pair
changes this field 4000 → 4123 mV.

Safety header: Vmax 4300 mV, Vmin 1500 mV, Cmax 5000 mAh, Tmax 70 °C.

## Imported PNE02 pairs (2026-09-02)

`PNE02_controlled_pair.zip` was imported with:

```bash
python tools/import_pne02_controlled_pairs.py c:/PNE02_controlled_pair.zip
```

| Directory | UI change | Expected field | Clean pair |
|-----------|-----------|----------------|------------|
| `pne02-charge-current/` | 10 mA → 17 mA | `fVref` | yes |
| `pne02-discharge-current/` | 10 mA → 19 mA | `fVref` | yes |
| `pne02-end-voltage/` | 2500 mV → 3123 mV | `fEndV` | yes |
| `pne02-loop-count/` | LOOP 2 → 3 | `loop_count` | yes |
| `pne02-rest-duration/` | REST 60 s → 123 s | `fIref` | yes |
| `pne02-sampling-interval/` | record 60 s → 120 s (charge) | `record_time_s` | yes |
| `pne02-sampling-interval-discharge/` | record 60 s → 120 s (discharge) | `record_time_s` | yes |
| `pne02-cv-cutoff/` | 2 mA → 3 mA | `fEndI` | yes (cap496@496 normalized on before) |

Layout: `0x00010002/612` (4080 B) from CTSEditorPro on **PNE02**
(`CYCC-1004-S01-R004-N01`, channel `김휘호/baseline2`). Header filename drift
normalized before diff. `loop_goto_ensol` waived on baseline2; use
[`baseline3-loop-goto.sch`](baseline3-loop-goto.sch) instead — see
[`BASELINE3_LOOP_GOTO_PNE02.md`](BASELINE3_LOOP_GOTO_PNE02.md).
`baseline2.sch` reopen confirmed on PNE02; per-pair reopen + screenshots still pending.

## LOOP goto template (baseline3)

```powershell
python tools/export_baseline3_loop_goto_pne02.py
```

6-step `CCCV → REST → CC_DCHG → REST → LOOP → END` (5432 B). Default LOOP goto = step 1;
change to step 2 in CTSEditorPro for `pne02-loop-goto/` controlled pair.

## Imported LOOP goto pair (2026-09-02)

`goto_controlled_pair.zip` → `pne02-loop-goto/` (`loop_target@48`, step 17, 1→7, clean).

```bash
python tools/import_goto_controlled_pair.py c:/goto_controlled_pair.zip
```

CTSEditorPro expanded baseline3 to 18 steps (12648 B, `0x10002`) on save.
`loop_goto_ensol@564` unchanged; PNE02 UI writes goto to **+48**.
