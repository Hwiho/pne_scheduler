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

- Units: 20
- Total `.sch`: 29153
- Unknown (no protocol keyword): 10956 (37.6%)

| Unit | Files | Classified | Unknown | LOOP files | Step sizes | Rating hint |
|------|------:|-----------:|--------:|-----------:|------------|-------------|
| PNE01 | 36 | 91.7% | 8.3% | 36 | 612×36 | 500mA |
| PNE02 | 3449 | 75.7% | 24.3% | 3448 | 612×3446, 696×2 | 500mA |
| PNE03 | 1541 | 65.8% | 34.2% | 1541 | 612×1533, 696×8 | 6A |
| PNE04 | 3273 | 34.6% | 65.4% | 3273 | 612×3273 | 500mA |
| PNE05 | 1874 | 68.5% | 31.5% | 1874 | 612×1874 | 500mA |
| PNE06 | 1074 | 61.3% | 38.7% | 1074 | 612×1074 | 500mA |
| PNE07 | 1459 | 73.5% | 26.5% | 1459 | 612×1459 | 500mA |
| PNE08 | 2221 | 58.9% | 41.1% | 2221 | 612×2221 | 500mA |
| PNE09 | 2121 | 66.2% | 33.8% | 2121 | 612×2120, 696×1 | 500mA |
| PNE10 | 1832 | 75.3% | 24.7% | 1832 | 612×1832 | 500mA |
| PNE11 | 1828 | 68.2% | 31.8% | 1827 | 612×1825, 696×2 | 500mA |
| PNE12 | 222 | 78.4% | 21.6% | 220 | 612×220 | 20A |
| PNE13 | 414 | 45.7% | 54.3% | 413 | 612×413 | 20A |
| PNE14 | 277 | 55.6% | 44.4% | 276 | 612×274, 696×2 | 20A |
| PNE15 | 2732 | 58.4% | 41.6% | 2731 | 696×1927, 720×609, 612×195 | 6A |
| PNE16 | 2453 | 64.4% | 35.6% | 2450 | 696×2048, 720×221, 612×181 | 6A |
| PNE18 | 57 | 17.5% | 82.5% | 57 | 612×57 | 6A |
| PNE19 | 276 | 34.8% | 65.2% | 275 | 696×267, 612×8 | 6A |
| PNE20 | 354 | 31.4% | 68.6% | 353 | 696×343, 612×10 | 6A |
| PNE22 | 1660 | 69.0% | 31.0% | 1660 | 612×1660 | 100mA |

### Per-unit detail

#### PNE01 (36 files)

- LOOP goto aggregate: +564 only=167, +48 only=0, both=14, neither=0
- Official rating: **500mA** | max in corpus: 128.85 mA

- `capacheck`: 20
- `doe`: 13
- `unknown`: 3

- Versions: `{'0x00010003': 21, '0x00010002': 15}`
- Step sizes: `{612: 36}`
- Top layouts: `[('0x00010002/612B/15st', 11), ('0x00010003/612B/15st', 9), ('0x00010003/612B/51st', 5), ('0x00010003/612B/48st', 5), ('0x00010002/612B/48st', 4)]`

#### PNE02 (3449 files)

- LOOP goto aggregate: +564 only=20202, +48 only=3, both=300, neither=23
- Official rating: **500mA** | max in corpus: 37763.375 mA (corpus max exceeds official)

- `rate_capability`: 1463
- `unknown`: 839
- `cycle_life`: 244
- `formation`: 187
- `charge`: 145
- `capacheck`: 114
- `rate_test`: 96
- `qpeed`: 90
- `hppc`: 84
- `rpt`: 54
- `dcir`: 25
- `soc_setting`: 22

- Versions: `{'0x00010003': 3344, '0x00010002': 102, '0x00010004': 2}`
- Step sizes: `{612: 3446, 696: 2}`
- Top layouts: `[('0x00010003/612B/39st', 1280), ('0x00010003/612B/9st', 636), ('0x00010003/612B/30st', 218), ('0x00010003/612B/15st', 145), ('0x00010003/612B/7st', 93)]`

#### PNE03 (1541 files)

- LOOP goto aggregate: +564 only=7890, +48 only=1, both=331, neither=57
- Official rating: **6A** | max in corpus: 6000.0 mA

- `unknown`: 527
- `cycle_life`: 214
- `formation`: 181
- `rate_test`: 136
- `hppc`: 128
- `rpt`: 87
- `rate_capability`: 82
- `doe`: 62
- `capacheck`: 51
- `eis`: 13
- `discharge`: 12
- `dcir`: 8

