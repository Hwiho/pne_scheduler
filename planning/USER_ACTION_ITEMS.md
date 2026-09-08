# What you need to do (lab / decisions)

Software Gate A–C work that can run without equipment is done and was
**re-audited against the roadmap on 2026-09-03** (see `ROADMAP.md` §6.4 honest assessment).
**Gate D is deferred.** Below is only what still needs a person in the lab.

---

## 1. Gate C5 — PNE PC smoke test (**required** to close Gate C)

Checklist: [`GATE_C_EQUIPMENT_SMOKE_CHECKLIST.md`](GATE_C_EQUIPMENT_SMOKE_CHECKLIST.md)
Why one file now covers everything: [`GATE_C5_EVIDENCE_COVERAGE.md`](GATE_C5_EVIDENCE_COVERAGE.md)

Pre-built file (preferred, replaces the old rest→CC→end-only smoke): `example/smoke_writer_probe.sch`
Or regenerate:

```powershell
python -m pne_scheduler.tools.rebuild_smoke_sch_from_lab_header example/smoke_writer_probe.schproj
```

Expected: **CCCV charge (8 mA @ 4.2 V) → rest → CC discharge
(8 mA, cutoff 2.5 V) → rest → LOOP x2 (goto step 1) → END**, 6 steps.
No Cycle marker (CTS requires Cycle…Loop pairing; PNE02 loop pairs omit Cycle).
This single file combines every field that already has controlled-pair or corpus
evidence (charge, discharge, CV cutoff, LOOP, per-step sampling) so one reopen
replaces what would otherwise be several separate physical checks — see the
evidence-coverage doc for the full field-by-field justification.

### On the PNE PC

1. Copy `smoke_writer_probe.sch` to the cycler PC (overwrite any older smoke file
   already loaded on a channel).
2. Open in **CTSEditorPro** (save-only first).
3. Walk the per-step value table in the checklist (charge/discharge current &
   voltage, LOOP count/goto, sampling intervals, END).
4. Re-save once; keep both files if possible.
5. Fill the checklist (date, unit, CTSPro build, pass/fail).

The old minimal file (`example/smoke_rest_cc_end.sch`) still exists as a fallback
to isolate header-framing issues from step-logic issues if the probe fails to open.

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
- **Gate E** semantic export (until C5 closes Gate C)
- Claiming full “696 lab semantic parity” beyond framing/zero-tail policy
- Labeling `build` output as equipment-safe

## 4. Product direction (locked in roadmap)

Target UX is **Autolab Nova + LabVIEW feel** while *making* schedules from modules —
visual/interaction inspiration only, not realtime control. See `ROADMAP.md` §1.1 and §6.6.
Gate A–C lessons are a permanent checklist in §5.6.
