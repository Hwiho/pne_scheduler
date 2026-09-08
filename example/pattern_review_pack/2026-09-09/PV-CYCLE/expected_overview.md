# PV-CYCLE — Cycle life

**REOPEN ONLY — DO NOT START OR RUN ON EQUIPMENT.**

- Module: `cycle_life`
- Parameters: `{"loop_count": 3}`
- Expected steps: **7**
- Software trust: `software-checked`
- Canonical reference: Cycle corpus family
- Candidate SHA-256: `24f750a9f74bc01a914a355e5fd8784f84ae327a866c216c421c7bd7af803b2d`

## Review

Open `candidate_REOPEN_ONLY_DO_NOT_RUN.sch` in CTSPro and compare every row with `expected_steps.csv`.
Record the CTSPro build, displayed values, Save-As behavior, and result in the pack-level
`review_results.csv`. A successful open is not permission to run.

## Warnings / unresolved evidence

- MODULE_TRUST: Cycle life status is software-checked
- MODULE_LIMITATION: Checkpoint/RPT insertion is not modeled.
- Checkpoint/RPT insertion is not modeled.
- REOPEN ONLY. DO NOT START OR RUN THIS SCHEDULE ON EQUIPMENT.
- Only the 1760-byte header came from a CTSPro-authored PNE02 file; the step payload was software-generated.
- The exact output hash must pass CTSPro reopen/display/save-as review before promotion.
