# What you need to do (lab / decisions)

Software Gate A–C work that can run without equipment is done and was
**re-audited against the roadmap on 2026-09-03** (see `ROADMAP.md` §6.4 honest assessment).
**Gate D is deferred.** Below is only what still needs a person in the lab.

---

## 1. Gate C5 — PNE PC smoke test (**required** to close Gate C)

Checklist: [`GATE_C_EQUIPMENT_SMOKE_CHECKLIST.md`](GATE_C_EQUIPMENT_SMOKE_CHECKLIST.md)

Pre-built file (preferred): `example/smoke_rest_cc_end.sch`  
Or regenerate:

```powershell
cd c:\Users\LGES\Cursor
python -m pne_scheduler build pne_scheduler/example/smoke_rest_cc_end.schproj -o pne_scheduler/example/smoke_rest_cc_end.sch --allow-experimental-output
```

Expected: **REST 60 s → CCCV charge (~8 mA @ 4.2 V) → END**.

### On the PNE PC

1. Copy `smoke_rest_cc_end.sch` to the cycler PC.
2. Open in **CTSEditorPro** (save-only first).
3. Confirm rest / charge current·voltage / END.
4. Re-save once; keep both files if possible.
5. Fill the checklist (date, unit, CTSPro build, pass/fail).

Until C5 is signed off, `build` stays **experimental**.

### Near-term safer alternative (optional)

For editing real lab schedules before C5, prefer **`patch-sch`** on a CTSPro-authored
template (Gate C0.2) over from-scratch `build`.

---

## 2. Optional / later

| Item | When |
|------|------|
| Screenshots for Gate B pairs | Nice-to-have; waived |
| PNE16 dedicated pairs | Waived via PNE02 shared-prefix |
| Nonzero 696 tail appears | Then controlled pair — today tails are zero |
| Commit filled C5 checklist | After lab run |

---

## 3. Do not start yet

- **Gate D** (until you ask)
- **Gate E Autolab procedure UX** semantic export (until C5 closes Gate C)
- Claiming full “696 lab semantic parity” beyond framing/zero-tail policy
- Labeling `build` output as equipment-safe
- Live Autolab-style instrument control / realtime plots (deferred product line)

## 4. Product direction (locked in roadmap)

Target UX is **Autolab / Nova-style procedure authoring** for PNE `.sch` (offline), not
LabVIEW-only and not CTS runtime replacement. See `ROADMAP.md` §1.1 and §6.6.
Gate A–C lessons are now a permanent checklist in §5.6.
