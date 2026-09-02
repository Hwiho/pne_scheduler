# Lab corpus report (PNE unit zips)

Machine-readable: [`PNE_UNIT_CORPUS.json`](PNE_UNIT_CORPUS.json), [`PNE_UNIT_COMPARISON.json`](PNE_UNIT_COMPARISON.json)

Regenerate:

```powershell
python tools/analyze_pne_unit_corpus.py
python tools/compare_pne_units.py
```

---
## Corpus scan (per zip)

Source zips: `example/corpus_zips/PNE##.zip` (or `c:\PNE##.zip` on lab PC).

- Units: 10
- Total `.sch`: 18708
- Unknown (no protocol keyword): 12060 (64.5%)

| Unit | Files | Classified | Unknown | LOOP files | Step sizes | Rating hint |
|------|------:|-----------:|--------:|-----------:|------------|-------------|
| PNE01 | 36 | 91.7% | 8.3% | 36 | 612×36 | 500mA |
| PNE02 | 3449 | 42.7% | 57.3% | 3448 | 612×3446, 696×2 | 500mA |
| PNE03 | 1541 | 55.0% | 45.0% | 1541 | 612×1533, 696×8 | 6A |
| PNE04 | 3273 | 19.2% | 80.8% | 3273 | 612×3273 | 500mA |
| PNE05 | 1874 | 35.8% | 64.2% | 1874 | 612×1874 | 500mA |
| PNE06 | 1074 | 14.0% | 86.0% | 1074 | 612×1074 | 500mA |
| PNE07 | 1459 | 13.9% | 86.1% | 1459 | 612×1459 | 500mA |
| PNE08 | 2221 | 39.2% | 60.8% | 2221 | 612×2221 | 500mA |
| PNE09 | 2121 | 49.5% | 50.5% | 2121 | 612×2120, 696×1 | 500mA |
| PNE22 | 1660 | 43.7% | 56.3% | 1660 | 612×1660 | 100mA |

### Per-unit detail

#### PNE01 (36 files)

- LOOP goto aggregate: +564 only=167, +48 only=0, both=14, neither=0
- Official rating: **500mA** | max in corpus: 128.85 mA

- `capacheck`: 20
- `doe`: 8
- `rpt`: 5
- `unknown`: 3

- Versions: `{'0x00010003': 21, '0x00010002': 15}`
- Step sizes: `{612: 36}`
- Top layouts: `[('0x00010002/612B/15st', 11), ('0x00010003/612B/15st', 9), ('0x00010003/612B/51st', 5), ('0x00010003/612B/48st', 5), ('0x00010002/612B/48st', 4)]`

#### PNE02 (3449 files)

- LOOP goto aggregate: +564 only=20202, +48 only=3, both=300, neither=23
- Official rating: **500mA** | max in corpus: 37763.375 mA (corpus max exceeds official)

- `unknown`: 1978
- `rate_test`: 518
- `cycle_life`: 231
- `formation`: 179
- `charge`: 126
- `capacheck`: 114
- `hppc`: 82
- `qpeed`: 81
- `rpt`: 56
- `gitt`: 17
- `rest`: 14
- `discharge`: 12

- Versions: `{'0x00010003': 3344, '0x00010002': 102, '0x00010004': 2}`
- Step sizes: `{612: 3446, 696: 2}`
- Top layouts: `[('0x00010003/612B/39st', 1280), ('0x00010003/612B/9st', 636), ('0x00010003/612B/30st', 218), ('0x00010003/612B/15st', 145), ('0x00010003/612B/7st', 93)]`

#### PNE03 (1541 files)

- LOOP goto aggregate: +564 only=7890, +48 only=1, both=331, neither=57
- Official rating: **6A** | max in corpus: 6000.0 mA

- `unknown`: 694
- `formation`: 208
- `cycle_life`: 195
- `rate_test`: 126
- `rpt`: 99
- `hppc`: 91
- `capacheck`: 51
- `discharge`: 20
- `eis`: 13
- `ocv`: 12
- `dcir`: 8
- `soc_setting`: 6

- Versions: `{'0x00010003': 1484, '0x00010002': 49, '0x00010004': 8}`
- Step sizes: `{612: 1533, 696: 8}`
- Top layouts: `[('0x00010003/612B/15st', 333), ('0x00010003/612B/9st', 255), ('0x00010003/612B/6st', 57), ('0x00010003/612B/21st', 47), ('0x00010003/612B/22st', 43)]`

#### PNE04 (3273 files)

- LOOP goto aggregate: +564 only=17478, +48 only=0, both=796, neither=0
- Official rating: **500mA** | max in corpus: 8153.0 mA (corpus max exceeds official)