- Versions: `{'0x00010003': 1484, '0x00010002': 49, '0x00010004': 8}`
- Step sizes: `{612: 1533, 696: 8}`
- Top layouts: `[('0x00010003/612B/15st', 333), ('0x00010003/612B/9st', 255), ('0x00010003/612B/6st', 57), ('0x00010003/612B/21st', 47), ('0x00010003/612B/22st', 43)]`

#### PNE04 (3273 files)

- LOOP goto aggregate: +564 only=17478, +48 only=0, both=796, neither=0
- Official rating: **500mA** | max in corpus: 8153.0 mA (corpus max exceeds official)

- `unknown`: 2141
- `rate_capability`: 468
- `hppc`: 354
- `cycle_life`: 142
- `formation`: 64
- `discharge`: 30
- `rate_test`: 26
- `charge`: 16
- `dcir`: 11
- `storage`: 7
- `ocv`: 5
- `qc`: 4

- Versions: `{'0x00010003': 3245, '0x00010002': 28}`
- Step sizes: `{612: 3273}`
- Top layouts: `[('0x00010003/612B/9st', 1022), ('0x00010003/612B/30st', 704), ('0x00010003/612B/39st', 387), ('0x00010003/612B/6st', 180), ('0x00010003/612B/104st', 117)]`

#### PNE05 (1874 files)

- LOOP goto aggregate: +564 only=13021, +48 only=0, both=748, neither=0
- Official rating: **500mA** | max in corpus: 499.0 mA

- `unknown`: 591
- `rate_capability`: 568
- `hppc`: 233
- `cycle_life`: 197
- `formation`: 166
- `storage`: 70
- `rpt`: 25
- `charge`: 10
- `capacheck`: 4
- `rate_test`: 4
- `doe`: 3
- `rest`: 1

- Versions: `{'0x00010003': 1855, '0x00010002': 19}`
- Step sizes: `{612: 1874}`
- Top layouts: `[('0x00010003/612B/39st', 549), ('0x00010003/612B/9st', 288), ('0x00010003/612B/30st', 225), ('0x00010003/612B/104st', 138), ('0x00010003/612B/15st', 98)]`

#### PNE06 (1074 files)

- LOOP goto aggregate: +564 only=8820, +48 only=0, both=316, neither=0
- Official rating: **500mA** | max in corpus: 374.88 mA

- `unknown`: 416
- `rate_capability`: 350
- `cycle_life`: 266
- `hppc`: 18
- `storage`: 14
- `doe`: 6
- `charge`: 3
- `formation`: 1

- Versions: `{'0x00010003': 1074}`
- Step sizes: `{612: 1074}`
- Top layouts: `[('0x00010003/612B/39st', 346), ('0x00010003/612B/68st', 204), ('0x00010003/612B/45st', 171), ('0x00010003/612B/62st', 107), ('0x00010003/612B/9st', 84)]`

#### PNE07 (1459 files)

- LOOP goto aggregate: +564 only=12358, +48 only=0, both=297, neither=0
- Official rating: **500mA** | max in corpus: 499.0 mA

- `rate_capability`: 800
- `unknown`: 386
- `hppc`: 112
- `qpeed`: 69
- `formation`: 43
- `cycle_life`: 32
- `rate_test`: 8
- `doe`: 4
- `rpt`: 3
- `charge`: 2

- Versions: `{'0x00010003': 1447, '0x00010002': 12}`
- Step sizes: `{612: 1459}`
- Top layouts: `[('0x00010003/612B/39st', 809), ('0x00010003/612B/68st', 158), ('0x00010003/612B/62st', 85), ('0x00010003/612B/77st', 55), ('0x00010003/612B/9st', 52)]`

#### PNE08 (2221 files)

- LOOP goto aggregate: +564 only=11721, +48 only=0, both=345, neither=0
- Official rating: **500mA** | max in corpus: 174076.0 mA (corpus max exceeds official)

- `unknown`: 912
- `cycle_life`: 287
- `formation`: 284
- `rate_capability`: 281
- `rpt`: 157
- `hppc`: 87
- `rate_test`: 85
- `qpeed`: 44
- `charge`: 20
- `ocv`: 17
- `discharge`: 16
- `doe`: 11

- Versions: `{'0x00010003': 2173, '0x00010002': 48}`
- Step sizes: `{612: 2221}`
- Top layouts: `[('0x00010003/612B/9st', 463), ('0x00010003/612B/15st', 286), ('0x00010003/612B/31st', 177), ('0x00010003/612B/30st', 166), ('0x00010003/612B/39st', 161)]`

#### PNE09 (2121 files)

