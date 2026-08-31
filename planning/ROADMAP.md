# SCH Schedule Builder — Structural Analysis & Roadmap

## Change History

| Date | Summary |
|------|---------|
| 2026-08-31 | Initial draft: documented the structure based on `sch_file_structure_20250211.xlsx`, ASSB_Analyzer_dev, and the Ensol PNE converter; established the roadmap for a visual modular schedule builder |
| 2026-08-31 | Created the `pne_scheduler/` package — IR, C-rate, module stubs, CLI, and example `.schproj` |
| 2026-08-31 | Reassessed repository status — secured the original SCH archive and reprioritized implementation and validation |

---

## 1. Goal

Enable creation of `.sch` binary schedule files for PNE cyclers **without using the native editor**.

- **LabVIEW-style** modular visual interface: drag, place, and connect experiment blocks
- Provide battery experiment types as **template modules** (cycle life, formation, RPT, HPPC, DC-IR, etc.)
- Users enter a **C-rate**, and current (A/mA) is calculated automatically from the **reference capacity**
- Generated `.sch` files must be directly executable on PNE equipment

---

## 2. `.sch` File Structure (Current Understanding)

### 2.1 Sources

| Source | Role | Status |
|--------|------|--------|
| `c:\sch_file_structure_20250211.xlsx` | Official PNE field definitions (by version) | **Canonical specification** |
| `ASSB_Analyzer_dev` → `assb_analyzer/io/pne_converter.py` | Reading, validation, and metadata extraction | Optional external validator; not included in the repository |
| `_vendor/Ensol_PNE_framework/pne_app/io/pne_converter.py` | Partial reader for CycleNum and DCIR reference | Local vendor copy |
| `assb_analyzer/io/cell_c_rate_reference.py` | C-rate ↔ capacity ↔ current (analysis side) | **Logic reusable by the writer** |
| `assb_analyzer/io/classification_bulk_apply.py` | Comparison of identical SCH structure fingerprints | Bulk application of compatible Source values |

> **Current implementation:** The standalone layout detector/viewer parser in `io/sch_parser.py`
> coexists with the ASSB/Ensol adapter in `io/reader.py`. `io/writer.py` is a spike
> that writes a 512-byte placeholder header and must not yet be considered a PNE-compatible writer.

### 2.2 File Versions (Excel Sheets)

| Sheet name | `nFileVersion` | Step field count (approx.) | Notes |
|------------|----------------|----------------------------|-------|
| Type1 `0x00010001` | 65537 | ~90 | Legacy, `szName[64]` |
| Type2 `0x00010001` | 65537 | ~90 | Similar to Type1 |
| `0x00010002` | 65538 | ~90 | |
| `0x00010003` | 65539 | ~105 | ASSB converter **default target** (`step_size=612`) |
| `0x00010004` | 65540 | ~118 | |
| `0x00010007` | 65543 | **132** (includes `stEISSet`) | Latest, adds EIS fields |

**Primary target version:** `0x00010003` + `step_size=612`
→ The ASSB converter already implements its layout policy, DCIR SOC rules, and current-condition mapping for this combination.
**Secondary:** `0x00010004` + `step_size=696`, which accounts for 90% of the corpus.
**Later:** `0x00010007` (when EIS experiments are needed).

### 2.3 Binary Layout (4 Sections)

