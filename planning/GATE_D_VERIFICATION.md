# Gate D — Verification Method

Status: **canonical** (2026-09-08)  
Scope: software-only module fidelity (`validate → expand → compile → parse → semantic compare`)  
Machine entrypoint: `python -m pne_scheduler.tools.run_gate_d_verification`  
Audit / remediations: [`GATE_D_VERIFICATION_AUDIT.md`](GATE_D_VERIFICATION_AUDIT.md)

---

## 1. Goal

Prove that every Gate D P0/P1 experiment module:

1. Validates parameters against a `CellProfile`
2. Expands to a coherent `StepIntent` topology
3. Compiles to Ensol 612-byte records with expected packed fields
4. Writes a framed `.sch` that the native parser can re-read
5. Round-trips semantically on writer-ready fields
6. Emits **honest warnings** where evidence is weak (DCR IR-only, `fEndC`)
7. Shares a step-type **family** with the matching locked golden (not byte equality)

Equipment reopen is **out of scope** for Gate D (already closed by C5 for the smoke class).

---

## 2. Verification layers (must all pass)

| ID | Layer | What it checks | Primary code |
|----|-------|----------------|--------------|
| **V1** | Policy / capacity | Writer Q_nom = `cell_profile.nominal_capacity_mAh` only; viewer may disagree | `tests/test_capacity_contract.py`, `planning/Q_NOM_POLICY.json` |
| **V2** | Module matrix | Every registered Gate D module runs `run_module_pipeline` and passes | `validate/gate_d_verification.py` |
| **V3** | Compile semantics | Non-zero I for charge/discharge; time@20; discharge end-V; charge V when set; LOOP count/goto | `validate/gate_d_harness.py` |
| **V4** | Round-trip | Write → `read_sch_binary` + `parse_schedule_file` step count + type codes | `validate/roundtrip.py` |
| **V5** | Honesty warnings | RPT/DC-IR must warn on DCR; SOC-fraction modules must warn on `fEndC` | harness warnings |
| **V6** | Golden families | Locked goldens share required type families with module expands | `validate/topology.py` |
| **V7** | Registry coverage | Every module in the Gate D matrix is registered; no silent orphans | verification matrix |
| **V8** | Exit report | JSON report with `gate_d_passed` and per-check results | `tools/run_gate_d_verification.py` |

---

## 3. Module matrix (params used for verification)

| Module | Params (verification profile) | Required topology tokens | Required warnings |
|--------|-------------------------------|--------------------------|-------------------|
| `formation` | `cycle_count=1`, `rest_s=60` | charge, rest, discharge, end | — |
| `rest` | `duration_s=120` | rest, end | — |
| `cycle_life` | `loop_count=2`, `rest_s=30` | cycle, charge, discharge, loop, end | — |
| `rpt` | 2 SOCs, short rests/pulses | discharge, rest | DCR + fEndC |
| `dcir` | 1 SOC, short rests/pulses | discharge, rest, end | DCR + fEndC |
| `hppc` | 2 SOCs, short rests/pulses | charge, discharge, rest | fEndC (SOC adjust) |
| `capacheck` | `measurement_cycles=1`, short rest | cycle, loop, charge, discharge, end | — |
| `qpeed` (`full`) | SOC `[0.5]`, short pulses | charge, discharge, rest | fEndC |
| `qpeed` (`soc_setting`) | SOC `[0.5]` | discharge, rest, loop, end | fEndC |
| `insitu_cycle` | `loop_count=2` | cycle…loop…end; label contains `in-situ` | — |

---

## 4. Golden family rules

Compare **normalized families** (`charge|discharge|rest|cycle|loop|end|…`), never step counts.

| Golden id | Module reference | Required shared family |
|-----------|------------------|------------------------|
| `golden-formation-696` | formation | `{charge, rest}` |
| `golden-cycle-612-long` | cycle_life | `{charge, discharge, rest, loop, end}` |
| `golden-hppc-612` | hppc | `{charge, discharge, rest}` |
| `golden-capacheck-612-b0` | capacheck | `{cycle, loop, charge, discharge, rest, end}` |
| `golden-rpt-612` | (fixture only) | parseable; `{charge, discharge, rest, end}` |
| `golden-qpeed-612` | (fixture only) | parseable; `{charge, discharge, rest, end}` |

Missing fixture files → check **skipped** (not failed).

---

## 5. How to run

```powershell
cd c:\Users\LGES\Cursor\pne_scheduler
python -m pne_scheduler.tools.run_gate_d_verification
# or via pytest (CI):
python -m pytest tests/test_gate_d_verification.py tests/test_capacity_contract.py tests/test_gate_d_harness.py tests/test_gate_d_fixture_topology.py -q
```

Exit report path (default): `planning/GATE_D_VALIDATION_REPORT.json`

---

## 6. Pass / fail

- **Pass:** `gate_d_passed == true` and every non-skipped check `status == "pass"`
- **Fail:** any pipeline mismatch, missing required warning, family miss, or matrix orphan
- **Skip:** golden file absent on disk

Do **not** claim equipment-executable fidelity for OCV/Impedance/Balance (see `STEP_TYPES_EXTENDED.md`).