- LOOP goto aggregate: +564 only=13137, +48 only=0, both=276, neither=3
- Official rating: **500mA** | max in corpus: 174227.0 mA (corpus max exceeds official)

- `unknown`: 717
- `rate_capability`: 429
- `hppc`: 181
- `rate_test`: 167
- `formation`: 122
- `cycle_life`: 119
- `qpeed`: 116
- `storage`: 86
- `rpt`: 48
- `charge`: 41
- `ocv`: 22
- `dcir`: 17

- Versions: `{'0x00010003': 2060, '0x00010002': 60, '0x00010004': 1}`
- Step sizes: `{612: 2120, 696: 1}`
- Top layouts: `[('0x00010003/612B/15st', 434), ('0x00010003/612B/9st', 204), ('0x00010003/612B/63st', 188), ('0x00010003/612B/39st', 163), ('0x00010003/612B/7st', 116)]`

#### PNE10 (1832 files)

- LOOP goto aggregate: +564 only=15347, +48 only=0, both=470, neither=0
- Official rating: **500mA** | max in corpus: 496.0 mA

- `rate_capability`: 509
- `unknown`: 452
- `cycle_life`: 249
- `hppc`: 201
- `qpeed`: 153
- `formation`: 119
- `rate_test`: 54
- `charge`: 35
- `rest`: 13
- `discharge`: 11
- `dcir`: 8
- `capacheck`: 8

- Versions: `{'0x00010003': 1769, '0x00010002': 63}`
- Step sizes: `{612: 1832}`
- Top layouts: `[('0x00010003/612B/39st', 407), ('0x00010003/612B/68st', 227), ('0x00010003/612B/45st', 146), ('0x00010003/612B/15st', 107), ('0x00010003/612B/33st', 82)]`

#### PNE11 (1828 files)

- LOOP goto aggregate: +564 only=17967, +48 only=2, both=400, neither=10
- Official rating: **500mA** | max in corpus: 393.216 mA

- `unknown`: 582
- `hppc`: 430
- `qpeed`: 332
- `formation`: 188
- `cycle_life`: 155
- `rate_capability`: 96
- `rate_test`: 13
- `discharge`: 8
- `qc`: 8
- `rpt`: 4
- `charge`: 4
- `soc_setting`: 2

- Versions: `{'0x00010003': 1731, '0x00010002': 94, '0x00010004': 2}`
- Step sizes: `{612: 1825, 696: 2}`
- Top layouts: `[('0x00010003/612B/101st', 262), ('0x00010003/612B/69st', 176), ('0x00010003/612B/82st', 120), ('0x00010003/612B/65st', 111), ('0x00010003/612B/45st', 88)]`

#### PNE12 (222 files)

- LOOP goto aggregate: +564 only=1058, +48 only=0, both=14, neither=0
- Official rating: **20A** | max in corpus: 20000.0 mA

- `cycle_life`: 52
- `rpt`: 49
- `unknown`: 48
- `hppc`: 25
- `ocv`: 15
- `rate_test`: 12
- `formation`: 7
- `capacheck`: 6
- `discharge`: 5
- `rate_capability`: 2
- `rest`: 1

- Versions: `{'0x00010003': 210, '0x00010002': 10}`
- Step sizes: `{612: 220}`
- Top layouts: `[('0x00010003/612B/9st', 32), ('0x00010003/612B/21st', 28), ('0x00010003/612B/41st', 21), ('0x00010003/612B/45st', 20), ('0x00010003/612B/6st', 20)]`

#### PNE13 (414 files)

- LOOP goto aggregate: +564 only=1958, +48 only=0, both=117, neither=0
- Official rating: **20A** | max in corpus: 12500.0 mA

- `unknown`: 225
- `hppc`: 41
- `ocv`: 26
- `cycle_life`: 22
- `rpt`: 21
- `formation`: 21
- `rate_capability`: 12
- `rate_test`: 12
- `discharge`: 10
- `rest`: 8
- `storage`: 7
- `charge`: 5

- Versions: `{'0x00010003': 398, '0x00010002': 15}`
- Step sizes: `{612: 413}`
- Top layouts: `[('0x00010003/612B/15st', 92), ('0x00010003/612B/7st', 53), ('0x00010003/612B/9st', 47), ('0x00010003/612B/13st', 26), ('0x00010003/612B/8st', 26)]`

#### PNE14 (277 files)

- LOOP goto aggregate: +564 only=1015, +48 only=0, both=27, neither=4
- Official rating: **20A** | max in corpus: 86250.0 mA (corpus max exceeds official)