- `unknown`: 2645
- `hppc`: 224
- `rate_test`: 165
- `cycle_life`: 111
- `formation`: 64
- `discharge`: 22
- `charge`: 13
- `dcir`: 11
- `storage`: 7
- `rpt`: 5
- `ocv`: 3
- `qc`: 2

- Versions: `{'0x00010003': 3245, '0x00010002': 28}`
- Step sizes: `{612: 3273}`
- Top layouts: `[('0x00010003/612B/9st', 1022), ('0x00010003/612B/30st', 704), ('0x00010003/612B/39st', 387), ('0x00010003/612B/6st', 180), ('0x00010003/612B/104st', 117)]`

#### PNE05 (1874 files)

- LOOP goto aggregate: +564 only=13021, +48 only=0, both=748, neither=0
- Official rating: **500mA** | max in corpus: 499.0 mA

- `unknown`: 1203
- `hppc`: 199
- `cycle_life`: 166
- `formation`: 145
- `rate_test`: 66
- `storage`: 53
- `rpt`: 25
- `charge`: 7
- `capacheck`: 4
- `doe`: 3
- `rest`: 1
- `ocv`: 1

- Versions: `{'0x00010003': 1855, '0x00010002': 19}`
- Step sizes: `{612: 1874}`
- Top layouts: `[('0x00010003/612B/39st', 549), ('0x00010003/612B/9st', 288), ('0x00010003/612B/30st', 225), ('0x00010003/612B/104st', 138), ('0x00010003/612B/15st', 98)]`

#### PNE06 (1074 files)

- LOOP goto aggregate: +564 only=8820, +48 only=0, both=316, neither=0
- Official rating: **500mA** | max in corpus: 374.88 mA

- `unknown`: 924
- `cycle_life`: 98
- `rate_test`: 23
- `storage`: 12
- `formation`: 10
- `hppc`: 4
- `charge`: 3

- Versions: `{'0x00010003': 1074}`
- Step sizes: `{612: 1074}`
- Top layouts: `[('0x00010003/612B/39st', 346), ('0x00010003/612B/68st', 204), ('0x00010003/612B/45st', 171), ('0x00010003/612B/62st', 107), ('0x00010003/612B/9st', 84)]`

#### PNE07 (1459 files)

- LOOP goto aggregate: +564 only=12358, +48 only=0, both=297, neither=0
- Official rating: **500mA** | max in corpus: 499.0 mA

- `unknown`: 1256
- `qpeed`: 69
- `hppc`: 51
- `rate_test`: 39
- `cycle_life`: 23
- `formation`: 16
- `rpt`: 3
- `charge`: 2

- Versions: `{'0x00010003': 1447, '0x00010002': 12}`
- Step sizes: `{612: 1459}`
- Top layouts: `[('0x00010003/612B/39st', 809), ('0x00010003/612B/68st', 158), ('0x00010003/612B/62st', 85), ('0x00010003/612B/77st', 55), ('0x00010003/612B/9st', 52)]`

#### PNE08 (2221 files)

- LOOP goto aggregate: +564 only=11721, +48 only=0, both=345, neither=0
- Official rating: **500mA** | max in corpus: 174076.0 mA (corpus max exceeds official)

- `unknown`: 1350
- `formation`: 245
- `rate_test`: 186
- `rpt`: 173
- `cycle_life`: 80
- `hppc`: 78
- `qpeed`: 44
- `charge`: 20
- `ocv`: 17
- `capacheck`: 8
- `discharge`: 6
- `gitt`: 5

- Versions: `{'0x00010003': 2173, '0x00010002': 48}`
- Step sizes: `{612: 2221}`
- Top layouts: `[('0x00010003/612B/9st', 463), ('0x00010003/612B/15st', 286), ('0x00010003/612B/31st', 177), ('0x00010003/612B/30st', 166), ('0x00010003/612B/39st', 161)]`

#### PNE09 (2121 files)

- LOOP goto aggregate: +564 only=13137, +48 only=0, both=276, neither=3
- Official rating: **500mA** | max in corpus: 174227.0 mA (corpus max exceeds official)

- `unknown`: 1072
- `rate_test`: 404
- `hppc`: 148
- `formation`: 106
- `qpeed`: 93
- `cycle_life`: 75
- `storage`: 60
- `rpt`: 51
- `charge`: 47
- `ocv`: 19
- `eis`: 17
- `discharge`: 12