```
┌─────────────────────────────────────┐
│ PS_FILE_ID_HEADER                   │
│  nFileID, nFileVersion              │
│  szCreateDateTime[64]               │
│  szDescrition[128]                  │
│  szReserved[128]                    │
├─────────────────────────────────────┤
│ FILE_TEST_INFORMATION  (×2 blocks)  │
│  lID, lType                         │
│  szName[], szDescription[]          │
│  szCreator[], szModifiedTime[]      │
├─────────────────────────────────────┤
│ FILE_CELL_CHECK_PARAM               │
│  fMaxVoltage, fMinVoltage           │
│  fMaxCurrent, fOCVLimitVal          │
│  fTrickleCurrent, fDeltaVoltage     │
│  lTrickleTime, nMaxFaultNo, bPreTest│
├─────────────────────────────────────┤
│ FILE_STEP_CONDITION  (×N steps)     │
│  chStepNo, chType, chMode           │
│  fVref, fIref (voltage/current setpoints) │
│  fEndTime, fEndV, fEndI, fEndC ...  │
│  Loop/Goto (nLoopInfo*, nGotoStepID)│
│  Limit (fVLimit*, fILimit*)         │
│  Sampling (fDeltaTime/V/I)          │
│  DCIR (fDCRStartTime, fDCREndTime)  │
│  SOC (fSocRate, fMaxCapacity)       │
│  ... (version-specific extension fields) │
└─────────────────────────────────────┘
```

### 2.4 Step Type / Mode Codes

**chType (Step type)**

| Name | Code | Purpose |
|------|------|---------|
| CHARGE | 0x01 | Charge |
| DISCHARGE | 0x02 | Discharge |
| REST | 0x03 | Rest |
| OCV | 0x04 | OCV measurement |
| IMPEDANCE | 0x05 | Impedance |
| END | 0x06 | End |
| CYCLE | 0x07 | Cycle marker |
| LOOP | 0x08 | Loop |
| PATTERN | 0x09 | Pattern file |
| BALANCE | 0x0A | Balance |

**chMode (Execution mode)** — combinations used by the converter:

| Code | Meaning | Converter mapping |
|------|---------|-------------------|
| 0x0101 | CCCV | `SCH_STEP_TYPE_CCCV` |
| 0x0201 | CC Charge | `SCH_STEP_TYPE_CC_CHARGE` |
| 0x0202 | CC Discharge | `SCH_STEP_TYPE_CC_DISCHARGE` |

**Relationship between SCH and CTS StepNo (important):**

```
CTS StepNo = SCH StepNo + 1
```

Both ASSB `cell_c_rate_reference.py` and `pne_converter.py` validate current conditions based on this mapping. The writer must follow the same rule.

### 2.5 Validated Layout Registry

| `nFileVersion` | Header / payload offset | Step record | Fixture count |
|----------------|-------------------------:|------------:|--------------:|
| `0x00010002` | 1632 | 612 | 6 |
| `0x00010003` | 1760 | 612 | 4 |
| `0x00010004` | 1844 | 696 | 92 |

Across the corpus of 102 files, versions and framing match these three combinations
exactly, with no footer. This is an invariant of the current sample; it does not assume
that unseen producers use the same structure. The writer must select the version-specific
schema through the layout registry and preserve unknown/reserved bytes.

The 696-byte record is not formed simply by appending 84 bytes to the 612-byte record.
Later fields are shifted by 8 bytes in comparable schedules, so a separate field map is required.

### 2.6 Core Step Fields (Required for Experiment Module Design)

| Field | Meaning | Module input |
|-------|---------|--------------|
| `fVref` | Target voltage (V) | Charge upper limit / discharge lower limit |
| `fIref` | Target current (mA, equipment raw value) | Calculated as **C-rate × reference capacity** |
| `fEndTime` | End time (sec) | Rest, interval between HPPC pulses |
| `fEndV` | End voltage | CC-CV transition, discharge termination |
| `fEndI` | End current (CV cutoff) | Specified as a C-rate such as C/20 or C/50 |
| `fEndC` | End capacity (mAh) | SOC setting, partial cycle |
| `fEndCVTime` | CV phase duration | |
| `nLoopInfoGoto/Cycle` | Loop target/count | Cycle-life experiments, RPT period |
| `nGotoStepID` | SOC reference step | DC-IR SOC setting |
| `fDCRStartTime/EndTime` | DCIR measurement window | DC-IR module |
| `fDeltaTime/V/I` | Data sampling | Default profile |
| `fSocRate` | SOC ratio | SOC setting step |
| `fMaxCapacity` | Reference capacity (mAh) | Basis for C-rate calculation |