- `unknown`: 123
- `rate_test`: 58
- `cycle_life`: 25
- `hppc`: 16
- `rpt`: 15
- `formation`: 9
- `discharge`: 7
- `capacheck`: 6
- `ocv`: 6
- `storage`: 5
- `rate_capability`: 4
- `rest`: 3

- Versions: `{'0x00010003': 262, '0x00010002': 12, '0x00010004': 2}`
- Step sizes: `{612: 274, 696: 2}`
- Top layouts: `[('0x00010003/612B/9st', 57), ('0x00010003/612B/15st', 34), ('0x00010003/612B/6st', 19), ('0x00010003/612B/33st', 18), ('0x00010003/612B/7st', 15)]`

#### PNE15 (2732 files)

- LOOP goto aggregate: +564 only=1667, +48 only=472, both=281, neither=10367
- Official rating: **6A** | max in corpus: 11190.0 mA (corpus max exceeds official)

- `unknown`: 1137
- `formation`: 426
- `cycle_life`: 399
- `hppc`: 176
- `rate_test`: 156
- `rate_capability`: 104
- `capacheck`: 88
- `doe`: 50
- `storage`: 50
- `discharge`: 30
- `rpt`: 30
- `rest`: 24

- Versions: `{'0x00010004': 1927, '0x00010005': 609, '0x00010002': 195}`
- Step sizes: `{696: 1927, 720: 609, 612: 195}`
- Top layouts: `[('0x00010004/696B/15st', 435), ('0x00010004/696B/9st', 425), ('0x00010004/696B/12st', 227), ('0x00010005/720B/15st', 181), ('0x00010005/720B/21st', 156)]`

#### PNE16 (2453 files)

- LOOP goto aggregate: +564 only=1165, +48 only=438, both=163, neither=7646
- Official rating: **6A** | max in corpus: 9440.0 mA (corpus max exceeds official)

- `unknown`: 873
- `cycle_life`: 440
- `formation`: 295
- `hppc`: 174
- `rate_capability`: 174
- `rate_test`: 163
- `capacheck`: 71
- `rpt`: 54
- `storage`: 53
- `charge`: 43
- `discharge`: 31
- `qc`: 27

- Versions: `{'0x00010004': 2048, '0x00010005': 221, '0x00010002': 179, '0x00010003': 2}`
- Step sizes: `{696: 2048, 720: 221, 612: 181}`
- Top layouts: `[('0x00010004/696B/12st', 348), ('0x00010004/696B/9st', 326), ('0x00010004/696B/6st', 262), ('0x00010004/696B/15st', 130), ('0x00010005/720B/15st', 125)]`

#### PNE18 (57 files)

- LOOP goto aggregate: +564 only=479, +48 only=0, both=15, neither=0
- Official rating: **6A** | max in corpus: 78.0 mA

- `unknown`: 47
- `hppc`: 4
- `storage`: 3
- `ocv`: 2
- `cycle_life`: 1

- Versions: `{'0x00010003': 53, '0x00010002': 4}`
- Step sizes: `{612: 57}`
- Top layouts: `[('0x00010003/612B/68st', 25), ('0x00010003/612B/35st', 11), ('0x00010003/612B/15st', 8), ('0x00010003/612B/10st', 4), ('0x00010003/612B/3st', 2)]`

#### PNE19 (276 files)

- LOOP goto aggregate: +564 only=73, +48 only=8, both=2, neither=1106
- Official rating: **6A** | max in corpus: 1045.0 mA

- `unknown`: 180
- `storage`: 23
- `formation`: 22
- `cycle_life`: 18
- `rpt`: 12
- `rate_test`: 7
- `ocv`: 5
- `rest`: 5
- `rate_capability`: 3
- `qpeed`: 1

- Versions: `{'0x00010004': 267, '0x00010002': 8}`
- Step sizes: `{696: 267, 612: 8}`
- Top layouts: `[('0x00010004/696B/15st', 67), ('0x00010004/696B/33st', 60), ('0x00010004/696B/6st', 45), ('0x00010004/696B/9st', 29), ('0x00010004/696B/13st', 13)]`

#### PNE20 (354 files)

- LOOP goto aggregate: +564 only=105, +48 only=35, both=12, neither=1132
- Official rating: **6A** | max in corpus: 605.0 mA

- `unknown`: 243
- `rate_test`: 35
- `cycle_life`: 23
- `rate_capability`: 20
- `hppc`: 20
- `rest`: 4
- `formation`: 4
- `ocv`: 3
- `rpt`: 2