- Versions: `{'0x00010003': 2060, '0x00010002': 60, '0x00010004': 1}`
- Step sizes: `{612: 2120, 696: 1}`
- Top layouts: `[('0x00010003/612B/15st', 434), ('0x00010003/612B/9st', 204), ('0x00010003/612B/63st', 188), ('0x00010003/612B/39st', 163), ('0x00010003/612B/7st', 116)]`

#### PNE22 (1660 files)

- LOOP goto aggregate: +564 only=7712, +48 only=0, both=79, neither=0
- Official rating: **100mA** | max in corpus: 82300.0 mA (corpus max exceeds official)

- `unknown`: 935
- `rate_test`: 225
- `formation`: 127
- `rpt`: 114
- `hppc`: 76
- `cycle_life`: 66
- `storage`: 26
- `capacheck`: 23
- `qpeed`: 20
- `ocv`: 16
- `discharge`: 10
- `gitt`: 8

- Versions: `{'0x00010003': 1588, '0x00010002': 72}`
- Step sizes: `{612: 1660}`
- Top layouts: `[('0x00010003/612B/9st', 454), ('0x00010003/612B/39st', 359), ('0x00010003/612B/15st', 132), ('0x00010003/612B/7st', 103), ('0x00010003/612B/19st', 57)]`


---

## Cross-unit comparison

Diff from lab zip corpora (`PNE01` … `PNE09`, `PNE22`).

| Unit | Files | Unknown | Protocols | Median I (mA) | Max I (mA) | 696B | LOOP both% | Top layout |
|------|------:|--------:|----------:|--------------:|-----------:|-----:|-----------:|------------|
| PNE01 | 36 | 8.3% | 3 | 28.182 | 128.85 | 0 | 7.7% | `0x00010002/612B/15st` |
| PNE02 | 3449 | 57.3% | 19 | 6.632 | 37763.375 | 2 | 1.5% | `0x00010003/612B/39st` |
| PNE03 | 1541 | 45.0% | 16 | 64.0 | 6000.0 | 8 | 4.0% | `0x00010003/612B/15st` |
| PNE04 | 3273 | 80.8% | 12 | 2.0 | 8153.0 | 0 | 4.4% | `0x00010003/612B/9st` |
| PNE05 | 1874 | 64.2% | 12 | 5.723 | 499.0 | 0 | 5.4% | `0x00010003/612B/39st` |
| PNE06 | 1074 | 86.0% | 6 | 7.45 | 374.88 | 0 | 3.5% | `0x00010003/612B/39st` |
| PNE07 | 1459 | 86.1% | 7 | 8.05 | 499.0 | 0 | 2.3% | `0x00010003/612B/39st` |
| PNE08 | 2221 | 60.8% | 14 | 9.12 | 174076.0 | 0 | 2.9% | `0x00010003/612B/9st` |
| PNE09 | 2121 | 50.5% | 16 | 16.3 | 174227.0 | 1 | 2.1% | `0x00010003/612B/15st` |
| PNE22 | 1660 | 56.3% | 15 | 6.306 | 82300.0 | 0 | 1.0% | `0x00010003/612B/9st` |

### What is the same (all units)

- **dominant_version**: `0x00010003`
- **dominant_step_size**: `612`
- **dominant_payload_v3**: `1760`
- **dominant_payload_v2**: `1632`
- **loop_primary_offset**: `+564`
- **current_unit_in_sch**: `mA`
- **cv_cutoff_ratio_mode**: `0.5`

### Per-unit unique traits

#### PNE01

- 696B step records: none
- safety header populated: maxI=200 mA (11 files)
- high typical current (median 28.182 mA vs corpus 7.8)

**Top categories**
- `capacheck`: 20 (55.6%)
- `doe`: 8 (22.2%)
- `rpt`: 5 (13.9%)
- `unknown`: 3

**Top step counts**
- 15 steps: 20 files
- 48 steps: 9 files
- 51 steps: 5 files
- 9 steps: 2 files

**Current modes (mA)**
- 21.621 mA: 54 steps
- 27.786 mA: 27 steps
- 28.182 mA: 27 steps
- 97.294 mA: 18 steps
- 28.347 mA: 18 steps

#### PNE02

- 696B step records: 2 files
- 0x10004 (696 formation): 2 files
- safety header @0x3D8: mostly empty

**Top categories**
- `unknown`: 1978
- `rate_test`: 518 (15.0%)
- `cycle_life`: 231 (6.7%)
- `formation`: 179 (5.2%)
- `charge`: 126 (3.7%)
- `capacheck`: 114 (3.3%)
- `hppc`: 82 (2.4%)
- `qpeed`: 81 (2.3%)

**Top step counts**
- 39 steps: 1345 files
- 9 steps: 637 files
- 30 steps: 220 files
- 15 steps: 146 files
- 7 steps: 93 files