---

## 3. Proposed Architecture

### 3.1 3-Layer Structure

```
┌──────────────────────────────────────────────────────────┐
│  UI Layer — Visual Flow Editor (LabVIEW style)           │
│  Node graph: drag-drop modules, wire connections         │
└────────────────────────┬─────────────────────────────────┘
                         │ project JSON (.schproj)
┌────────────────────────▼─────────────────────────────────┐
│  Domain Layer — Experiment Modules + Schedule IR         │
│  Formation / CycleLife / RPT / HPPC / DCIR / Rest ...    │
│  C-rate Engine, Loop expander, Safety validator          │
└────────────────────────┬─────────────────────────────────┘
                         │ compiled step list
┌────────────────────────▼─────────────────────────────────┐
│  Binary Layer — SCH Writer + Round-trip Validator        │
│  struct pack, version-aware offsets, PNE float32 rules   │
└──────────────────────────────────────────────────────────┘
```

### 3.2 Intermediate Representation (Schedule IR)

Place a **version-independent IR** between the UI and binary layers.

```python
@dataclass
class ScheduleProject:
    name: str
    cell_profile: CellProfile          # reference capacity, Vmax/Vmin
    sch_version: int                   # 0x00010003
    modules: list[ExperimentModule]    # graph nodes
    connections: list[ModuleConnection]  # execution order

@dataclass
class CellProfile:
    nominal_capacity_mAh: float
    v_max: float
    v_min: float
    # optional: formation capacity, DCIR pulse C-rate table

@dataclass
class StepIntent:
    # User-friendly intent — C-rate based
    step_type: Literal["charge","discharge","rest","ocv","cycle","loop","end"]
    mode: Literal["CCCV","CC","CV"]
    c_rate: float | None              # used to derive fIref
    cv_cutoff_c_rate: float | None    # used to derive fEndI
    end_voltage_v: float | None
    end_time_s: float | None
    end_capacity_fraction: float | None  # SOC 50% → fEndC
    ...
```

Modules generate `StepIntent[]`, and the compiler flattens it into `FILE_STEP_CONDITION` byte records.

### 3.3 C-rate Engine (Addresses Requirement 3)

```
I_mA = C_rate × Q_nominal_mAh
```

| Input | Example | Output |
|-------|---------|--------|
| 1C charge, 80 mAh cell | C=1.0 | I = 80 mA |
| C/3 discharge | C=0.333 | I = 26.7 mA |
| CV cutoff C/20 | C=0.05 | fEndI = 4 mA |

**UI rules:**
- The user-facing unit is **always C-rate** (direct current input is available only as an advanced option)
- Set `nominal_capacity_mAh` once in the Cell Profile → propagate it to every module
- Provide the allowed C-rate table (`_ALLOWED_CURRENT_RATES`) from ASSB `cell_c_rate_reference.py` as presets
- When writing output, apply PNE raw units (mA) and float32 packing (`_f32repr` rules)

### 3.4 Visual UI (Addresses Requirement 1)

**Screen layout:**

```
┌─────────────┬────────────────────────────────┬──────────────┐
│ Module      │  Canvas (node graph)           │ Properties   │
│ Palette     │                                │ Panel        │
│             │  [Formation]──▶[CycleLife]     │              │
│ · Formation │         │                      │ C-rate: 1C   │
│ · CycleLife │         └──▶[RPT every 50]     │ Vmax: 4.2 V  │
│ · RPT       │                                │ Loop: 500    │
│ · HPPC      │                                │              │
│ · DC-IR     │                                │              │
│ · Rest      │                                │              │
│ · Loop      │                                │              │
└─────────────┴────────────────────────────────┴──────────────┘
│ Timeline preview  │  Step table  │  Export .sch  │  Validate │
└───────────────────────────────────────────────────────────────┘
```

