# PV-HPPC — HPPC full range

**REOPEN ONLY — DO NOT START OR RUN ON EQUIPMENT.**

- Module: `hppc`
- Parameters: `{"variant": "full"}`
- Expected steps: **62**
- Software trust: `software-checked`
- Canonical reference: Locked 62-step HPPC full-range golden
- Candidate SHA-256: `8b97e0275c0ef4b5c02aee2c76c924fb025eef04912eb22c5c890beca3532909`

## Review

Open `candidate_REOPEN_ONLY_DO_NOT_RUN.sch` in CTSPro and compare every row with `expected_steps.csv`.
Record the CTSPro build, displayed values, Save-As behavior, and result in the pack-level
`review_results.csv`. A successful open is not permission to run.

## Warnings / unresolved evidence

- MODULE_TRUST: HPPC status is software-checked
- MODULE_LIMITATION: Full topology is reproduced; DOD and CC mode-limit display still require CTSPro review.
- DISCHARGE_VLIM_HEADROOM: Discharge mode limit is below v_min; the end-voltage cutoff remains in range
- VOLTAGE_HEADROOM: Charge voltage limit exceeds cell v_max
- DOD_UNVERIFIED: DOD/SOC cutoff @384 is not controlled-pair verified
- Full topology is reproduced; DOD and CC mode-limit display still require CTSPro review.
- REOPEN ONLY. DO NOT START OR RUN THIS SCHEDULE ON EQUIPMENT.
- Only the 1760-byte header came from a CTSPro-authored PNE02 file; the step payload was software-generated.
- The exact output hash must pass CTSPro reopen/display/save-as review before promotion.
