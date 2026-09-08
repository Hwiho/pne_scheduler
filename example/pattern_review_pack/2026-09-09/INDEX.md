# PNE02 Pattern Reopen Review Pack

**All SCH files in this directory are REOPEN-ONLY and MUST NOT be started or run.**

Review the simplest schedules first, compare each screen with `expected_steps.csv`,
then Save As and record the result in `review_results.csv`. Approval is exact-hash- and
CTSPro-build-specific.

| ID | Pattern | Trust | Steps | Candidate |
|---|---|---:|---:|---|
| PV-FM | Formation | software-checked | 5 | [candidate_REOPEN_ONLY_DO_NOT_RUN.sch](PV-FM/candidate_REOPEN_ONLY_DO_NOT_RUN.sch) |
| PV-CAPA | Capacity check | software-checked | 12 | [candidate_REOPEN_ONLY_DO_NOT_RUN.sch](PV-CAPA/candidate_REOPEN_ONLY_DO_NOT_RUN.sch) |
| PV-CYCLE | Cycle life | software-checked | 7 | [candidate_REOPEN_ONLY_DO_NOT_RUN.sch](PV-CYCLE/candidate_REOPEN_ONLY_DO_NOT_RUN.sch) |
| PV-HPPC | HPPC full range | software-checked | 62 | [candidate_REOPEN_ONLY_DO_NOT_RUN.sch](PV-HPPC/candidate_REOPEN_ONLY_DO_NOT_RUN.sch) |
| PV-QPEED-F | QPEED full | software-checked | 167 | [candidate_REOPEN_ONLY_DO_NOT_RUN.sch](PV-QPEED-F/candidate_REOPEN_ONLY_DO_NOT_RUN.sch) |
| PV-QPEED-S | QPEED SOC setting | software-checked | 11 | [candidate_REOPEN_ONLY_DO_NOT_RUN.sch](PV-QPEED-S/candidate_REOPEN_ONLY_DO_NOT_RUN.sch) |
| PV-QC-CYCLE | QC cycle | software-checked | 17 | [candidate_REOPEN_ONLY_DO_NOT_RUN.sch](PV-QC-CYCLE/candidate_REOPEN_ONLY_DO_NOT_RUN.sch) |
| PV-QC-NQ | QC 1N1Q | software-checked | 17 | [candidate_REOPEN_ONLY_DO_NOT_RUN.sch](PV-QC-NQ/candidate_REOPEN_ONLY_DO_NOT_RUN.sch) |
| PV-QC-C | QC 1 charge | software-checked | 25 | [candidate_REOPEN_ONLY_DO_NOT_RUN.sch](PV-QC-C/candidate_REOPEN_ONLY_DO_NOT_RUN.sch) |
| PV-RPT | RPT prototype | prototype | 13 | [candidate_REOPEN_ONLY_DO_NOT_RUN.sch](PV-RPT/candidate_REOPEN_ONLY_DO_NOT_RUN.sch) |

Required before any SOC-dependent promotion: separate DOD@384 and fEndC@36
controlled pairs described in `planning/PATTERN_VALIDATION_PLAN.md`.
