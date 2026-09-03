# SCH Schedule Builder — Structural Analysis & Roadmap

## Change History

| Date | Summary |
|------|---------|
| 2026-08-31 | Initial draft: documented the structure based on `sch_file_structure_20250211.xlsx`, ASSB_Analyzer_dev, and the Ensol PNE converter; established the roadmap for a visual modular schedule builder |
| 2026-08-31 | Created the `pne_scheduler/` package — IR, C-rate, module stubs, CLI, and example `.schproj` |
| 2026-08-31 | Reassessed repository status — secured the original SCH archive and reprioritized implementation and validation |
| 2026-09-01 | Ensol sch_maker zip ingested; 612-byte mV/mA offset map adopted (`schema/ensol_v612.py`) |
| 2026-09-02 | Lab data policy: only `PNE##.zip` for cycler analysis; per-unit SCH layout + CTS build registry (`LAB_DATA_POLICY.md`, `EQUIPMENT_REGISTRY.json`) |
| 2026-09-02 | Project directory map + code rules: [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md) |
| 2026-09-02 | MD docs consolidated: [`planning/README.md`](README.md), [`LAB_CORPUS_REPORT.md`](LAB_CORPUS_REPORT.md), [`docs/README.md`](../docs/README.md), [`docs/GATE_B.md`](../docs/GATE_B.md) |

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
| `schema/reference/sch_file_structure_20250211.xlsx` | Expected official PNE field definitions (by version) | Canonical reference; JSON export in same folder |
| `ASSB_Analyzer_dev` → `assb_analyzer/io/pne_converter.py` | Reading, validation, and metadata extraction | Optional external validator; not included in the repository |
| `_vendor/Ensol_PNE_framework/pne_app/io/pne_converter.py` | Partial reader for CycleNum and DCIR reference | Local vendor copy |
| `vendor/ensol_sch_maker_ref/` (`Ensol_sch_maker` zip) | **Working 612-byte writer/reader**, mV/mA offsets, rescaler, block expanders | Adopted → `schema/ensol_v612.py`, parser/compiler fixes; see `planning/ENSOL_SCH_MAKER_ADOPTION.md` |
| `assb_analyzer/io/cell_c_rate_reference.py` | C-rate ↔ capacity ↔ current (analysis side) | **Logic reusable by the writer** |
| `assb_analyzer/io/classification_bulk_apply.py` | Comparison of identical SCH structure fingerprints | Bulk application of compatible Source values |

> **Current implementation:** The standalone layout detector/viewer parser in `io/sch_parser.py`
> coexists with the ASSB/Ensol adapter in `io/reader.py`. `io/writer.py` is a spike
> that builds a full `0x00010003`/1760 header but must not yet be considered a
> PNE-compatible writer until Gate C2–C5 complete.
> The CLI blocks `build` by default unless the developer explicitly passes
> `--allow-experimental-output`; even acknowledged output is for offline analysis only.

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

These names describe the intended module contract, not a claim that every binary offset and
unit is verified. `schema/fields.py` is authoritative for current evidence confidence.

| Field | Intended meaning | Current evidence | Module input |
|-------|------------------|------------------|--------------|
| `fVref` | Target voltage | Semantic unverified | Charge upper limit / discharge lower limit |
| `fIref` | Target current | Semantic unverified; equipment scaling unresolved | **C-rate × reference capacity** |
| `fEndTime` | End time | Semantic unverified | Rest or pulse interval |
| `fEndV` | End voltage | Corpus inferred | CC-CV transition or discharge termination |
| `fEndI` | End current | Corpus inferred | CV cutoff C-rate |
| `fEndC` | End capacity | Semantic unverified; no nonzero fixture | SOC setting or partial cycle |
| `fEndCVTime` | CV phase duration | Offset unresolved | CV duration |
| `loop_target/count` | Loop target and count | Corpus inferred at `+48/+52` | Cycle-life and RPT loops |
| `nGotoStepID` | SOC reference step | Offset/semantics unresolved | DC-IR SOC setting |
| `fDCRStartTime/EndTime` | DCIR measurement window | Offset/semantics unresolved | DC-IR module |
| `fDeltaTime/V/I` | Data sampling | Offset/semantics unresolved | Sampling profile |
| `fSocRate` | SOC ratio | Legacy offset only | SOC setting step |
| `fMaxCapacity` | Reference capacity | Legacy offset only | C-rate calculation basis |

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

