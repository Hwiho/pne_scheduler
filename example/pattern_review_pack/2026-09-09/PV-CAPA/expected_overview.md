# PV-CAPA — Capacity check

**REOPEN ONLY — DO NOT START OR RUN ON EQUIPMENT.**

- Module: `capacheck`
- Parameters: `{}`
- Expected steps: **12**
- Software trust: `software-checked`
- Canonical reference: PNE02 capacheck family; candidate topology needs review
- Candidate SHA-256: `f21ddba39769bd6c4c267ae2ccf1756d45afd9d230339c1f6e2cea758e42ef97`

## Review

Open `candidate_REOPEN_ONLY_DO_NOT_RUN.sch` in CTSPro and compare every row with `expected_steps.csv`.
Record the CTSPro build, displayed values, Save-As behavior, and result in the pack-level
`review_results.csv`. A successful open is not permission to run.

## Warnings / unresolved evidence

- MODULE_TRUST: Capacity check status is software-checked
- MODULE_LIMITATION: Golden step order is family-checked only.
- Golden step order is family-checked only.
- REOPEN ONLY. DO NOT START OR RUN THIS SCHEDULE ON EQUIPMENT.
- Only the 1760-byte header came from a CTSPro-authored PNE02 file; the step payload was software-generated.
- The exact output hash must pass CTSPro reopen/display/save-as review before promotion.
