# What you need to do (lab / decisions)

Gate C **exited 2026-09-08** (C5 PNE02). Gate D **software exit 2026-09-08**
(capacity contract + all P0/P1 module harnesses + golden family compares).
Software focus is now **Gate E** (modular UX). Below is only optional lab work.

---

## 1. Gate C5 — ✅ done

Checklist: [`GATE_C_EQUIPMENT_SMOKE_CHECKLIST.md`](GATE_C_EQUIPMENT_SMOKE_CHECKLIST.md)

---

## 2. Gate D — ✅ software done

- Capacity contract: `tests/test_capacity_contract.py`
- Module pipelines: `tests/test_gate_d_harness.py`
- Golden families: `tests/test_gate_d_fixture_topology.py`

Honest gaps (no lab required to close Gate D software bar): DCR IR-only;
`fEndC` unverified; modules are templates ≠ full lab schedules.

---

## 3. Optional lab — extended step types

CTS Type dropdown includes **Ocv / Impedance / Balance / Pattern**. Stubs:
[`STEP_TYPES_EXTENDED.md`](STEP_TYPES_EXTENDED.md). Corpus samples: **zero**.

When spare PNE02 time:

1. Rest→OCV→END, Rest→Impedance→END, Rest→Balance→END (+ Pattern if used)
2. Save + reopen; keep before/after bytes for Gate B5 intake
3. Promote nonzero deltas into `schema/fields.py`

---

## 4. Optional / later

| Item | When |
|------|------|
| Nonzero 696 tail appears | Controlled pair |
| OCV/Imp/Balance pairs | §3 |
| Prefer `patch-sch` for production edits | Until CLI header 54-byte gap understood |

---

## 5. Software next

- **Gate E** — Nova + LabVIEW *feel* for module/procedure authoring (§1.1, §6.6)
- Do not invent DCR binary maps without evidence
- Do not claim full 696 semantic lab parity beyond framing/zero-tail policy
