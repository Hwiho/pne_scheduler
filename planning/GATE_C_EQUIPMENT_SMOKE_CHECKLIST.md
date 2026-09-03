# Gate C5 — PNE PC / equipment smoke checklist

Status: **pending lab execution**  
Depends on: C1–C4 (header, compiler, native round-trip, ASSB cross-check)

This checklist is the mandatory equipment gate before any `build` output may be
labeled equipment-executable. Do **not** mark Gate C complete until every row
below is recorded for at least one PNE unit (prefer PNE02).

## Setup

| Item | Value |
|------|-------|
| Date | |
| Operator | |
| PNE unit | e.g. PNE02 |
| CTSPro / CTSEditorPro build | e.g. CYCC-1004-S01-R004-N01 |
| Channel / profile | |
| Project | `example/smoke_rest_cc_end.schproj` |
| Output file | `smoke_rest_cc_end.sch` — Rest → CCCV → END |

## Procedure

1. Generate offline:
   ```powershell
   cd c:\Users\LGES\Cursor\pne_scheduler
   python -m pne_scheduler build example/smoke_rest_cc_end.schproj -o smoke_rest_cc_end.sch --allow-experimental-output
   ```
2. Copy `smoke_rest_cc_end.sch` to the PNE PC.
3. Open in CTSEditorPro (save-only; do **not** execute on a cell for the first pass).
4. Confirm UI values: REST 60 s, charge ~8 mA @ 4.2 V (0.1C × 80 mAh), END present.
5. Re-save once from CTSEditorPro and keep both files for `compare_sch`.
6. Optional second pass: execute Rest→CC→END on an open channel only after reopen looks correct.

## Results

| Check | Pass? | Notes |
|-------|:-----:|-------|
| CTSEditorPro opens file without error | ☐ | |
| Rest duration displayed correctly | ☐ | |
| Charge current / voltage displayed correctly | ☐ | |
| END step present | ☐ | |
| Re-save does not scramble unrelated fields | ☐ | attach `compare_sch` JSON |
| (Optional) Channel execution completes | ☐ | |

## Sign-off

| Role | Name | Date |
|------|------|------|
| Operator | | |
| Reviewer | | |

Record the completed checklist path in `planning/ROADMAP.md` §11 / Gate C5 progress when done.
