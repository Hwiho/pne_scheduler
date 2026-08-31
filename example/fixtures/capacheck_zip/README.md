# SJ1300 Bimodal capacheck example schedules

Source archive: `c:\9)Bimodal_SJ1300_6040_NCN_capacheck.zip`

These `.sch` files are reference fixtures for `pne_scheduler` writer validation and
filename-based experiment classification.

## Classification (from filename)

| File | Category | Builder module | Steps | SCH version | Step size |
|------|----------|----------------|------:|-------------|-----------|
| `9)Bimodal_SJ1300_6040_NCN_capacheck.sch` | capacheck | `capacheck` | 15 | 0x00010003 | 612 |
| `3.BM_C1%_FM.sch` | formation | `formation` | 9 | 0x00010004 | 696 |
| `set3_bimodal-30_45℃ 0.5C cycle.sch` | cycle_life | `cycle_life` | 41 | 0x00010004 | 696 |
| `00207966_260803_727도매석_Set8_45℃ Cycle.sch` | cycle_life | `cycle_life` | 73 | 0x00010003 | 612 |
| `07100766_260511_SJ1300_dry_40um_RPT_500cycle.sch` | rpt | `rpt` | 41 | 0x00010004 | 696 |
| `임효진_3350_L.4.36_NP1.08_RPT_SOC50 End_챔버시험용.sch` | rpt | `rpt` | 19 | 0x00010002 | 612 |
| `07100766_260713_Set9_QPEED_SOC_setting_BM_SJ1300_6040_C_NCN.sch` | qpeed (`soc_setting`) | `qpeed` | 11 | 0x00010003 | 612 |
| `07100766_260617_Set2_bimodal-SJ1300-40um_80C_QPEED-2.sch` | qpeed (`full`) | `qpeed` | 167 | 0x00010003 | 612 |

## Filename rules

| Pattern in name | Category |
|-----------------|----------|
| `capacheck` | Initial capacity check (bimodal SJ1300 protocol) |
| `FM`, `C1%`, `formation` | Formation |
| `Cycle`, `0.5C cycle`, `45℃ Cycle` | Cycle life / aging |
| `RPT` | Reference performance test block |
| `QPEED` | Bimodal QPEED experiment family |
| `QPEED` + `SOC_setting` | QPEED sub-step: SOC conditioning values before pulse block |

`SOC_setting` is **not** a standalone top-level experiment. It is a QPEED sub-protocol.

## Typical topologies

- **capacheck / cycle_life / formation**: `REST → LOOP → CYCLE → CCCV → REST → CC_DCHG → REST → … → END`
- **rpt**: cycle block + extra reference discharge / SOC checkpoints
- **qpeed (soc_setting)**: short QPEED conditioning sequence ending in `LOOP → END`
- **qpeed (full)**: long pulse train (`CC_CHG` / `CC_DCHG` alternation with rests)

## Manifest

`manifest.json` contains parsed step topology and key fields (`fVref`, `fIref`, …)
for each fixture. Regenerate with:

```powershell
python pne_scheduler/tools/inspect_capacheck_zip.py
```