- Versions: `{'0x00010004': 343, '0x00010002': 10}`
- Step sizes: `{696: 343, 612: 10}`
- Top layouts: `[('0x00010004/696B/15st', 265), ('0x00010004/696B/27st', 19), ('0x00010004/696B/9st', 12), ('0x00010004/696B/7st', 11), ('0x00010004/696B/79st', 9)]`

#### PNE22 (1660 files)

- LOOP goto aggregate: +564 only=7712, +48 only=0, both=79, neither=0
- Official rating: **100mA** | max in corpus: 82300.0 mA (corpus max exceeds official)

- `unknown`: 514
- `rate_capability`: 436
- `rate_test`: 157
- `formation`: 108
- `rpt`: 104
- `cycle_life`: 93
- `hppc`: 82
- `storage`: 42
- `doe`: 25
- `capacheck`: 23
- `ocv`: 20
- `qpeed`: 20

- Versions: `{'0x00010003': 1588, '0x00010002': 72}`
- Step sizes: `{612: 1660}`
- Top layouts: `[('0x00010003/612B/9st', 454), ('0x00010003/612B/39st', 359), ('0x00010003/612B/15st', 132), ('0x00010003/612B/7st', 103), ('0x00010003/612B/19st', 57)]`


---

## Cross-unit comparison

Diff from lab zip corpora (`PNE01` … `PNE09`, `PNE22`).

| Unit | Files | Unknown | Protocols | Median I (mA) | Max I (mA) | 696B | LOOP both% | Top layout |
|------|------:|--------:|----------:|--------------:|-----------:|-----:|-----------:|------------|
| PNE01 | 36 | 8.3% | 2 | 28.182 | 128.85 | 0 | 7.7% | `0x00010002/612B/15st` |
| PNE02 | 3449 | 55.6% | 20 | 6.632 | 37763.375 | 2 | 1.5% | `0x00010003/612B/39st` |
| PNE03 | 1541 | 43.5% | 17 | 64.0 | 6000.0 | 8 | 4.0% | `0x00010003/612B/15st` |
| PNE04 | 3273 | 79.8% | 13 | 2.0 | 8153.0 | 0 | 4.4% | `0x00010003/612B/9st` |
| PNE05 | 1874 | 62.7% | 13 | 5.723 | 499.0 | 0 | 5.4% | `0x00010003/612B/39st` |
| PNE06 | 1074 | 83.2% | 7 | 7.45 | 374.88 | 0 | 3.5% | `0x00010003/612B/39st` |
| PNE07 | 1459 | 85.3% | 8 | 8.05 | 499.0 | 0 | 2.3% | `0x00010003/612B/39st` |
| PNE08 | 2221 | 58.3% | 16 | 9.12 | 174076.0 | 0 | 2.9% | `0x00010003/612B/9st` |
| PNE09 | 2121 | 46.1% | 18 | 16.3 | 174227.0 | 1 | 2.1% | `0x00010003/612B/15st` |
| PNE10 | 1832 | 54.5% | 16 | 8.0 | 496.0 | 0 | 3.0% | `0x00010003/612B/39st` |
| PNE11 | 1828 | 49.0% | 14 | 7.814 | 393.216 | 2 | 2.2% | `0x00010003/612B/101st` |
| PNE12 | 222 | 23.4% | 9 | 3092.0 | 20000.0 | 0 | 1.3% | `0x00010003/612B/9st` |
| PNE13 | 414 | 58.2% | 12 | 327.0 | 12500.0 | 0 | 5.6% | `0x00010003/612B/15st` |
| PNE14 | 277 | 57.0% | 9 | 1486.5 | 86250.0 | 2 | 2.6% | `0x00010003/612B/9st` |
| PNE15 | 2732 | 45.3% | 17 | 98.0 | 11190.0 | 1927 | 2.2% | `0x00010004/696B/15st` |
| PNE16 | 2453 | 40.6% | 18 | 89.0 | 9440.0 | 2048 | 1.7% | `0x00010004/696B/12st` |
| PNE18 | 57 | 82.5% | 4 | 7.0 | 78.0 | 0 | 3.0% | `0x00010003/612B/68st` |
| PNE19 | 276 | 75.7% | 6 | 30.0 | 1045.0 | 267 | 0.2% | `0x00010004/696B/15st` |
| PNE20 | 354 | 76.6% | 7 | 29.0 | 605.0 | 343 | 0.9% | `0x00010004/696B/15st` |
| PNE22 | 1660 | 55.2% | 15 | 6.306 | 82300.0 | 0 | 1.0% | `0x00010003/612B/9st` |

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

