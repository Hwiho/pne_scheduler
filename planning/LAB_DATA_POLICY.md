# Lab data policy — PNE cycler analysis

Date: 2026-09-02  
Status: **user-confirmed rules**

Machine-readable registry: [`EQUIPMENT_REGISTRY.json`](EQUIPMENT_REGISTRY.json)

---

## Rule 1 — Unit-numbered zip only for cycler analysis

**Only zip archives whose filename is the PNE unit id** (e.g. `PNE02.zip`, `PNE22.zip`) may be used for:

- per-cycler SCH binary structure analysis
- per-cycler equipment rating / CTS metadata
- corpus statistics attributed to a cycler

**Do not use** for cycler-specific conclusions:

- `capacheck_zip/`, `sch_lab_zip/`, `hppc/` fixture folders (golden fixtures only — not corpus)
- Ensol zip, Excel specs, mixed project archives without `PNE##.zip` name
- Individual `.sch` paths unless the parent archive is a valid unit zip

Golden fixtures remain valid for **semantic regression** on locked paths; they do not replace unit zip evidence for layout per equipment.

Enforced in: `schema/lab_corpus.py`, corpus analysis tools.

---

## Rule 2 — SCH binary layout may differ per cycler

Observed `.sch` framing (header size, step size, field offsets) can vary by **PNE unit**, not only by `nFileVersion`.

Therefore:

- `schema/layouts.py` keeps a **global default** per `0x00010002` / `0x00010003` / `0x00010004`
- `EQUIPMENT_REGISTRY.json` records **per-unit observed layouts** from unit zips
- Writer/compiler must eventually select layout by **`(pne_unit, ctspro_build, nFileVersion)`**, not version alone

Gate B/C work should tag every controlled pair and golden with `pne_unit`.

---

## Rule 3 — Record CTSPro build per cycler (from PPT)

CTSPro software build (PPT slide / lab metadata) can change binary layout even on the same `nFileVersion`.

Each PNE unit entry must record:

| Field | Example |
|-------|---------|
| `ctspro_build` | `CYCC-1004-S01-R004-N01` |
| `ctspro_build_source` | `ppt` / `lab_sticker` / `unknown` |
| `ctspro_build_date` | optional |

Writer smoke tests and layout maps are valid only for the **(unit, ctspro_build)** pair they were verified on.

---

## Current unit zip corpus (analysis allowed)

| Zip | Unit | In rating guideline |
|-----|------|---------------------|
| PNE01.zip | PNE01 | yes (500 mA) |
| PNE02.zip | PNE02 | yes (500 mA) |
| PNE03.zip | PNE03 | yes (6 A) |
| PNE04.zip | PNE04 | **pending** |
| PNE05.zip | PNE05 | **pending** |
| PNE22.zip | PNE22 | yes (100 mA) |

---

## Open intake (fill from PPT / lab)

| Unit | CTSPro build | Confirmed layout pairs |
|------|--------------|------------------------|
| PNE01 | ? | 0x10003/612 (observed) |
| PNE02 | CYCC-1004-S01-R004-N01 | 0x10003/612 (golden) |
| PNE03 | ? | 0x10003/612, 0x10004/696 (observed) |
| PNE04 | ? | 0x10003/612 (observed) |
| PNE05 | ? | 0x10003/612 (observed) |
| PNE16 | CYCC-1004-S01-R004-N01 | 0x10004/696 (golden, no unit zip yet) |
| PNE22 | ? | 0x10003/612 (observed) |
