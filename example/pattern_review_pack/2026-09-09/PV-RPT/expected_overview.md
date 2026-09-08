# PV-RPT — RPT prototype

**REOPEN ONLY — DO NOT START OR RUN ON EQUIPMENT.**

- Module: `rpt`
- Parameters: `{}`
- Expected steps: **13**
- Software trust: `prototype`
- Canonical reference: RPT corpus family; fEndC/DCR unresolved
- Candidate SHA-256: `fb2f4dd4cd05c2ee01596077a20605f0ce15c631adefcd30ae7b36f767bf85d5`

## Review

Open `candidate_REOPEN_ONLY_DO_NOT_RUN.sch` in CTSPro and compare every row with `expected_steps.csv`.
Record the CTSPro build, displayed values, Save-As behavior, and result in the pack-level
`review_results.csv`. A successful open is not permission to run.

## Warnings / unresolved evidence

- MODULE_TRUST: RPT status is prototype
- MODULE_LIMITATION: Capacity cutoff and DCR window need controlled pairs.
- FENDC_UNVERIFIED: Capacity cutoff fEndC@36 is not controlled-pair verified
- DCR_IR_ONLY: DCR window is IR-only and is not written
- Step 1: end_capacity_fraction packs fEndC@36, which is semantic_unverified (no nonzero example exists in the corpus; schema/fields.py). SOC-targeting via this field is unconfirmed pending controlled-pair evidence (Gate D).
- Step 3: dcr_start_s/dcr_end_s are kept on the IR only; binary DCR offsets are externally unresolved (Gate C2/D).
- Step 5: end_capacity_fraction packs fEndC@36, which is semantic_unverified (no nonzero example exists in the corpus; schema/fields.py). SOC-targeting via this field is unconfirmed pending controlled-pair evidence (Gate D).
- Step 7: dcr_start_s/dcr_end_s are kept on the IR only; binary DCR offsets are externally unresolved (Gate C2/D).
- Step 9: end_capacity_fraction packs fEndC@36, which is semantic_unverified (no nonzero example exists in the corpus; schema/fields.py). SOC-targeting via this field is unconfirmed pending controlled-pair evidence (Gate D).
- Step 11: dcr_start_s/dcr_end_s are kept on the IR only; binary DCR offsets are externally unresolved (Gate C2/D).
- Capacity cutoff and DCR window need controlled pairs.
- REOPEN ONLY. DO NOT START OR RUN THIS SCHEDULE ON EQUIPMENT.
- Only the 1760-byte header came from a CTSPro-authored PNE02 file; the step payload was software-generated.
- The exact output hash must pass CTSPro reopen/display/save-as review before promotion.