### 5.5 Recommended Feature Order

The next product work should favor verifiable, template-preserving operations before
from-scratch binary generation.

| Priority | Feature | Why it belongs here | Dependency |
|----------|---------|---------------------|------------|
| P0 | **Safe export gate and build manifest** | Prevents experimental output from being mistaken for equipment-ready SCH; records source hash, schema evidence, target profile, and validation results | Available now |
| P0 | **Template-preserving SCH patcher** | Reuses a CTSPro-authored header and unknown bytes while changing only allowlisted, evidence-qualified fields | Controlled field pairs and reopen checks |
| P0 | **Semantic SCH diff** | Shows step-level intent changes instead of only raw bytes and can assert that the expected field alone changed | Reader field coverage |
| P0 | **Target equipment profile** | Makes PNE02/16/21/22, current range, CTSPro version, units, and supported layout explicit instead of inferring them from filenames | User/INI metadata |
| P1 | **Schedule linter and execution preview** | Detects invalid loops, missing END, unsafe V/I limits, unreachable steps, and implausible duration before export | IR and parser |
| P1 | **Read-only SCH → IR import** | Enables review, cloning, and diffing of existing schedules before editable round-trip is trusted | Semantic reader coverage |
| P1 | **Versioned protocol templates** | Makes Formation/Cycle/RPT/HPPC defaults reviewable and traceable by equipment profile | Golden module fixtures |
| P2 | **Parameter sweep and batch export** | Produces controlled variants after one template is verified | Safe patcher and manifest |
| P2 | **Approval/audit bundle** | Packages SCH hash, human-readable step table, diff report, screenshots, and operator approval | Stable export workflow |
| P3 | **Visual flow editor** | Improves composition UX after the underlying semantic and safety contracts are reliable | Gates C, D, and release gate |

Features that should not be prioritized yet are direct hardware control, automatic upload to
cycler PCs, and broad 0x00010007/EIS generation. Their failure modes are harder to inspect
than offline file generation and they depend on unresolved schemas.

---

## 6. Implementation Roadmap

Work proceeds **Gate A → B → C → D → E → F** in order. Do not start a later Gate until the
current Gate’s exit criteria are met (or an explicit waiver is recorded in §11).

```
Gate A  개발 기반          ✅ complete (local)
  ↓
Gate B  바이너리 스키마    ✅ complete
  ↓
Gate C  호환 SCH writer    🔄 lab-blocked on C5  ← current focus
  ↓
Gate D  모듈 픽스처 검증   ⏳ deferred
  ↓
Gate E  편집 UX / 고급 기능
  ↓
Gate F  운영 릴리스 / 추적성
```

### 6.0 Gate maintenance rules

When new problems appear during implementation:

1. **Log first** — add a row to §11 *Discovered issues backlog* with date, gate, severity, and owner.
2. **Assign a gate** — blocking schema/writer issues stay in B or C; module fidelity → D; UX → E; release process → F.
3. **Update the active gate** — move tasks into that gate’s task table and mark status (`open` / `in progress` / `done`).
4. **Record resolution** — close the §11 row when exit criteria or a documented waiver is met.
5. **Do not skip gates** — if Gate C is blocked by a B item, fix B first; do not mark C complete with a hidden dependency.

Status labels used below: `✅ done` · `🔄 in progress` · `⏳ not started` · `⚠️ blocked`

---

### 6.1 Repository Assessment Results as of 2026-09-03

