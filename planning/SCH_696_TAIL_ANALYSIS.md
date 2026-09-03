# 696-byte step tail analysis (Gate C6)

Date: 2026-09-03  
Machine-readable: [`SCH_696_TAIL_ANALYSIS.json`](SCH_696_TAIL_ANALYSIS.json)

## Verdict

**In all secured evidence, the 84-byte tail (offsets 612–695) is unused (all zeros).**  
The from-scratch writer’s `612-byte prefix + 84 zero bytes` policy matches the lab corpus.

| Scope | Count | Nonzero tail records |
|------|------:|---------------------:|
| Catalog fixtures (`step_size=696`) | 92 files / 2056 steps | **0** |
| Corpus zip `0x00010004` sample | 15 files | **0** |

## What this means for Gate C6

| Item | Status |
|------|--------|
| `0x00010004` / 1844 B header | ✅ |
| Shared-prefix field registry (`record_time_s`, loops, …) | ✅ |
| Writer emits 696 B steps with zero tail | ✅ (matches corpus) |
| Named semantics for bytes 612–695 | **N/A in current corpus** — no nonzero data to map |

Excel’s `0x00010004` sheet still lists many logical fields, but those offsets are **not** a direct binary map onto 612–695 (same class of mismatch already seen for 612-byte Ensol vs ASSB/Excel).

## Optional follow-up (only if lab changes)

1. If a new CTSPro build writes nonzero bytes past 612, capture a controlled before/after pair.
2. Re-run the catalog/corpus scan and update this report.

Until then, **C6 is complete for the observed corpus**.