**Top categories**
- `capacheck`: 20 (55.6%)
- `doe`: 13 (36.1%)
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
- `unknown`: 1919
- `rate_test`: 525 (15.2%)
- `cycle_life`: 232 (6.7%)
- `formation`: 186 (5.4%)
- `charge`: 124 (3.6%)
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
- high typical current (median 64.0 mA vs corpus 12.7)

**Top categories**
- `unknown`: 670
- `cycle_life`: 201 (13.0%)
- `formation`: 172 (11.2%)
- `rate_test`: 133 (8.6%)
- `hppc`: 105 (6.8%)
- `rpt`: 82 (5.3%)
- `doe`: 62 (4.0%)
- `capacheck`: 51 (3.3%)

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
- low typical current (median 2.0 mA vs corpus 12.7)

**Top categories**
- `unknown`: 2612
- `hppc`: 227 (6.9%)
- `rate_test`: 167 (5.1%)
- `cycle_life`: 124 (3.8%)
- `formation`: 64 (2.0%)
- `discharge`: 35 (1.1%)
- `charge`: 12 (0.4%)
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
- `unknown`: 1175
- `hppc`: 199 (10.6%)
- `cycle_life`: 171 (9.1%)
- `formation`: 166 (8.9%)
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
- `unknown`: 894
- `cycle_life`: 107 (10.0%)
- `doe`: 32 (3.0%)
- `rate_test`: 19 (1.8%)
- `storage`: 13 (1.2%)
- `hppc`: 4 (0.4%)
- `charge`: 3 (0.3%)
- `formation`: 2 (0.2%)

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
- `unknown`: 1244
- `qpeed`: 69 (4.7%)
- `hppc`: 51 (3.5%)
- `rate_test`: 39 (2.7%)
- `cycle_life`: 23 (1.6%)
- `formation`: 16 (1.1%)
- `doe`: 12 (0.8%)
- `rpt`: 3 (0.2%)

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
- `unknown`: 1295
- `formation`: 240 (10.8%)
- `rate_test`: 189 (8.5%)
- `rpt`: 157 (7.1%)
- `cycle_life`: 127 (5.7%)
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
- `unknown`: 978
- `rate_test`: 458 (21.6%)
- `hppc`: 147 (6.9%)
- `formation`: 113 (5.3%)
- `qpeed`: 93 (4.4%)
- `storage`: 87 (4.1%)
- `cycle_life`: 85 (4.0%)
- `rpt`: 48 (2.3%)

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

#### PNE10

- 696B step records: none
- safety header @0x3D8: mostly empty

**Top categories**
- `unknown`: 998
- `rate_test`: 271 (14.8%)
- `hppc`: 173 (9.4%)
- `qpeed`: 129 (7.0%)
- `cycle_life`: 126 (6.9%)
- `formation`: 57 (3.1%)
- `charge`: 27 (1.5%)
- `discharge`: 11 (0.6%)

**Top step counts**
- 39 steps: 410 files
- 68 steps: 227 files
- 45 steps: 147 files
- 15 steps: 112 files
- 33 steps: 88 files

**Current modes (mA)**
- 6.8 mA: 1356 steps
- 6.7 mA: 540 steps
- 68.0 mA: 452 steps
- 7.9 mA: 428 steps
- 26.4 mA: 290 steps

#### PNE11

- 696B step records: 2 files
- 0x10004 (696 formation): 2 files
- safety header @0x3D8: mostly empty

**Top categories**
- `unknown`: 896
- `hppc`: 387 (21.2%)
- `qpeed`: 209 (11.4%)
- `formation`: 159 (8.7%)
- `cycle_life`: 116 (6.3%)
- `rate_test`: 31 (1.7%)
- `qc`: 8 (0.4%)
- `discharge`: 4 (0.2%)

**Top step counts**
- 101 steps: 268 files
- 69 steps: 191 files
- 82 steps: 126 files
- 65 steps: 125 files
- 45 steps: 88 files

**Current modes (mA)**
- 13.304 mA: 192 steps
- 7.665 mA: 169 steps
- 7.019 mA: 154 steps
- 7.678 mA: 154 steps
- 6.675 mA: 147 steps

#### PNE12

- 696B step records: none
- safety header @0x3D8: mostly empty
- high typical current (median 3092.0 mA vs corpus 12.7)

**Top categories**
- `cycle_life`: 52 (23.4%)
- `unknown`: 52
- `rpt`: 49 (22.1%)
- `hppc`: 25 (11.3%)
- `ocv`: 15 (6.8%)
- `rate_test`: 12 (5.4%)
- `formation`: 7 (3.2%)
- `capacheck`: 6 (2.7%)