**Technology stack candidates:**

| Option | Advantages | Disadvantages |
|--------|------------|---------------|
| **A. Tkinter + custom canvas** | Same stack as pne_studio2, simple deployment | Significant effort to implement the node graph |
| **B. PySide6 + NodeEditor** | Closer to the LabVIEW UX | Adds dependencies |
| **C. Web (React Flow) + Electron** | Best graph UX | Separate app, complex deployment |

**Recommendation:** Start the Phase 3 visual UI as a separate app in `pne_scheduler/ui/`, then integrate it with pne_studio2 later.

---

## 4. Experiment Module Catalog (Requirement 2)

### 4.1 Phase 1 — Essential Modules

| Module | Step pattern | Main parameters (C-rate based) |
|--------|--------------|--------------------------------|
| **Formation** | Charge CCCV → Rest → Discharge CC → Rest (×N cycles) | charge C, discharge C, Vmax/Vmin, cycle count |
| **Cycle Life** | [Charge CCCV → Rest → Discharge CC → Rest] × loop | C_charge, C_discharge, end condition (V or C), loop count |
| **RPT** | Reference discharge (C/3) → Rest → pseudo-OCV steps | C_ref, SOC checkpoints, anchor cycle interval |
| **DC-IR** | SOC setting discharge → Rest → pulse discharge (short CC) → Rest | SOC %, pulse C, pulse duration, DCR window |
| **HPPC** | SOC staircase + pulse train (charge/discharge pulses) | SOC list, pulse C, pulse/rest duration |
| **Rest / OCV** | Rest or OCV hold | duration, ΔV sampling |

### 4.2 Phase 2 — Extension Modules

| Module | Description |
|--------|-------------|
| **Calendar Aging** | Storage at SOC X%, periodic RPT insert |
| **Rate Capability** | Multi C-rate discharge ladder |
| **GITT** | Intermittent current + rest OCV |
| **Pattern Drive** | PATTERN step + `.pat` file connection |
| **EIS** | `stEISSet` (0x00010007 only) |
| **Self-discharge** | Long rest + periodic OCV |
| **Pre-test / Cell Check** | Automatic generation of `FILE_CELL_CHECK_PARAM` |

### 4.3 Common Module Interface

```python
class ExperimentModule(Protocol):
    module_type: str
    def validate(self, cell: CellProfile) -> list[str]: ...
    def expand(self, cell: CellProfile) -> list[StepIntent]: ...
    def estimated_duration_h(self, cell: CellProfile) -> float: ...
    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict) -> Self: ...
```

---

## 5. Additional Proposed Features (Requirement 4)

### 5.1 Safety and Validation

| Feature | Description |
|---------|-------------|
| **Safety envelope** | Automatically validate each step against the Cell Profile V/I limits |
| **Round-trip validator** | Writer output → reparse with ASSB `parse_sch_cycle_map_bytes` → compare with the original IR |
| **PNE simulator hook** | If possible, dry-run in the PNE PC simulator (manual verification checklist) |
| **StepNo continuity check** | Consecutive 1..N numbering, presence of an END step, and LOOP goto validity |

### 5.2 Productivity

| Feature | Description |
|---------|-------------|
| **Template library** | Cell Profile integration with ASSB presets (`06_assb_design_stack`) |
| **Import existing .sch** | Reverse-parse a measured sch → IR → graph editing (reader extension) |
| **Clone & parameter sweep** | Sweep only C-rate / cycle count over the same structure → batch export |
| **Schedule fingerprint** | Compatible with ASSB `FrozenScheduleStructureFingerprint` — search for Sources with the same structure |
| **Human-readable export** | Step table in Excel/PDF (for attachment to process documents) |
| **Estimated duration / throughput** | Summary of total estimated time, energy, and cycle count |

### 5.3 Analysis Integration (pne_studio2 / ASSB Ecosystem)