| Area | Status | Evidence / assessment |
|------|--------|-----------------------|
| Original fixtures | **Secured** | 102-file catalog + archives; Gate B controlled pairs under `example/gate_b_pairs/` |
| File reading/viewer | **Usable** | Registry-first 612/696 layout detection; structural goldens; Ensol-aligned display fields |
| Equipment provenance | **Partially classified** | Explicit intake metadata required; filename inference prohibited |
| Classification/stack/C-rate inference | **Partially complete** | Unit tests + analysis reports; viewer-only Q_nom inference |
| `.schproj` IR/JSON | **Partially complete** | Serialization and linear DAG sorting; no schema version migration yet |
| Experiment modules | **prototype** | `expand` for Formation, Cycle Life, RPT, DC-IR, HPPC, capacheck, QPEED, smoke |
| Binary compiler | **C2 done (with DCR gap)** | Mode, end, loop/goto, sampling, SOC packed; DCR remains IR-only |
| SCH writer | **Software-complete pending C5** | Full `0x10003` header; `0x10004` framing; still experimental until equipment smoke |
| Round-trip validator | **C3 done** | `validate/roundtrip.py` semantic field compare on Ensol offsets |
| ASSB cross-check | **C4 thin-but-green** | Layout/step parity + limited field overlap (`fEndC`); not full semantic ASSB parity |
| GUI | **Partially complete** | Viewer/resume/flow editor exist; export still gated |
| Test execution environment | **Restored** | Local `pytest` green (~250+); hosted CI still Gate F |

---

### 6.2 Gate A — Restore the Development Baseline

| | |
|---|---|
| **Status** | ✅ **Complete** (local) |
| **Depends on** | — |
| **Exit criteria** | Clean editable install; pytest green; 102-fixture inventory locked |
| **Next gate** | Gate B |

| # | Task | Status | Completion criteria |
|---|------|--------|---------------------|
| A1 | Fix `pyproject.toml` package discovery/source layout | ✅ | `import pne_scheduler` succeeds after editable install in a clean environment |
| A2 | Establish the test command and CI baseline | ✅ local | `python -m pytest tests/ -q` passes; README badge matches count |
| A3 | Add fixture inventory tests | ✅ | ZIP counts (8, 93) + HPPC presence verified automatically |

**Notes:** Hosted CI is deferred to **F6**; local pass count is not equipment-compatibility evidence.

**Progress record**
- A1: package/subpackage imports verified from editable install and clean-target wheel
- A3: 8 + 93 + 1 HPPC = 102 fixtures locked
- A2: 112 tests pass locally; README still shows 100 — update badge when convenient

---

### 6.3 Gate B — Establish the Binary Schema as the Single Source of Truth

| | |
|---|---|
| **Status** | ✅ **Passed** (`gate_b_passed=true`, 2026-09-03) |
| **Depends on** | Gate A |
| **Exit criteria** | Raw-unit contract resolved; parser/schema/compiler agree; semantic goldens for representative fixtures; intake metadata gates evidence promotion |
| **Next gate** | Gate C |

| # | Task | Status | Completion criteria |
|---|------|--------|---------------------|
| B0 | Define PNE raw-unit/profile mapping | ✅ | mV/mA scaling, offset `+12`/`+16`/`+20`, INI current-range per target profile |
| B1 | Header/step field tables for 612/696 | ✅ | Offset, dtype, size, version in one registry (`schema/fields.py`); 696 tail deferred to C6 |
| B2 | Parser/schema/compiler offset alignment | ✅ | `fEndV`, `fEndI`, shared-prefix fields aligned; ASSB divergences documented |
| B3 | Read regression over all 102 files | ✅ | Version, payload offset, step size/count cataloged |
| B4 | Semantic golden tests | ✅ | `GOLDEN_SEMANTIC_EXPECTATIONS.json` + 7 fixture byte checks; parser cross-check |
| B5 | Controlled-pair intake validation | ✅ | PNE02 pairs reopen-verified; PNE16 `fIref`/`fVref` waived via shared-prefix evidence |

**Recommended order inside Gate B:** B0 → B5 → B2 → B4 → finish B1 unknowns.

