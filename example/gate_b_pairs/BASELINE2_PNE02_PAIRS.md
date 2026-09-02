# PNE02 baseline2 — recommended controlled pairs

Use `example/gate_b_pairs/baseline2.sch` as **before.sch** in CTSEditorPro on **PNE02**
(`CYCC-1004-S01-R004-N01`, `0x00010003/612`). Save only — do not execute.

## Already covered (20A baseline, `0x10002`)

| Pair dir | Field | Notes |
|----------|-------|-------|
| `baseline-charge-current/` | `fVref@16` | 10 A tier — not PNE02 |
| `baseline-end-voltage/` | `mode_value@12` | same |
| `baseline-cv-cutoff/` | `fEndI@32` | same |
| `baseline-loop-count/` | `loop_count@52` | same |

Re-run these on **PNE02 + baseline2** for writer evidence on the 500 mA tier.

## Priority queue (PNE02 / baseline2)

| Pri | CTSPro UI change | before → after | Expected field | Suggested folder |
|----:|------------------|----------------|----------------|------------------|
| 1 | Charge current | 10 mA → 17 mA | `current_mA@16` | `pne02-charge-current/` |
| 2 | Discharge current | 10 mA → 19 mA | `current_mA@16` | `pne02-discharge-current/` |
| 3 | CV cutoff | 2 mA → 3 mA | `cv_cutoff_mA@32` | `pne02-cv-cutoff/` |
| 4 | End voltage (discharge) | 2500 mV → 3123 mV | `voltage_cutoff_mV@28` | `pne02-end-voltage/` |
| 5 | LOOP count | 2 → 3 | `loop_count@52` | `pne02-loop-count/` |
| 6 | Rest duration (add REST step or edit step time) | 60 s → 123 s | `time_or_rest_s@20` | `pne02-rest-duration/` |
| 7 | Sampling / record interval | 60 s → 120 s | `record_time_s@340` | `pne02-sampling-interval/` |
| ~~8~~ | ~~LOOP goto target~~ | — | `loop_goto_ensol@564` | **blocked** — see below |

## PNE16 (696 B) — waived via PNE02 shared-prefix evidence

| Pri | UI change | before → after | Field | Status |
|----:|-----------|----------------|-------|--------|
| ~~9~~ | Charge current | — | `current_mA@16` | **waived** — `pne02-charge-current/`, `pne02-discharge-current/` |
| ~~10~~ | Rest duration | — | `time_or_rest_s@20` | **waived** — `pne02-rest-duration/` |

696-byte records share the first 612 bytes with PNE02; B1 diff shows no prefix float
divergence at `@16` / `@20`. Gate B waiver:
[`planning/GATE_B_CONTROLLED_PAIR_WAIVERS.json`](../../planning/GATE_B_CONTROLLED_PAIR_WAIVERS.json).

## Per-pair checklist

1. Copy `baseline2.sch` → `before.sch`
2. Change **one** UI value → save `after.sch`
3. Fill `intake.json` (`equipment.label=PNE02`, `ctspro_version=CYCC-1004-S01-R004-N01`)
4. Screenshot + CTSPro reopen on `after.sch`
5. `python -m pne_scheduler compare before.sch after.sch -o comparison.json`

## Regenerate baseline2

```powershell
python tools/export_baseline2_pne02.py
```

Output: [`baseline2.sch`](baseline2.sch) + [`baseline2.meta.json`](baseline2.meta.json).

**Open in CTSEditorPro on PNE02** and confirm the schedule loads; re-save once if the
editor normalizes header bytes.

## LOOP goto — not achievable on baseline2

On `CCCV → CC_DCHG → LOOP → END`, CTSEditorPro LOOP goto UI exposes **only step 1**
(`loop_goto_ensol@564` = 1 in the imported pairs). Step 2 cannot be selected, so a
controlled before/after pair for goto target is **not possible** on this schedule.

Gate B waiver: [`planning/GATE_B_CONTROLLED_PAIR_WAIVERS.json`](../../planning/GATE_B_CONTROLLED_PAIR_WAIVERS.json).
Discovery evidence remains corpus + `golden-cycle-612-long`. Writer promotion for
`loop_goto_ensol` would need a longer schedule where multiple goto targets are selectable.
Use [`baseline3-loop-goto.sch`](baseline3-loop-goto.sch) — see
[`BASELINE3_LOOP_GOTO_PNE02.md`](BASELINE3_LOOP_GOTO_PNE02.md).

## baseline2 reopen (confirmed)

User confirmed `baseline2.sch` opens in CTSEditorPro on PNE02 (2026-09-02).
See [`baseline2.meta.json`](baseline2.meta.json). Imported controlled pairs were saved
as `0x00010002/612` (4080 B) under `김휘호/baseline2` — CTSEditorPro may normalize
layout on save.
