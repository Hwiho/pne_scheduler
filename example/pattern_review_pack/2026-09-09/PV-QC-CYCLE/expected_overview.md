# PV-QC-CYCLE — QC cycle

**REOPEN ONLY — DO NOT START OR RUN ON EQUIPMENT.**

- Module: `qc`
- Parameters: `{"variant": "cycle"}`
- Expected steps: **17**
- Software trust: `software-checked`
- Canonical reference: Set2 17-step QC cycle family
- Candidate SHA-256: `8161fcd5d7024a52b6736869643413059381c2b2270d10f633f68f25ee859d99`

## Review

Open `candidate_REOPEN_ONLY_DO_NOT_RUN.sch` in CTSPro and compare every row with `expected_steps.csv`.
Record the CTSPro build, displayed values, Save-As behavior, and result in the pack-level
`review_results.csv`. A successful open is not permission to run.

## Warnings / unresolved evidence

- MODULE_TRUST: QC charge status is software-checked
- MODULE_LIMITATION: Set-specific voltage/time values require user reopen review.
- Set-specific voltage/time values require user reopen review.
- REOPEN ONLY. DO NOT START OR RUN THIS SCHEDULE ON EQUIPMENT.
- Only the 1760-byte header came from a CTSPro-authored PNE02 file; the step payload was software-generated.
- The exact output hash must pass CTSPro reopen/display/save-as review before promotion.
