# Gate B controlled-pair queue

Repository-only preparation is complete. These CTSPro save-only pairs are the remaining
external evidence queue; none should be executed on equipment.

| Priority | Target | Layout | UI field | Before → after | Expected field |
|---:|---|---|---|---|---|
| 1 | PNE02 | `0x00010003/612` | Rest duration | 60 s → 123 s | `fIref` (`time_or_rest_s@20`) |
| 2 | PNE02 | `0x00010003/612` | Charge current | 10 mA → 17 mA | `fVref` (`current_mA@16`) |
| 3 | PNE02 | `0x00010003/612` | Discharge current | 10 mA → 19 mA | `fVref` (`current_mA@16`) |
| 4 | PNE02 | `0x00010003/612` | End voltage | 3000 mV → 3123 mV | `fEndV@28` |
| 5 | PNE02 | `0x00010003/612` | CV cutoff current | 2 mA → 3 mA | `fEndI@32` |
| 6 | PNE02 | `0x00010003/612` | LOOP count | 2 → 3 | `loop_count@52` |
| 7 | PNE02 | `0x00010003/612` | LOOP target | step 2 → step 3 | `loop_target@48` / `loop_goto_ensol@564` discovery |
| 8 | PNE02 | `0x00010003/612` | Sampling interval | 1 s → 2 s | `record_time_s@340` |
| 9 | PNE16 | `0x00010004/696` | Charge current | 100 mA → 117 mA | shared-prefix `current_mA@16` |
| 10 | PNE16 | `0x00010004/696` | Rest duration | 60 s → 123 s | shared-prefix `time_or_rest_s@20` |

Each directory must contain `before.sch`, `after.sch`, `intake.json`, and at least one
referenced screenshot. The intake must include the CTSPro build and channel profile.
`tools/run_gate_b_validation.py --require-gate-exit` recomputes the binary comparison
instead of trusting a stale report.