**Progress record**
- B1 partial: evidence registry with confidence levels; LOOP at `+48/+52` confirmed
- B3: `example/fixtures/catalog.json` locks geometry and provenance for 102 files
- End-condition offsets unified: `fEndV=28`, `fEndI=32`, `fEndC=36` across parser/schema/compiler
- Intake tooling: `tools/compare_sch`, `docs/GATE_B.md`
- **Ensol sch_maker adoption (2026-09-01):** validated 612-byte map — `+12` mV setpoint, `+16` mA current, `+20` s duration, `+28`/`+32` end V/I; parser + compiler updated; golden capacheck regression
- **Corpus evidence pass (2026-09-02):** 23,281 schedules mined; canonical 612-byte
  sampling, DOD, capacity-reference, and loop fields registered as `corpus_inferred`.
- **Gate B exit (2026-09-03):** `gate_b_passed=true`. PNE02 controlled pairs cover
  `fVref`, `fIref`, `fEndV`, `fEndI`, `loop_count`, `loop_target`, `record_time_s`.
  PNE16 `fIref`/`fVref` waived via shared-prefix evidence
  (`planning/GATE_B_CONTROLLED_PAIR_WAIVERS.json`).
- Writer Q_nom is fail-safe and explicit: only
  `CellProfile.nominal_capacity_mAh` may drive compilation; stack/filename inference is
  viewer-only.

**Blocking items (see also §11):** PNE voltage/L-level encoding; dual capacity models (viewer vs writer Q_nom).

---

### 6.4 Gate C — Actually Compatible SCH Writer

| | |
|---|---|
| **Status** | 🔄 **Lab-blocked on C5** ← **current focus** |
| **Depends on** | Gate B exit (`gate_b_passed=true`) |
| **Exit criteria (original)** | 612 writer round-trips semantically; 696 lab parity; PNE PC smoke test recorded; no placeholder header |
| **Exit criteria (accepted 2026-09-03)** | See honest assessment below — software slice done; **C5 remaining**; C6 reframed as framing/corpus policy |
| **Next gate** | Gate D (deferred until requested) |

| # | Task | Status | Completion criteria | Honest note |
|---|------|--------|---------------------|-------------|
| C0 | Guard experimental output | ✅ | Default CLI blocks `build`; explicit flag + warning | Solid |
| C0.1 | Build validation manifest | ✅ | Manifest on every write path | Solid |
| C0.2 | Template-preserving patch slice | ✅ | Writer-ready allowlist + byte preservation | **Preferred near-term lab path** vs from-scratch `build` |
| C1 | Full header for `0x00010003` | ✅ | No 512-byte placeholder; 1760 B framing | Solid |
| C2 | Step compiler | ✅ | mode, end, loop/goto, sampling, SOC | **DCR not packed** (Excel≠Ensol); intentional |
| C3 | Internal round-trip | ✅ | Semantic write→read on Ensol offsets | Covers smoke/intent fields; not every module E2E (that is Gate D) |
| C4 | ASSB cross-check | ✅ | Layout + step-count + overlapping fields | **Thin**: shared ASSB candidate compare is mostly `fEndC`; currents checked via ASSB helpers. Do not read as full ASSB semantic parity |
| C5 | PNE PC smoke test | ⏳ **blocking** | CTSEditorPro reopen (+ optional run) recorded | **Only Gate C exit item left** |
| C6 | `0x00010004/696` | ✅ *reframed* | Header 1844 + 696 steps (612 prefix + zero tail) | Original “696 lab parity / semantically verified” **not** fully claimed. Secured corpus tails are all-zero; writer matches that. Nonzero-tail mapping deferred until evidence appears |

**Recommended order:** stop new Gate C software work → **run C5** → then decide Gate D.

#### Gate C honest assessment (2026-09-03)

**What went right (direction is sound)**
1. Gate order respected: B evidence → C0 safety → C1 header → C2 compiler → C3/C4 validators before equipment.
2. Dual writer strategy is correct: `patch-sch` (template-preserving, evidence-gated) is safer for near-term lab use; from-scratch `build` stays experimental until C5.
3. Refusing to invent DCR / 696-tail semantics without bytes in corpus was the right call.
4. C5 is correctly the remaining hard gate — software cannot close equipment reopen.

