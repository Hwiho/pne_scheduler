# Gate B — auto-generated annex

Regenerate: `python tools/assb_parser_diff_report.py`

## 612 vs 696 step layout diff (auto-generated)

- Catalog fixtures: **102**
- Sampled 612-byte step records: **200**
- Sampled 696-byte step records: **200**

## Interpretation

- 696-byte records are NOT a simple 84-byte append to 612-byte records.
- Late-field offsets in 0x00010003 corpus differ from ASSB legacy table (+8/+16 shifts).
- Semantic field names for bytes 612-695 require controlled pairs or Excel+fixture correlation.

## Extension nonzero hotspots (696-byte tail)

_No nonzero extension bytes in sample._

## Prefix float divergence heuristic

_No prefix divergence flagged in sample._

---

## ASSB vs internal parser divergence

Auto-generated report for Gate B. ASSB vendored constants live in `vendor/assb_sch/`. Internal reader uses `schema/fields.py`.

## Shared offset pairs (must match)

| ASSB name | ASSB offset | PNE name | PNE offset |
|-----------|-------------|----------|------------|
| SCH_REFERENCE_CURRENT_OFFSET | 16 | OFFSET_F_VREF | 16 |
| SCH_END_CURRENT_OFFSET | 32 | OFFSET_F_END_I | 32 |
| fEndC | 36 | OFFSET_F_END_C | 36 |

## Documented divergences

- **nGotoStepID** @ 84 vs **OFFSET_N_GOTO_STEP_ID** @ 92: pne_scheduler corpus regression; ASSB legacy PNE_file_structures offset
- **fSocRate** @ 384 vs **OFFSET_F_SOC_RATE** @ 392: pne_scheduler corpus regression (+8 bytes vs ASSB)
- **fMaxCapacity** @ 412 vs **OFFSET_F_MAX_CAPACITY** @ 428: pne_scheduler corpus regression (+16 bytes vs ASSB)
- **bUseActualCapa** @ 496 vs **OFFSET_B_USE_ACTUAL_CAPA** @ 512: pne_scheduler corpus regression (+16 bytes vs ASSB)
- **bUseDataStepNo** @ 497 vs **OFFSET_B_USE_DATA_STEP_NO** @ 513: pne_scheduler corpus regression (+16 bytes vs ASSB)

## Fixture comparison summary

- Fixtures checked: **11**
- Layout matches: **11**
- Step-count matches: **11**
- Fixtures with ASSB/native field mismatches: **0**

## Per-fixture notes

- `fixtures\capacheck_zip\00207966_260803_727도급셀_Set8_45도 Cycle.sch`: layout=True, steps=True, field_mismatches=0
- `fixtures\capacheck_zip\07100766_260511_SJ1300_dry_40um_RPT_500cycle.sch`: layout=True, steps=True, field_mismatches=0
- `fixtures\capacheck_zip\07100766_260617_Set2_bimodal-SJ1300-40um_80C_QPEED-2.sch`: layout=True, steps=True, field_mismatches=0
- `fixtures\capacheck_zip\3.BM_C1%_FM.sch`: layout=True, steps=True, field_mismatches=0
- `fixtures\capacheck_zip\9)Bimodal_SJ1300_6040_NCN_capacheck.sch`: layout=True, steps=True, field_mismatches=0
- `fixtures\hppc\HPPC_Full range.sch`: layout=True, steps=True, field_mismatches=0
- `fixtures\sch_lab_zip\0.5C cycle.sch`: layout=True, steps=True, field_mismatches=0
- `fixtures\sch_lab_zip\00207966_250903_2Ah Gr_closed CTCP ╛╚└ⁿ╝║┐δ.sch`: layout=True, steps=True, field_mismatches=0
- `fixtures\sch_lab_zip\00207966_260702_3┐∙ ░φ┐┬└·└σ╝┐ ╣µ└ⁿ.sch`: layout=True, steps=True, field_mismatches=0
- `fixtures\sch_lab_zip\07100766_260522_Set1_SJ900_wet_QC_1_charge.sch`: layout=True, steps=True, field_mismatches=0
- `fixtures\hppc\HPPC_Full range.sch`: layout=True, steps=True, field_mismatches=0