| Feature | Description |
|---------|-------------|
| **ASSB classification hint** | Automatically tag the expected test type (formation/cycle/dcir) from the module combination |
| **C-rate display sync** | Use the same reference capacity as the ASSB Cell Manager `cell_c_rate_reference` schema |
| **Sampling preset** | Default Δt/ΔV/ΔQ values (resolve the UNKNOWN item in cyclediag IMPROVEMENT_ROADMAP #16) |
| **Post-build checklist** | Guidance for `.cts` naming, `.ini` current range, and channel folder structure |

### 5.4 Advanced

| Feature | Description |
|---------|-------------|
| **Conditional branching** | SOC/voltage conditional goto (`nGotoStepID` scenario) |
| **Multi-version export** | Same IR → selectable 0x00010003 / 0x00010007 output |
| **Chiller / thermal profile** | fTref, chiller fields (0x00010007) |
| **Version control** | `.schproj` git-friendly JSON + diff view |

---

## 6. Implementation Roadmap

### 6.1 Repository Assessment Results as of 2026-08-31

| Area | Status | Evidence / assessment |
|------|--------|-----------------------|
| Original fixtures | **Secured** | 8-file and 93-file SCH ZIPs in `example/archives/`, and 1 HPPC file in `example/fixtures/hppc/` |
| File reading/viewer | **Partially complete** | Implemented registry-first 612/696-byte layout detection; all 102 fixtures have automated structural golden regression coverage |
| Equipment provenance | **Partially classified** | Current fixture-only catalog records user-confirmed, user-attributed, and unknown equipment sources without creating filename rules for future files |
| Classification/stack/C-rate inference | **Partially complete** | Unit tests exist and analysis reports have been generated |
| `.schproj` IR/JSON | **Partially complete** | Serialization and linear DAG sorting implemented; no schema validation/version migration |
| Experiment modules | **prototype** | expand implemented for Formation, Cycle Life, RPT, DC-IR, HPPC, capacheck, QPEED, etc. |
| Binary compiler | **spike** | Packs only some fields; does not write core fields such as mode, loop, DCR, and sampling |
| SCH writer | **Incomplete/do not use** | Uses a 512-byte placeholder header; actual file sections are not implemented |
| Round-trip validator | **Incomplete** | Validation is impossible without an external parser, and currently only the step count is compared |
| GUI | **Partially complete** | Viewer/resume/bulk editor exist; flow editor is a placeholder |
| Test execution environment | **Restored** | Editable install and wheel import succeed after explicitly registering the root-layout package |

### 6.2 Gate A — Restore the Development Baseline (Highest Priority)

| # | Task | Completion criteria |
|---|------|---------------------|
| A1 | Fix `pyproject.toml` package discovery/source layout | `import pne_scheduler` succeeds after an editable install in a clean environment |
| A2 | Establish the test command and CI baseline | All `python -m pytest tests/ -q` tests pass, and the actual pass count matches the README |
| A3 | Add fixture inventory tests | Automatically verify the SCH counts in the ZIPs (8, 93) and the presence of the HPPC fixture |

Until this gate is complete, neither the existing “65+ passed” statement nor module
completion statuses may be used as release evidence.

**Progress record**
- A1 complete: verified package/subpackage imports after an editable install and from a wheel installed into a separate target
- A3 complete: automatically verified that the two ZIPs match the 8-file and 93-file extracted directory listings, for a total of 102 files including HPPC
- A2 in progress: confirmed `75 passed` locally; establishing the CI baseline and updating the README count remain

### 6.3 Gate B — Establish the Binary Schema as the Single Source of Truth

| # | Task | Completion criteria |
|---|------|---------------------|
| B1 | Create header/step field tables for the 612/696 layouts | Manage offset, dtype, size, and version source in one place in the code |
| B2 | Resolve parser/schema/compiler offset discrepancies | In particular, compare `fEndV`, `fEndI`, and `fEndC` against originals, Excel, and ASSB results |
| B3 | Read regression over all 102 original files | Detect version, payload offset, step size/count for all 8 + 93 + HPPC files |
| B4 | Semantic golden tests for representative fixtures | Step types and core values for Formation/Cycle/RPT/QPEED/HPPC match golden data |

The end-condition offsets in `schema/v0x00010003_612.py`, `io/sch_parser.py`, and
`engine/compiler.py` have been unified based on analysis of the original corpus. Analysis
values generated before the correction are treated only as reference material; the regenerated
manifest and golden tests are authoritative.

**Progress record**
- B3 complete: `example/fixtures/catalog.json` locks SHA-256, version, payload offset,
  step size, step count, and equipment provenance for all 102 checked-in fixtures
- Layout detection now uses the v2/v3/v4 registry first and retains structural scanning
  only as a guarded fallback for unknown producers

### 6.4 Gate C — Actually Compatible SCH Writer

| # | Task | Completion criteria |
|---|------|---------------------|
| C1 | Full header/test-info/cell-check writer for `0x00010003` | Generate the defined payload offset and size without placeholders |
| C2 | Complete the step compiler | Write mode, end conditions, loop/goto, sampling, SOC, and DCR fields |
| C3 | Make the internal round-trip validator independent | Semantic write → read comparison without an external ASSB installation |
| C4 | Cross-validate against the external parser | Internal parser results match ASSB results when available |
| C5 | PNE PC/equipment smoke test | Successfully load a Rest → CC Charge → END file and record the checklist |
| C6 | Extend writer for `0x00010004/696` | Semantically compare the dominant lab archive format (89/93) with representative fixtures |

The 612-byte implementation is the first vertical slice for establishing the schema. Support
for 696-byte records is essential for actual lab parity, so the writer must not be marked fully
complete until C6 is finished. Until a successful PNE load, do not document CLI `build`
output as “equipment-executable.”

### 6.5 Gate D — Experiment Module Fixture Fidelity

| Priority | Module | Validation fixture / criteria |
|----------|--------|-------------------------------|
| P0 | Formation, Cycle Life, Rest | Compare step topology, current, voltage, and loop semantics with representative originals |
| P0 | RPT, DC-IR | Semantic diff of SOC reference, DCR window, and goto relationships |
| P1 | HPPC | Compare the SOC staircase and bidirectional pulses in `HPPC_Full range.sch` |
| P1 | capacheck, QPEED, in-situ cycle | Compare golden topology for the 8-file bimodal archive |

Each module must pass `validate`, `expand`, binary compile, and round-trip in a single
integration test before it is marked complete.

### 6.6 Gate E — Editing UX and Advanced Features

1. Fixture-based regression tests for the existing viewer/resume/bulk editor
2. Flow editor module palette, DAG canvas, property panel, and live preview
3. Validation feedback and blocking of unsafe conditions before export
4. `.sch` → IR import, 0x00010007/EIS, and fingerprint integration
5. pne_studio integration

Gate E proceeds after writer compatibility is secured in Gate C.

---

## 7. Proposed Package Layout

```
pne_scheduler/                   # main package (repo root)
├── planning/ROADMAP.md          # this document
├── example/example.schproj
├── schema/
│   ├── v0x00010003_612.py
│   └── enums.py
├── ir/
│   ├── cell_profile.py
│   ├── project.py
│   └── step_intent.py
├── modules/
│   ├── formation.py
│   ├── cycle_life.py
│   ├── rpt.py
│   ├── hppc.py
│   ├── dcir.py
│   └── rest.py
├── engine/
│   ├── c_rate.py
│   └── compiler.py
├── io/
│   ├── reader.py
│   └── writer.py
├── validate/
│   └── roundtrip.py
├── stack/                       # FP, L-level, xMyU, capacity inference
├── protocol/                    # protocol defaults and inference
├── classify/                    # filename classification
├── edit/                        # bulk module editing
├── resume/                      # resume interrupted experiments
├── ui/
│   ├── schedule_viewer.py
│   ├── project_editor.py
│   ├── resume_wizard.py
│   └── flow_editor.py           # placeholder
├── tools/                       # batch fixture analysis
├── docs/
└── tests/

run_pne_scheduler.py             # root launcher
```

**Validation dependency principle:** Basic read/write/round-trip functionality must work
with the repository alone. Use `assb_analyzer.io.pne_converter.parse_sch_cycle_map_bytes`
as an optional cross-validator; the absence of the external package must not cause basic
tests to be skipped.

---

## 8. Risks & Unresolved Items

| Item | Status | Response |
|------|--------|----------|
| Package import fails after editable install | **Resolved** | Regression validation of editable install and clean-target wheel import |
| Parser/schema/compiler end-condition offset discrepancy | **Internally consistent** | `fEndV=28`, `fEndI=32`, `fEndC=36`; comparison of originals with nonzero `fEndC` against the external parser continues in B2 |
| Misunderstanding of LOOP goto/count offsets | **Resolved** | Corpus confirmed `+48/+52`; corrected the previous `+84/+88` and added 612/696 golden tests |
| Mismatch between lab format and writer target | **Confirmed** | 89 of 93 files use `0x10004/696`; proceed with Gate C6 immediately after 612 validation |
| Automatic selection of 612 vs 696 byte step size | Partially understood | Validate version→size mapping against the 102 secured measured sch files |
| PNE raw current unit (mA vs A) | Depends on ini range | Compare Cell range profile with ASSB `unit_scale` |
| Internal structure of `FILE_GRADE`, `STRUCT_EIS_SET` | Only names are present in Excel | Defer 0x00010007 to Phase 4 |
| Recommended Δt/ΔV/ΔQ values | UNKNOWN in cyclediag | Reverse-extract from internal standard sch samples |
| Writer validation on physical equipment | Not started | PNE PC load test is mandatory in Gate C5 |
| External ASSB parser availability | Dependency outside the repository | Make the internal parser the default source of truth and optionally cross-validate |
| Drift between fixture names and test expectations | **Confirmed** | Do not hide with skips; stabilize with manifest-based fixture lookup |

---

## 9. Immediate Next Actions

1. ✅ **Restore packaging** — completed editable install and clean-target wheel import validation
2. ✅ **Add automatic fixture checks** — established 101 archive/extracted files + 1 HPPC file as test inputs
3. ✅ **Resolve internal offset conflict** — unified parser/schema/compiler locations for `fEndV/fEndI/fEndC`
4. **Externally confirm offsets** — validate semantics using an original with nonzero `fEndC` or the official field table
5. ✅ **Full reader regression test** — locked layout, step count, hash, and EOF geometry for all 102 files
6. **Implement writer header** — complete the schema/writer vertical slice for `0x00010003/612`
7. **696-byte lab parity** — extend the writer for `0x00010004/696`, which accounts for 89/93
8. **End-to-end validation of representative modules** — Formation → Cycle Life → RPT/DC-IR order
9. **PNE load test** — promote the writer to usable only after a successful result is recorded

---

## 10. Reference Code Locations

| Path | Content |
|------|---------|
| `c:\sch_file_structure_20250211.xlsx` | Official PNE field specification |
| `ASSB_Analyzer_dev/assb_analyzer/io/pne_converter.py` | SCH parser (read), current conditions, DCIR SOC rules |
| `ASSB_Analyzer_dev/assb_analyzer/io/cell_c_rate_reference.py` | C-rate ↔ capacity |
| `ASSB_Analyzer_dev/assb_analyzer/io/classification_bulk_apply.py` | SCH structure fingerprint |
| `_vendor/Ensol_PNE_framework/pne_app/io/pne_converter.py` | Local partial reader |
| `pne_studio2/assets/presets/06_assb_design_stack.json` | Cell design preset (reference for capacity estimation) |