**Where status was overstated (corrected here)**
1. **C6** was marked done against a stronger original bar (“696 lab parity / semantically verified”). Accepted bar is now: **framing + corpus-aligned zero-tail policy**. Full 696 semantic parity of complex lab schedules remains future work if tails become nonzero or if module E2E (Gate D) requires it.
2. **C4** is a useful smoke cross-check, not deep ASSB field-by-field validation of writer outputs.
3. **§6.1** previously still said round-trip was incomplete — that was stale after C3.
4. **§11** still listed some Gate B items as open/blocking after `gate_b_passed` — cleaned below.

**Optimal next moves**
| Priority | Action | Why |
|--------:|--------|-----|
| 1 | **C5 lab smoke** on `example/smoke_rest_cc_end.sch` | Sole remaining Gate C exit criterion |
| 2 | Prefer `patch-sch` for real schedule edits until C5 signed | Lower risk than from-scratch builds |
| 3 | Do **not** start Gate D until asked | Per product decision; C2/C3 already satisfy D’s software dependency minimum |
| 4 | Do **not** invent 696-tail or DCR binary maps | Wait for nonzero evidence / controlled pairs |
| 5 | After C5 pass: mark Gate C exited with documented gaps (DCR IR-only; 696 tail unused) | Keeps exit criteria honest |

**Rules**
- Until C5 passes, never label CLI `build` output as equipment-executable
- Do not mark Gate C complete without C5 sign-off
- C6 “complete” means framing/corpus policy only unless upgraded later

**Progress record**
- C0 / C0.1 / C0.2 / C1 / C2 / C3 / C4: implemented 2026-09-03 (see git history `dbf7fed`…`1eeceb3`)
- C5: checklist [`GATE_C_EQUIPMENT_SMOKE_CHECKLIST.md`](GATE_C_EQUIPMENT_SMOKE_CHECKLIST.md); smoke assets `example/smoke_rest_cc_end.*`
- C6: [`SCH_696_TAIL_ANALYSIS.md`](SCH_696_TAIL_ANALYSIS.md) — 92 catalog fixtures / 2056 steps, zero nonzero tails
- User action list: [`USER_ACTION_ITEMS.md`](USER_ACTION_ITEMS.md)

---

### 6.5 Gate D — Experiment Module Fixture Fidelity

| | |
|---|---|
| **Status** | ⏳ **Not started** (module `expand` prototypes exist) |
| **Depends on** | Gate C exit (C2, C3 minimum) |
| **Exit criteria** | Every P0 module passes `validate → expand → compile → parse → semantic compare` in one integration test |
| **Next gate** | Gate E |

| Priority | Module / harness | Status | Validation fixture / criteria |
|----------|------------------|--------|-------------------------------|
| P0 | Integration harness | ⏳ | End-to-end pipeline without external parser |
| P0 | Capacity model contract | ⏳ | Same Q_nom/current in viewer inference and writer compile |
| P0 | Formation, Cycle Life, Rest | ⏳ | Topology, I/V, loop vs representative originals |
| P0 | RPT, DC-IR | ⏳ | SOC reference, DCR window, goto semantics |
| P1 | HPPC | ⏳ | SOC staircase + pulses in `HPPC_Full range.sch` |
| P1 | capacheck, QPEED, in-situ | ⏳ | Golden topology for 8-file bimodal archive |

**Recommended order inside Gate D:** harness → capacity contract → Formation/Rest → Cycle Life → RPT/DC-IR → HPPC → capacheck/QPEED.

---

### 6.6 Gate E — Editing UX and Advanced Features

| | |
|---|---|
| **Status** | 🔄 **Partial** (read/edit tools exist; export UX ⏳) |
| **Depends on** | Gate C exit (semantic export requires trusted writer) |
| **Exit criteria** | Flow editor production-ready; unsafe export blocked; optional `.sch` → IR import |
| **Next gate** | Gate F |