**Current modes (mA)**
- 6.08 mA: 577 steps
- 6.225 mA: 428 steps
- 1.782 mA: 266 steps
- 17.97 mA: 179 steps
- 6.155 mA: 174 steps

#### PNE03

- 696B step records: 8 files
- 0x10004 (696 formation): 8 files
- safety header populated: maxI=6000 mA (1 files)
- high typical current (median 64.0 mA vs corpus 7.8)

**Top categories**
- `unknown`: 694
- `formation`: 208 (13.5%)
- `cycle_life`: 195 (12.7%)
- `rate_test`: 126 (8.2%)
- `rpt`: 99 (6.4%)
- `hppc`: 91 (5.9%)
- `capacheck`: 51 (3.3%)
- `discharge`: 20 (1.3%)

**Top step counts**
- 15 steps: 342 files
- 9 steps: 262 files
- 6 steps: 57 files
- 21 steps: 48 files
- 22 steps: 43 files

**Current modes (mA)**
- 98.0 mA: 1019 steps
- 327.0 mA: 725 steps
- 10.0 mA: 373 steps
- 25.0 mA: 309 steps
- 19.0 mA: 261 steps

#### PNE04

- 696B step records: none
- safety header @0x3D8: mostly empty
- low typical current (median 2.0 mA vs corpus 7.8)

**Top categories**
- `unknown`: 2645
- `hppc`: 224 (6.8%)
- `rate_test`: 165 (5.0%)
- `cycle_life`: 111 (3.4%)
- `formation`: 64 (2.0%)
- `discharge`: 22 (0.7%)
- `charge`: 13 (0.4%)
- `dcir`: 11 (0.3%)

**Top step counts**
- 9 steps: 1025 files
- 30 steps: 705 files
- 39 steps: 387 files
- 6 steps: 180 files
- 104 steps: 122 files

**Current modes (mA)**
- 1.977 mA: 177 steps
- 1.878 mA: 167 steps
- 1.935 mA: 164 steps
- 1.874 mA: 158 steps
- 1.252 mA: 156 steps

#### PNE05

- 696B step records: none
- safety header @0x3D8: mostly empty

**Top categories**
- `unknown`: 1203
- `hppc`: 199 (10.6%)
- `cycle_life`: 166 (8.9%)
- `formation`: 145 (7.7%)
- `rate_test`: 66 (3.5%)
- `storage`: 53 (2.8%)
- `rpt`: 25 (1.3%)
- `charge`: 7 (0.4%)

**Top step counts**
- 39 steps: 555 files
- 9 steps: 289 files
- 30 steps: 225 files
- 104 steps: 140 files
- 15 steps: 102 files

**Current modes (mA)**
- 1.068 mA: 166 steps
- 1.252 mA: 141 steps
- 1.128 mA: 130 steps
- 1.748 mA: 129 steps
- 1.22 mA: 124 steps

#### PNE06

- 696B step records: none
- safety header @0x3D8: mostly empty

**Top categories**
- `unknown`: 924
- `cycle_life`: 98 (9.1%)
- `rate_test`: 23 (2.1%)
- `storage`: 12 (1.1%)
- `formation`: 10 (0.9%)
- `hppc`: 4 (0.4%)
- `charge`: 3 (0.3%)

**Top step counts**
- 39 steps: 346 files
- 68 steps: 204 files
- 45 steps: 171 files
- 62 steps: 107 files
- 9 steps: 84 files

**Current modes (mA)**
- 7.45 mA: 1300 steps
- 6.042 mA: 660 steps
- 74.5 mA: 451 steps
- 6.4 mA: 401 steps
- 7.369 mA: 377 steps

#### PNE07

- 696B step records: none
- safety header @0x3D8: mostly empty

**Top categories**
- `unknown`: 1256
- `qpeed`: 69 (4.7%)
- `hppc`: 51 (3.5%)
- `rate_test`: 39 (2.7%)
- `cycle_life`: 23 (1.6%)
- `formation`: 16 (1.1%)
- `rpt`: 3 (0.2%)
- `charge`: 2 (0.1%)

**Top step counts**
- 39 steps: 809 files
- 68 steps: 159 files
- 62 steps: 86 files
- 77 steps: 64 files
- 9 steps: 52 files

**Current modes (mA)**
- 6.3 mA: 889 steps
- 7.8 mA: 542 steps
- 6.25 mA: 455 steps
- 8.05 mA: 444 steps
- 6.49 mA: 291 steps

#### PNE08

- 696B step records: none
- safety header populated: maxI=600 mA (2 files)