**Top step counts**
- 9 steps: 33 files
- 21 steps: 28 files
- 45 steps: 21 files
- 41 steps: 21 files
- 6 steps: 20 files

**Current modes (mA)**
- 3092.0 mA: 205 steps
- 5400.0 mA: 190 steps
- 3123.0 mA: 136 steps
- 14055.0 mA: 117 steps
- 937.0 mA: 75 steps

#### PNE13

- 696B step records: none
- safety header @0x3D8: mostly empty
- high typical current (median 327.0 mA vs corpus 12.7)

**Top categories**
- `unknown`: 241
- `hppc`: 41 (9.9%)
- `ocv`: 26 (6.3%)
- `rpt`: 21 (5.1%)
- `rate_test`: 19 (4.6%)
- `cycle_life`: 18 (4.3%)
- `formation`: 17 (4.1%)
- `discharge`: 8 (1.9%)

**Top step counts**
- 15 steps: 93 files
- 7 steps: 55 files
- 9 steps: 50 files
- 13 steps: 26 files
- 8 steps: 26 files

**Current modes (mA)**
- 124.0 mA: 211 steps
- 125.0 mA: 138 steps
- 110.0 mA: 129 steps
- 100.0 mA: 100 steps
- 120.0 mA: 82 steps

#### PNE14

- 696B step records: 2 files
- 0x10004 (696 formation): 2 files
- safety header @0x3D8: mostly empty
- high typical current (median 1486.5 mA vs corpus 12.7)

**Top categories**
- `unknown`: 158
- `rate_test`: 41 (14.8%)
- `cycle_life`: 17 (6.1%)
- `hppc`: 16 (5.8%)
- `rpt`: 15 (5.4%)
- `formation`: 9 (3.2%)
- `discharge`: 6 (2.2%)
- `capacheck`: 6 (2.2%)

**Top step counts**
- 9 steps: 59 files
- 15 steps: 35 files
- 33 steps: 19 files
- 6 steps: 19 files
- 7 steps: 15 files

**Current modes (mA)**
- 244.0 mA: 99 steps
- 5400.0 mA: 80 steps
- 5811.0 mA: 41 steps
- 1962.0 mA: 40 steps
- 1055.0 mA: 38 steps

#### PNE15

- 696B step records: 1927 files
- 0x10004 (696 formation): 1927 files
- safety header populated: maxI=500 mA (72 files)
- high typical current (median 98.0 mA vs corpus 12.7)

**Top categories**
- `unknown`: 1238
- `formation`: 422 (15.4%)
- `cycle_life`: 378 (13.8%)
- `rate_test`: 232 (8.5%)
- `hppc`: 160 (5.9%)
- `capacheck`: 88 (3.2%)
- `doe`: 50 (1.8%)
- `storage`: 49 (1.8%)

**Top step counts**
- 15 steps: 649 files
- 9 steps: 470 files
- 21 steps: 232 files
- 12 steps: 230 files
- 7 steps: 86 files

**Current modes (mA)**
- 98.0 mA: 2095 steps
- 327.0 mA: 1554 steps
- 490.0 mA: 538 steps
- 980.0 mA: 437 steps
- 33.0 mA: 415 steps

#### PNE16

- 696B step records: 2048 files
- 0x10004 (696 formation): 2048 files
- safety header populated: maxI=500 mA (49 files)
- high typical current (median 89.0 mA vs corpus 12.7)

**Top categories**
- `unknown`: 995
- `cycle_life`: 396 (16.1%)
- `rate_test`: 312 (12.7%)
- `formation`: 289 (11.8%)
- `hppc`: 174 (7.1%)
- `capacheck`: 71 (2.9%)
- `rpt`: 54 (2.2%)
- `storage`: 42 (1.7%)

**Top step counts**
- 12 steps: 348 files
- 9 steps: 344 files
- 15 steps: 334 files
- 6 steps: 267 files
- 18 steps: 98 files

**Current modes (mA)**
- 65.0 mA: 1232 steps
- 89.0 mA: 832 steps
- 74.0 mA: 473 steps
- 200.0 mA: 321 steps
- 24.0 mA: 309 steps

#### PNE18

- 696B step records: none
- safety header @0x3D8: mostly empty

**Top categories**
- `unknown`: 47
- `hppc`: 4 (7.0%)
- `storage`: 3 (5.3%)
- `ocv`: 2 (3.5%)
- `cycle_life`: 1 (1.8%)

**Top step counts**
- 68 steps: 26 files
- 35 steps: 11 files
- 15 steps: 9 files
- 10 steps: 4 files
- 9 steps: 3 files