| # | Task | Status | Completion criteria |
|---|------|--------|---------------------|
| E1 | Viewer/resume/bulk editor regression | 🔄 | Fixture-based GUI/CLI regression coverage |
| E2 | Flow editor (palette, canvas, properties, preview) | 🔄 | Linear DAG editor usable for real projects |
| E3 | Pre-export validation UX | ⏳ | Block invalid loops, missing END, V/I violations |
| E4 | `.sch` → IR import (read-only) | ⏳ | Reverse-parse for review/clone before editable round-trip |
| E5 | Advanced: 0x00010007/EIS, fingerprint | ⏳ | Deferred until C6 + explicit schema work |
| E6 | pne_studio2 integration | ⏳ | Shared cell profile and export workflow |

**Progress record**
- `pne_scheduler flow` / `run_pne_scheduler_flow.py`: linear graph, `.schproj` load/save, Cell Profile, step preview
- Remaining: drag layout, rich widgets, undo/redo, **semantic SCH export**, GUI automation

**Rule:** Do not prioritize E3/E4 semantic export until Gate C is complete.

---

### 6.7 Gate F — Operational Release and Traceability

| | |
|---|---|
| **Status** | ⏳ **Not started** |
| **Depends on** | Gate C minimum (C5); full product sign-off needs Gate D |
| **Exit criteria** | Equipment-verified artifact with immutable hash, documented profile, hosted CI |
| **Next gate** | — (maintenance / version bumps) |

| # | Task | Status | Completion criteria |
|---|------|--------|---------------------|
| F1 | Target equipment compatibility report | ⏳ | PNE unit/range, CTSPro version, layout, open assumptions |
| F2 | Reopen approval record | ⏳ | Exact SHA-256 opens in CTSPro; operator result logged |
| F3 | Equipment smoke-test protocol | ⏳ | Dummy-cell procedure, abort criteria, signed result |
| F4 | Artifact immutability | ⏳ | Released hash == smoke-tested hash; reapproval on change |
| F5 | Release status labels | ⏳ | `analysis-only` / `CTSPro-reopen-verified` / `equipment-verified` in CLI/UI |
| F6 | Hosted CI | ⏳ | Packaging, fixtures, schema invariants, doc checks on every PR |

**Rule:** No “equipment-ready” label until F1–F4 pass for the **exact** artifact and target profile.

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
| PNE voltage/L-level encoding | **Partially resolved (612)** | Ensol map: `+12` mV (not `+16`); L-level fVref heuristic only for 15–80 V range; QPEED still needs pair |
| Dual capacity models | **Writer path resolved** | Writer uses explicit `cell_capacity_mAh` (= 1C mA); viewer may still infer Q_nom |
| Internal structure of `FILE_GRADE`, `STRUCT_EIS_SET` | Only names are present in Excel | Defer 0x00010007 to Phase 4 |
| Recommended Δt/ΔV/ΔQ values | UNKNOWN in cyclediag | Reverse-extract from internal standard sch samples |
| Writer validation on physical equipment | Not started | PNE PC load test is mandatory in Gate C5 |
| External ASSB parser availability | Dependency outside the repository | Make the internal parser the default source of truth and optionally cross-validate |
| Drift between fixture names and test expectations | **Confirmed** | Do not hide with skips; stabilize with manifest-based fixture lookup |
| Experimental output mistaken for production | **Mitigated, not resolved** | Default-block `build`; require manifest, reopen verification, and exact-hash release gates |
| Binary changes after parsed END ignored by diff | **Resolved** | Compare and report unparsed tails in addition to header and step records |
| Equipment profile inferred from filenames | **Prohibited** | Require explicit provenance/profile metadata and retain unknown when unavailable |
| Controlled-pair metadata is incomplete or inconsistent | Open | Add schema validation before evidence promotion (B5) |
| Resume renumbers steps without proven goto remapping | Open safety issue | Detect nonzero reference fields and block or remap only after controlled semantic confirmation |
| Documentation language/status drift | Partially resolved | README and user guide are English; audit remaining public docs and derive test status in CI |

---

## 9. Current focus (active gate)

**Active gate: C — lab-blocked on C5.**  
Software Gate C work should pause except C5 support. Gate D is deferred.

