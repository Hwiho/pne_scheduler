# Golden fixture intake (fill in and return)

Use this form to pick reference `.sch` files for Gate B/D semantic validation.
Fill the **Your input** columns, save this file, and send it back.

**Instructions**

1. Review each candidate (files are in `example/gate_b_export/recommended_sch/`).
2. Mark **Select?** as `yes` / `no` / `maybe`.
3. Fill **PNE unit**, **CTSPro build** (from PPT if known), and **notes**.
4. If you use a different file for a category, write it under **Alternate file**.

---

## Your lab defaults (optional but helpful)

| Item | Your input |
|------|------------|
| Primary PNE unit for 3PJT ASSB work | e.g. PNE 2 / PNE 16 |
| CTSPro / CYCC build on that unit | e.g. CYCC-1004-S01-R004-N01 |
| Q_nom source preference | `inferred` / `explicit_mAh` / `ctspro_ui` / `unsure` |
| Typical Q_nom (mAh) if explicit | |
| Viewer display preference | `current_mA + estimated C-rate` (default) |

---

## Candidate fixtures

### 1 — Formation (696-byte, lab dominant)

| Field | Value |
|-------|-------|
| **File** | `00207966_260422_8stack_SJ900 ╜└╜─_FM ╚─_SOC30 ╝╝╞├.sch` |
| **Path** | `example/fixtures/sch_lab_zip/...` |
| **Format** | 0x00010004 / 696 B, 7 steps |
| **Catalog equipment** | PNE16 (probable) |
| **Select?** | |
| **Your PNE unit** | |
| **CTSPro build** | |
| **Notes** | |
| **Alternate file** | |

### 2 — Cycle life (short, 696 B)

| Field | Value |
|-------|-------|
| **File** | `00207966_250916_Gr-SiC_288kgf_1.0Mpa_0.5C cycle.sch` |
| **Format** | 0x00010004 / 696 B, 25 steps |
| **Catalog equipment** | PNE16 (probable) |
| **Select?** | |
| **Your PNE unit** | |
| **CTSPro build** | |
| **Notes** | |
| **Alternate file** | |

### 3 — Cycle life (short, pressure variant)

| Field | Value |
|-------|-------|
| **File** | `00207966_250916_Gr-SiC_288kgf_1.5Mpa_0.5C cycle.sch` |
| **Format** | 0x00010004 / 696 B, 25 steps |
| **Select?** | |
| **Your PNE unit** | |
| **Notes** | |

### 4 — Cycle life (long loops, 612 B)

| Field | Value |
|-------|-------|
| **File** | `00207966_260803_727도급셀_Set8_45도 Cycle.sch` |
| **Format** | 0x00010003 / 612 B, 73 steps |
| **Select?** | |
| **Your PNE unit** | |
| **Notes** | |

### 5 — RPT (612 B)

| Field | Value |
|-------|-------|
| **File** | `차효현_3350_L.4.36_NP1.08_RPT_SOC50 End_챔버미연동.sch` |
| **Format** | 0x00010002 / 612 B, 19 steps |
| **Select?** | |
| **Your PNE unit** | |
| **Notes** | |

### 6 — RPT (696 B)

| Field | Value |
|-------|-------|
| **File** | `07100766_260511_SJ1300_dry_40um_RPT_500cycle.sch` |
| **Format** | 0x00010004 / 696 B, 41 steps |
| **Select?** | |
| **Your PNE unit** | |
| **Notes** | |

### 7 — Capacheck / QPEED SOC (612 B, unit probe)

| Field | Value |
|-------|-------|
| **File** | `07100766_260713_Set9_QPEED_SOC_setting_BM_SJ1300_6040_C_NCN.sch` |
| **Format** | 0x00010003 / 612 B, 11 steps |
| **Catalog equipment** | PNE02 (probable) |
| **Select?** | |
| **Your PNE unit** | |
| **Notes** | |

### 8 — Formation / capacheck (696 B)

| Field | Value |
|-------|-------|
| **File** | `3.BM_C1%_FM.sch` |
| **Format** | 0x00010004 / 696 B, 9 steps |
| **Select?** | |
| **Your PNE unit** | |
| **Notes** | |

### 9 — QPEED (612 B, L-level fVref)

| Field | Value |
|-------|-------|
| **File** | `07100766_260617_Set2_bimodal-SJ1300-40um_80C_QPEED-2.sch` |
| **Format** | 0x00010003 / 612 B, 167 steps |
| **Catalog equipment** | PNE02 (probable) |
| **Select?** | |
| **Your PNE unit** | |
| **Notes** | |

### 10 — HPPC

| Field | Value |
|-------|-------|
| **File** | `HPPC_Full range.sch` |
| **Format** | 0x00010002 / 612 B, 62 steps |
| **Select?** | |
| **Your PNE unit** | |
| **Notes** | |

### 11–12 — Simple capa probe (696 B)

| # | File | Select? | PNE unit | Notes |
|---|------|---------|----------|-------|
| 11 | `00207966_250611_capa.sch` | | | |
| 12 | `00207966_250611_capa2.sch` | | | |

### Extra — Canonical capacheck (612 B, strongly recommended for B0)

| Field | Value |
|-------|-------|
| **File** | `9)Bimodal_SJ1300_6040_NCN_capacheck.sch` |
| **Path** | `example/fixtures/capacheck_zip/` |
| **Format** | 0x00010003 / 612 B, 15 steps |
| **Why** | Known `fEndV=2500` (mV) on discharge step |
| **Select?** | |
| **Your PNE unit** | |
| **Notes** | |

---

## Controlled pairs (optional — do not run on cell)

Only needed when you want to unlock writer-ready fields. **Not required all at once.**

| Priority | UI change | Done? (`yes`/`no`) | before/after paths | PNE unit |
|----------|-----------|--------------------|--------------------|----------|
| P0 | Rest duration 60→123 s | | | |
| P0 | Charge current 10→17 mA | | | |
| P0 | Discharge current 10→19 mA | | | |
| P0 | End voltage 3000→3123 mV | | | |
| P1 | CV cutoff 2→3 mA | | | |
| P1 | Loop count 2→3 | | | |
| P2 | Capacity termination off→on | | | |
| P2 | DCR window change | | | |

---

## Return checklist

- [ ] At least one fixture per category you care about marked `yes`
- [ ] PNE unit filled for selected files
- [ ] Lab defaults section filled (especially Q_nom preference)
- [ ] Save and send this file back