**Current modes (mA)**
- 7.0 mA: 147 steps
- 6.0 mA: 100 steps
- 6.5 mA: 88 steps
- 7.388 mA: 66 steps
- 7.8 mA: 48 steps

#### PNE19

- 696B step records: 267 files
- 0x10004 (696 formation): 267 files
- safety header @0x3D8: mostly empty

**Top categories**
- `unknown`: 209
- `formation`: 22 (8.0%)
- `cycle_life`: 18 (6.5%)
- `rpt`: 12 (4.3%)
- `rate_test`: 7 (2.5%)
- `ocv`: 5 (1.8%)
- `rate_capability`: 3 (1.1%)

**Top step counts**
- 15 steps: 69 files
- 33 steps: 60 files
- 6 steps: 45 files
- 9 steps: 29 files
- 13 steps: 13 files

**Current modes (mA)**
- 30.0 mA: 100 steps
- 13.0 mA: 98 steps
- 26.0 mA: 98 steps
- 7.563 mA: 90 steps
- 12.0 mA: 80 steps

#### PNE20

- 696B step records: 343 files
- 0x10004 (696 formation): 343 files
- safety header @0x3D8: mostly empty

**Top categories**
- `unknown`: 271
- `rate_test`: 36 (10.2%)
- `cycle_life`: 23 (6.5%)
- `hppc`: 12 (3.4%)
- `formation`: 4 (1.1%)
- `rest`: 3 (0.8%)
- `ocv`: 3 (0.8%)
- `rpt`: 2 (0.6%)

**Top step counts**
- 15 steps: 268 files
- 27 steps: 19 files
- 79 steps: 15 files
- 9 steps: 12 files
- 7 steps: 11 files

**Current modes (mA)**
- 15.0 mA: 175 steps
- 13.0 mA: 116 steps
- 43.0 mA: 95 steps
- 16.0 mA: 94 steps
- 53.0 mA: 80 steps

#### PNE22

- 696B step records: none
- safety header populated: maxI=600 mA (1 files)

**Top categories**
- `unknown`: 917
- `rate_test`: 210 (12.7%)
- `formation`: 108 (6.5%)
- `rpt`: 102 (6.1%)
- `cycle_life`: 90 (5.4%)
- `hppc`: 76 (4.6%)
- `storage`: 42 (2.5%)
- `doe`: 25 (1.5%)

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
| PNE01 | `capacheck` | 55.6% | 1.4% | +54.2 |
| PNE01 | `doe` | 36.1% | 1.0% | +35.1 |
| PNE12 | `rpt` | 22.1% | 2.3% | +19.8 |
| PNE12 | `cycle_life` | 23.4% | 7.9% | +15.5 |
| PNE11 | `hppc` | 21.2% | 6.7% | +14.4 |
| PNE09 | `rate_test` | 21.6% | 9.5% | +12.1 |
| PNE11 | `qpeed` | 11.4% | 2.2% | +9.2 |
| PNE15 | `formation` | 15.4% | 7.1% | +8.4 |
| PNE16 | `cycle_life` | 16.1% | 7.9% | +8.2 |
| PNE11 | `rate_test` | 1.7% | 9.5% | -7.8 |
| PNE06 | `rate_test` | 1.8% | 9.5% | -7.7 |
| PNE19 | `rate_test` | 2.5% | 9.5% | -7.0 |
| PNE06 | `formation` | 0.2% | 7.1% | -6.9 |
| PNE07 | `rate_test` | 2.7% | 9.5% | -6.8 |
| PNE06 | `hppc` | 0.4% | 6.7% | -6.4 |
| PNE07 | `cycle_life` | 1.6% | 7.9% | -6.3 |
| PNE12 | `ocv` | 6.8% | 0.5% | +6.3 |
| PNE18 | `cycle_life` | 1.8% | 7.9% | -6.2 |
| PNE05 | `rate_test` | 3.5% | 9.5% | -6.0 |
| PNE07 | `formation` | 1.1% | 7.1% | -6.0 |

### Interpretation notes

- **Unknown filenames** are mostly project/material names; low unknown% (PNE01) means clearer naming, not better binary.
- **Max I (mA)** in a zip reflects stored schedule values (cell size × C-rate), not always equipment rating.
- **696B / 0x10004** is a file-format generation, not tied to one cycler. PNE15/PNE16 are the large 696 corpora; both also carry `0x00010005/720`. PNE19/PNE20 are 696-dominant with no 720 (CYCN-P1107 / CYCSA-P1107). PNE18 (CYCC-1006, 6A) is 612-only.
- **LOOP both%** = nested loop steps with both +48 and +564 populated; higher on complex HPPC/RPT schedules.
