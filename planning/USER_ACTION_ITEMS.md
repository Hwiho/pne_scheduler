# What you need to do (lab / decisions)

Software Gate A–C work that can run without equipment is done.
**Gate D is deferred** (as requested). Below is only what still needs a person in the lab or an explicit decision.

---

## 1. Gate C5 — PNE PC smoke test (required to close Gate C)

Checklist: [`GATE_C_EQUIPMENT_SMOKE_CHECKLIST.md`](GATE_C_EQUIPMENT_SMOKE_CHECKLIST.md)

### Generate the smoke file (on this PC)

```powershell
cd c:\Users\LGES\Cursor\pne_scheduler
python -m pne_scheduler build example/smoke_rest_cc_end.schproj -o smoke_rest_cc_end.sch --allow-experimental-output
```

Expected schedule: **REST 60 s → CCCV charge (0.1C to 4.2 V) → END**.

### On the PNE PC

1. Copy `smoke_rest_cc_end.sch` to the cycler PC.
2. Open in **CTSEditorPro** (save-only first — do not execute yet).
3. Confirm rest duration / charge current·voltage / END look correct.
4. Re-save once; keep both files if possible for `compare_sch`.
5. Fill the checklist table (date, unit, CTSPro build, pass/fail).
6. Optional: execute Rest→CC→END on an open channel only after reopen looks good.

Until C5 is signed off, `build` output stays **experimental** (not equipment-executable).

---

## 2. Optional / later (not blocking Gate D deferral)

| Item | When |
|------|------|
| Screenshots for Gate B pairs | Nice-to-have; currently waived |
| PNE16 dedicated `fIref`/`fVref` pairs | Waived via PNE02 shared-prefix; collect only if you want stronger 696 evidence |
| Nonzero 696-byte tail appears in a new CTSPro save | Then capture a controlled pair — today all secured 696 tails are **zero** ([`SCH_696_TAIL_ANALYSIS.md`](SCH_696_TAIL_ANALYSIS.md)) |
| Commit filled C5 checklist into the repo | After the lab run |

---

## 3. Do not start yet

- **Gate D** (module E2E) — deferred per your request  
- Labeling any `build` output as safe for equipment — blocked on C5