| Step | Gate | Action |
|------|------|--------|
| 1 | **C5** | Open `example/smoke_rest_cc_end.sch` in CTSEditorPro; fill checklist |
| 2 | C exit | After C5 sign-off, mark Gate C complete with documented gaps (DCR IR-only; 696 tail unused) |
| 3 | D | Deferred until explicitly requested |
| 4 | F | Release gates later |

Completed software prerequisites: Gate A; Gate B (`gate_b_passed`); C0–C4; C6 framing/corpus policy.

See also: [`USER_ACTION_ITEMS.md`](USER_ACTION_ITEMS.md).

---

## 10. Reference Code Locations

| Path | Content |
|------|---------|
| `schema/reference/sch_file_structure_20250211.xlsx` | Official PNE field specification |
| `ASSB_Analyzer_dev/assb_analyzer/io/pne_converter.py` | SCH parser (read), current conditions, DCIR SOC rules |
| `ASSB_Analyzer_dev/assb_analyzer/io/cell_c_rate_reference.py` | C-rate ↔ capacity |
| `ASSB_Analyzer_dev/assb_analyzer/io/classification_bulk_apply.py` | SCH structure fingerprint |
| `_vendor/Ensol_PNE_framework/pne_app/io/pne_converter.py` | Local partial reader |
| `pne_studio2/assets/presets/06_assb_design_stack.json` | Cell design preset (reference for capacity estimation) |

---

## 11. Discovered issues backlog

New problems found during implementation are recorded here first, then promoted into the
relevant Gate task table (§6.2–6.7). Closed items stay for audit trail.

| Date | Gate | Severity | Issue | Status | Resolution / next action |
|------|------|----------|-------|--------|--------------------------|
| 2026-08-31 | B | blocking | PNE voltage/L-level encoding (`+12` mode vs `+16` fVref) | **resolved for writer path** | Ensol map + Gate B pairs: `@12` volt/vlim, `@16` current_mA |
| 2026-08-31 | B | blocking | Dual capacity models (CellProfile vs stack-inferred Q_nom) | resolved | Writer uses explicit `CellProfile.nominal_capacity_mAh`; inferred Q_nom is display-only |
| 2026-08-31 | B | normal | Controlled-pair metadata incomplete → evidence promotion unsafe | resolved | B5 intake validation + PNE02 pairs; PNE16 waived |
| 2026-09-03 | C | **blocking** | C5 equipment smoke still required before executable builds | open | `GATE_C_EQUIPMENT_SMOKE_CHECKLIST.md` + `example/smoke_rest_cc_end.sch` |
| 2026-09-03 | C | normal | C6 original “696 semantic lab parity” stronger than delivered | **accepted waiver** | Reframed: framing + zero-tail corpus policy; see §6.4 honest assessment |
| 2026-09-03 | C | normal | C4 ASSB cross-check is thin (layout/steps/`fEndC`) | accepted | Enough as smoke; deepen only if C5 or lab diffs demand it |
| 2026-09-03 | C | normal | 696-byte tail (612–695) all-zero in secured corpus | resolved | Writer zero-pad matches corpus; `SCH_696_TAIL_ANALYSIS.md` |
| 2026-09-03 | C | normal | DCR binary offsets unresolved | accepted deferral | IR-only until controlled evidence; blocks DC-IR fidelity (Gate D), not C5 |
| 2026-08-31 | E | safety | Resume may renumber steps without goto remap proof | open | Block or remap only after semantic confirmation; track under E1/resume |
| 2026-09-01 | B | low | README test badge lags actual count | open | Sync badge when next touching README |
| 2026-08-31 | C | normal | 89/93 lab fixtures use `0x10004/696`, not 612-byte layout | mitigated | C6 framing writer exists; full schedule parity deferred |
| 2026-09-01 | B | normal | fEndV unit mismatch (fixture mV vs compiler V) | resolved | Ensol adoption; `tests/test_unit_contract.py` |
| 2026-09-01 | B/D | normal | Golden fixtures locked from user intake (7 selected, PNE02+PNE16) | done | `planning/GOLDEN_FIXTURES_LOCKED.json` |
| | | | *(add new rows here)* | | |