**Top categories**
- `unknown`: 1350
- `formation`: 245 (11.0%)
- `rate_test`: 186 (8.4%)
- `rpt`: 173 (7.8%)
- `cycle_life`: 80 (3.6%)
- `hppc`: 78 (3.5%)
- `qpeed`: 44 (2.0%)
- `charge`: 20 (0.9%)

**Top step counts**
- 9 steps: 464 files
- 15 steps: 293 files
- 31 steps: 177 files
- 30 steps: 167 files
- 39 steps: 162 files

**Current modes (mA)**
- 6.225 mA: 601 steps
- 21.78 mA: 254 steps
- 8.363 mA: 234 steps
- 8.052 mA: 180 steps
- 6.6 mA: 170 steps

#### PNE09

- 696B step records: 1 files
- 0x10004 (696 formation): 1 files
- safety header populated: maxI=600 mA (6 files)

**Top categories**
- `unknown`: 1072
- `rate_test`: 404 (19.0%)
- `hppc`: 148 (7.0%)
- `formation`: 106 (5.0%)
- `qpeed`: 93 (4.4%)
- `cycle_life`: 75 (3.5%)
- `storage`: 60 (2.8%)
- `rpt`: 51 (2.4%)

**Top step counts**
- 15 steps: 435 files
- 9 steps: 208 files
- 63 steps: 188 files
- 39 steps: 164 files
- 7 steps: 117 files

**Current modes (mA)**
- 8.25 mA: 1423 steps
- 27.225 mA: 429 steps
- 17.967 mA: 289 steps
- 6.64 mA: 252 steps
- 41.25 mA: 245 steps

#### PNE22

- 696B step records: none
- safety header populated: maxI=600 mA (1 files)

**Top categories**
- `unknown`: 935
- `rate_test`: 225 (13.6%)
- `formation`: 127 (7.7%)
- `rpt`: 114 (6.9%)
- `hppc`: 76 (4.6%)
- `cycle_life`: 66 (4.0%)
- `storage`: 26 (1.6%)
- `capacheck`: 23 (1.4%)

**Top step counts**
- 9 steps: 468 files
- 39 steps: 383 files
- 15 steps: 136 files
- 7 steps: 103 files
- 19 steps: 57 files

**Current modes (mA)**
- 1.833 mA: 159 steps
- 5.932 mA: 132 steps
- 1.842 mA: 131 steps
- 1.86 mA: 129 steps
- 1.21 mA: 128 steps


### Category mix divergence (vs corpus average)

| Unit | Category | Unit% | Corpus% | Δ pp |
|------|----------|------:|--------:|-----:|
| PNE01 | `capacheck` | 55.6% | 1.2% | +54.4 |
| PNE01 | `doe` | 22.2% | 0.1% | +22.2 |
| PNE01 | `rpt` | 13.9% | 2.8% | +11.0 |
| PNE09 | `rate_test` | 19.0% | 9.4% | +9.7 |
| PNE03 | `formation` | 13.5% | 5.9% | +7.6 |
| PNE06 | `rate_test` | 2.1% | 9.4% | -7.2 |
| PNE03 | `cycle_life` | 12.7% | 5.6% | +7.1 |
| PNE07 | `rate_test` | 2.7% | 9.4% | -6.7 |
| PNE05 | `rate_test` | 3.5% | 9.4% | -5.9 |
| PNE02 | `rate_test` | 15.0% | 9.4% | +5.6 |
| PNE05 | `hppc` | 10.6% | 5.1% | +5.5 |
| PNE08 | `formation` | 11.0% | 5.9% | +5.1 |
| PNE06 | `formation` | 0.9% | 5.9% | -5.0 |
| PNE08 | `rpt` | 7.8% | 2.8% | +4.9 |
| PNE07 | `formation` | 1.1% | 5.9% | -4.8 |
| PNE06 | `hppc` | 0.4% | 5.1% | -4.7 |
| PNE04 | `rate_test` | 5.0% | 9.4% | -4.3 |
| PNE22 | `rate_test` | 13.6% | 9.4% | +4.2 |
| PNE07 | `cycle_life` | 1.6% | 5.6% | -4.0 |
| PNE22 | `rpt` | 6.9% | 2.8% | +4.0 |

### Interpretation notes

- **Unknown filenames** are mostly project/material names; low unknown% (PNE01) means clearer naming, not better binary.
- **Max I (mA)** in a zip reflects stored schedule values (cell size × C-rate), not always equipment rating.
- **696B / 0x10004** is a file-format generation, not tied to one cycler — but only PNE02/PNE03 have any in this corpus.
- **LOOP both%** = nested loop steps with both +48 and +564 populated; higher on complex HPPC/RPT schedules.
