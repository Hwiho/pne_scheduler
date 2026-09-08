# Gate D — Verification Audit & Remediation Plan

Date: 2026-09-08  
Method audited: [`GATE_D_VERIFICATION.md`](GATE_D_VERIFICATION.md)  
Against: `validate/gate_d_harness.py`, topology tests, capacity contract, ROADMAP §6.5

---

## 1. Audit procedure

For each verification layer V1–V8:

1. Locate the claimed check in code or tests
2. Ask: can this fail for a real regression?
3. Ask: is the pass criterion machine-enforceable?
4. Record gap → severity → remediation

---

## 2. Findings

| ID | Layer | Finding | Severity | Remediation |
|----|-------|---------|----------|-------------|
| A1 | V8 | No single machine entrypoint / JSON exit report (unlike Gate B) | **high** | Add `validate/gate_d_verification.py` + `tools/run_gate_d_verification.py` → `GATE_D_VALIDATION_REPORT.json` |
| A2 | V2 | Module coverage was ad-hoc pytest cases; a new module could ship untested | **high** | Explicit `GATE_D_MODULE_MATRIX` + registry orphan check |
| A3 | V3 | Harness checked discharge end-V and current, but **not charge voltage@12** when `voltage_v` set | **medium** | Pack check in harness |
| A4 | V3 | LOOP count/goto only covered via roundtrip path; compile-time assert missing | **medium** | Compile-time loop field checks in harness |
| A5 | V5 | Required warnings for RPT/DCIR not enforced by a single matrix-driven check | **medium** | Matrix `required_warning_substrings` |
| A6 | V6 | Family tests existed but were separate from the exit report | **low** | Fold into verification runner |
| A7 | V1 | Capacity contract solid; not wired into Gate D exit report | **low** | Include V1 as report checks |
| A8 | Docs | ROADMAP claimed Gate D exit without a re-runnable verification method | **medium** | This audit + method doc + CI-oriented test |

---

## 3. Remediation status

| ID | Status | Where |
|----|--------|-------|
| A1 | ✅ done | `tools/run_gate_d_verification.py`, `planning/GATE_D_VALIDATION_REPORT.json` (generated) |
| A2 | ✅ done | `validate/gate_d_verification.py::GATE_D_MODULE_MATRIX` |
| A3 | ✅ done | `gate_d_harness.py` charge `voltage_v` → `@12` |
| A4 | ✅ done | `gate_d_harness.py` loop count/goto compile checks |
| A5 | ✅ done | matrix-driven warning asserts in verification runner |
| A6 | ✅ done | family checks inside `run_gate_d_verification()` |
| A7 | ✅ done | policy + compile Q_nom checks in runner |
| A8 | ✅ done | `GATE_D_VERIFICATION.md` + this audit + `tests/test_gate_d_verification.py` |

---

## 4. Residual accepted gaps (not defects)

- Module expands are **templates**; lab goldens are longer — family only
- DCR bytes never packed (L3)
- `fEndC` packs with `semantic_unverified` warning
- OCV/Imp/Balance outside Gate D module matrix

---

## 5. Re-audit trigger

Re-run this audit when:

- A new experiment module is registered
- Compiler packing for DCR / fEndC confidence changes
- Golden lock set changes
