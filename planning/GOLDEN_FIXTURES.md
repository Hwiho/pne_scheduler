# Golden fixtures (Gate B/D)

Machine-readable lock: [`GOLDEN_FIXTURES_LOCKED.json`](GOLDEN_FIXTURES_LOCKED.json)  
Intake form (fillable): [`../example/gate_b_export/GOLDEN_FIXTURE_INTAKE.md`](../example/gate_b_export/GOLDEN_FIXTURE_INTAKE.md)

Source intake completed: 2026-09-01

---

## Selected for golden tests (7 files)

| ID | Category | Format | PNE unit |
|----|----------|--------|----------|
| golden-formation-696 | formation | 696 B | **PNE16** |
| golden-cycle-696 | cycle_life | 696 B | **PNE16** |
| golden-cycle-612-long | cycle_life | 612 B | **PNE02** |
| golden-rpt-612 | rpt | 612 B | **PNE02** |
| golden-qpeed-612 | qpeed (full) | 612 B | **PNE02** |
| golden-hppc-612 | hppc | 612 B | **PNE02** |
| golden-capacheck-612-b0 | capacheck | 612 B | **PNE02** |

**Equipment split**

- **PNE02 (500 mA)** — cycle 612, RPT, QPEED, HPPC, capacheck  
- **PNE16 (6 A)** — formation 696, cycle 696  

---

## Not selected

| File | Reason |
|------|--------|
| `…1.0Mpa_0.5C cycle.sch` | User: no |
| `…RPT_500cycle.sch` | User: no (PNE30) |
| `…QPEED_SOC_setting…sch` | Deferred — `QpeedVariant.SOC_SETTING` |
| `3.BM_C1%_FM.sch` | FM → formation, not capacheck |

---

## Domain rules (user-confirmed)

1. **FM** in filename (without capacheck) → **formation**  
2. Formation ≠ capacheck  
3. Derating = capacheck family (`ProtocolVariant.DERATING`)  
4. QPEED SOC setting — distinct QPEED sub-type  

---

## Open items

| Item | Status |
|------|--------|
| Primary 3PJT PNE unit | not filled |
| CTSPro build per unit | partial — see [`EQUIPMENT_CTS_FROM_PPT.md`](EQUIPMENT_CTS_FROM_PPT.md) |
| Q_nom source | writer uses explicit 1C current (mA) per user decision |

---

## Candidate list (pre-intake reference)

See locked JSON for paths. Original 12-candidate table lived in `example/gate_b_export/` export pack; superseded by selections above.
