# PV-QPEED-F — QPEED full

**REOPEN ONLY — DO NOT START OR RUN ON EQUIPMENT.**

- Module: `qpeed`
- Parameters: `{"variant": "full"}`
- Expected steps: **167**
- Software trust: `software-checked`
- Canonical reference: PNE02 locked 167-step golden
- Candidate SHA-256: `90ccc42fc617de8ec0baafeb5b03354527b2195c4663b16012ea363ef0c40e43`

## Review

Open `candidate_REOPEN_ONLY_DO_NOT_RUN.sch` in CTSPro and compare every row with `expected_steps.csv`.
Record the CTSPro build, displayed values, Save-As behavior, and result in the pack-level
`review_results.csv`. A successful open is not permission to run.

## Warnings / unresolved evidence

- MODULE_TRUST: QPEED status is software-checked
- MODULE_LIMITATION: DOD/SOC semantics still need CTSPro controlled-pair verification.
- VOLTAGE_HEADROOM: Charge voltage limit exceeds cell v_max
- DOD_UNVERIFIED: DOD/SOC cutoff @384 is not controlled-pair verified
- DOD/SOC semantics still need CTSPro controlled-pair verification.
- REOPEN ONLY. DO NOT START OR RUN THIS SCHEDULE ON EQUIPMENT.
- Only the 1760-byte header came from a CTSPro-authored PNE02 file; the step payload was software-generated.
- The exact output hash must pass CTSPro reopen/display/save-as review before promotion.
