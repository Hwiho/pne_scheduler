# PV-QC-C — QC 1 charge

**REOPEN ONLY — DO NOT START OR RUN ON EQUIPMENT.**

- Module: `qc`
- Parameters: `{"variant": "1_charge"}`
- Expected steps: **25**
- Software trust: `software-checked`
- Canonical reference: QC 1-charge 24–26-step family
- Candidate SHA-256: `c8d5d4ee966834570ce58cd1aa65c5e512644187e689c832c1b403c8cb003624`

## Review

Open `candidate_REOPEN_ONLY_DO_NOT_RUN.sch` in CTSPro and compare every row with `expected_steps.csv`.
Record the CTSPro build, displayed values, Save-As behavior, and result in the pack-level
`review_results.csv`. A successful open is not permission to run.

## Warnings / unresolved evidence

- MODULE_TRUST: QC charge status is software-checked
- MODULE_LIMITATION: Set-specific voltage/time values require user reopen review.
- DOD_UNVERIFIED: DOD/SOC cutoff @384 is not controlled-pair verified
- Set-specific voltage/time values require user reopen review.
- REOPEN ONLY. DO NOT START OR RUN THIS SCHEDULE ON EQUIPMENT.
- Only the 1760-byte header came from a CTSPro-authored PNE02 file; the step payload was software-generated.
- The exact output hash must pass CTSPro reopen/display/save-as review before promotion.
