# SCH layout sharing — 500 mA vs 20 A

Date: 2026-09-02  
Status: **verified on controlled-pair fixtures**  
Machine-readable: [`SCH_LAYOUT_TIER_SHARING.json`](SCH_LAYOUT_TIER_SHARING.json)

---

## Short answer

**500 mA (PNE02) and 20 A (baseline) use the same binary step layout and the same field offsets.**  
They differ in **stored values** (mA scale), **CTSPro build**, and **header metadata** — not in a separate offset map per current tier.

---

## Controlled-pair comparison (2026-09-02)

| | 20 A `baseline-charge-current/before.sch` | 500 mA `pne02-charge-current/before.sch` |
|---|-------------------------------------------|------------------------------------------|
| Layout | `0x00010002` / 612 B steps / payload @ 1632 | **same** |
| File size | 4080 B | **same** |
| Steps | CCCV → CC_DCHG → LOOP → END | **same** |
| `compare_sch` compatible | yes | yes |

### Same offsets (Ensol v612)

| Offset | Field | 20 A example | 500 mA example |
|-------:|-------|-------------|---------------|
| 12 | CV voltage mV | 4000 | 4000 |
| 16 | current mA | **10000** (10 A) | **10** |
| 32 | CV cutoff mA | **2000** (2 A) | **2** |
| 340 | record interval s | 60 | 60 |
| 496 | cap_mode | 0 | 1* |

\*PNE02 `baseline2` saves often write `cap496=1`; PNE02 corpus norm is `0`. See `pne02-cv-cutoff/` import notes.

Payload differs in **13 bytes** (mostly `@16` / `@32` values); header differs in **56 bytes** (filename, channel, build string).

---

## Corpus note

Both **PNE02.zip (500 mA)** and **PNE12.zip (20 A)** are dominated by **`0x00010003` / 612 B** with varying step counts and file sizes.  
Current tier does **not** imply a different step-size table.

Layout selection remains **`(nFileVersion, payload_offset, step_size)`** — eventually **`(pne_unit, ctspro_build, nFileVersion)`** per [`LAB_DATA_POLICY.md`](LAB_DATA_POLICY.md).

---

## What is shared vs separated

### Shared (one parser/writer offset map)

- `schema/ensol_v612.py`, `schema/fields.py`
- `compare_sch` word alignment
- Step type codes (CCCV, CC_DCHG, REST, LOOP, END)
- Gate B field names (`fVref` → `current_mA@16`, etc.)

### Separated (evidence policy — do not mix)

| Tag | Why |
|-----|-----|
| `equipment.label` + `rating` | Writer Q·C-rate and scale |
| `ctspro_version` | Build-specific save quirks |
| `channel_profile` | Provenance |
| Controlled-pair directory | `pne02-*` vs `baseline-*` |

20 A baseline pairs remain useful as **structural cross-checks**; **writer-ready promotion** for PNE02 500 mA must come from **`pne02-*`** pairs (reopen verified).

---

## References

- [`example/gate_b_pairs/README.md`](../example/gate_b_pairs/README.md) — imported pairs
- [`planning/EQUIPMENT_CURRENT_RATINGS.json`](EQUIPMENT_CURRENT_RATINGS.json) — official tiers
- [`docs/GATE_B.md`](../docs/GATE_B.md) — evidence promotion ladder
