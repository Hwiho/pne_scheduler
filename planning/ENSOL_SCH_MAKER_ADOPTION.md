# Ensol sch_maker → pne_scheduler adoption log

Date: 2026-09-01  
Source: `c:\Ensol_sch_maker (1).zip` → `vendor/ensol_sch_maker_ref/`

## Summary

Ensol sch_maker provides a **working 612-byte `.sch` writer** used in the lab. Cross-checking
its offset map against the locked golden capacheck (`9)Bimodal…capacheck.sch`, PNE02) resolves
several Gate B0 blockers that ASSB legacy field names obscured.

## Adopted (in code / tests)

| Item | Status | Location |
|------|--------|----------|
| 612-byte step offset map (mV/mA/s) | ✅ | `schema/ensol_v612.py` |
| Golden capacheck byte regression | ✅ | `tests/test_ensol_v612_golden.py` |
| Reader uses **+16 mA** for C-rate display | ✅ | `io/sch_parser.py` |
| Compiler writes **mV @ +12/+28**, **mA @ +16/+32**, **time @ +20** | ✅ | `engine/compiler.py` |
| Writer contract: `I_mA = C_rate × cell_capacity_mAh` | ✅ | already in `engine/c_rate.py` |
| Vendor snapshot + README | ✅ | `vendor/ensol_sch_maker_ref/` |
| Rescaler offset targets (+16, +32) | ✅ | `io/current_rescaler.py`, `tools/rescale_sch_current.py` |

## Adopted (documentation / roadmap)

| Item | Location |
|------|----------|
| Block taxonomy mapping | below |
| Header layout (1632 vs 1760, magic, safety @ 0x3D8) | Gate C1 |
| LOOP = CYCMRK … steps … LOOP(n) pattern | Gate D modules |
| CYCMRK missing → wrong loop target | `resume` / linter backlog |

## Block type mapping (Ensol → pne_scheduler)

| Ensol `sch_core` expander | pne_scheduler module / classify |
|---------------------------|----------------------------------|
| `capacity_check` | `capacheck` |
| `soc_setting` | `qpeed` + `QpeedVariant.SOC_SETTING` |
| `pulse_test` | `hppc` |
| `cycle` | `cycle_life` |
| `rate_test` | (future) rate capability |
| `rest` | `rest` |

## Intentionally not merged yet

| Item | Reason |
|------|--------|
| Full `sch_core` header writer (1632 B) | Corpus uses 1760 B for 0x10003; template patch first (Gate C) |
| `OFF_GOTO @ 564` vs corpus `+48` | Needs controlled pair on PNE02 LOOP step |
| `OFF_F496` cap flags vs ASSB `+512` | Offset divergence; pair required |
| Flask web UI | Gate E / separate from pne_scheduler package |
| 696-byte layout | Ensol targets 612 only; B1 still needs 696 map |

## Gate B impact

- **B0 partially unblocked** for 612-byte CCCV/CCDi/REST: voltage mV, current mA, duration s.
- **B4** can build semantic goldens using Ensol field names.
- **User writer model** (1C current input → mA in SCH) matches Ensol `crate_to_mA`.

## Verification command

```powershell
cd c:\Users\LGES\Cursor\pne_scheduler
python -m pytest tests/test_ensol_v612_golden.py tests/test_unit_contract.py -q
```
