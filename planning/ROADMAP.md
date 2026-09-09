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
| 2026-09-03 | Gate C audit: C5 blocking; C6 reframed; lessons checklist + modular UX vision (§1, §5.6, §6.6) |
| 2026-09-03 | Clarified UX intent: Autolab Nova + LabVIEW **feel** for schedule/module authoring — not realtime instrument control |
| 2026-09-06 | Audited all step-field evidence against PNE02 controlled pairs and corpus mining; replaced the single-purpose C5 smoke fixture with one combinatorial `smoke_writer_probe` covering charge/discharge/LOOP/sampling so one reopen suffices (`GATE_C5_EVIDENCE_COVERAGE.md`) |
| 2026-09-06 | Fixed the open resume safety issue: LOOP goto targets are now remapped to post-splice step numbering (or resume is blocked with a clear error) instead of silently keeping stale original step numbers |
| 2026-09-06 | Code audit pass: `write_sch` no longer discards `compile_step_warnings()` (CLI `build` now prints/records DCR, `goto_step_id`, and the newly-added `end_capacity_fraction`/`fEndC` warnings), fixed a dead label-check in `insitu_cycle`, and fixed a dataclass-field type-resolution bug in `bulk_edit` that silently turned negative int params into floats |
| 2026-09-06 | Second audit pass (background agent + manual verification): fixed a Gate B5 evidence-integrity bug where a controlled pair's `expected_field` mismatch was only a warning, not an error, letting the wrong offset be counted as controlled-pair evidence; fixed an overly-permissive `_L_EXPLICIT` regex in `stack/levels.py` that mistook ordinary letter+digit filename fragments (e.g. "Cell01", "bimodal-30") for explicit L-level markers, confirmed against 2 real corpus fixtures |
| 2026-09-06 | Roadmap-process audit: discovered hosted CI (`.github/workflows/ci.yml`, live since 2026-09-02) has been red for 12 consecutive commits despite ROADMAP claiming F6 "not started"; corrected §6.1/§6.7/L13. Corrected two now-false "scheduled for deletion" notes in `PROJECT_STRUCTURE.md` (`io/reader.py`, `validate/roundtrip.py` are both load-bearing). Synced `planning/README.md`'s index (10 missing files). Added `ruff` as a lint dev-dependency, wired into CI |
| 2026-09-06 | Pushed the fix (`d60ea3b`); hosted CI green again (run #33). Deleted 3 confirmed-dead code paths (2 tools scripts, 1 3.7MB vendor archive); README now shows a live GitHub Actions badge instead of a static count. Re-split Gate D/E/F by per-task equipment dependency (only C5, E3/E3.1, F1–F4 actually need a PNE PC) and unblocked the rest for parallel work per user authorization. Found 6 unmerged `cursor/*` branches from earlier Cursor Cloud runs — 3 touch UI (theming, module recipes, schedule explanation) and look salvageable as design reference, not junk; see §6.6.1 and `UI_UX_NOTES.md` |
| 2026-09-08 | **C5 passed on PNE02** (`smoke_writer_probe.sch`); Gate C exited with documented gaps (DCR IR-only; 696 tail unused; CLI `build_sch_header` 54-byte gap open). OCV/Impedance/Pattern/Balance IR+compiler stubs + offset registry (`STEP_TYPES_EXTENDED.md`); Gate D P0 harness started (`validate/gate_d_harness.py`) |
| 2026-09-08 | Gate D software slice completed: capacity contract tests; Formation/Rest/Cycle Life + RPT/DC-IR + HPPC/capacheck/QPEED/in-situ harness; golden family topology compares (`validate/topology.py`) |
| 2026-09-08 | Gate D verification method + audit remediations: `GATE_D_VERIFICATION.md`, harness charge-V/loop checks, `run_gate_d_verification` → `GATE_D_VALIDATION_REPORT.json` (`gate_d_passed=true`; current matrix 49 pass) |
| 2026-09-08 | Post-C5 status sweep (L5): cleared stale "behind C5" wording from the gate diagram, Gate E `Depends on`/Rules/E3/E3.1 rows, and Gate F F1–F4 — the C5 pass satisfied those dependencies. Added [`GUARDRAILS.md`](GUARDRAILS.md), a topic-grouped reading view of §5.6/§8/§11 |
| 2026-09-08 | Gate D mutation backtest found and fixed two verification holes (V6 never compared module expansions; skips did not block `gate_d_passed`) — see §11. Archived closed-gate evidence and consumed analysis outputs to [`../legacy/`](../legacy/README.md); only files with zero `.py` references were moved, and the C5 signed record stays cited from Gate F2 |
| 2026-09-08 | Gate E/pattern re-audit: added the missing module-composition contract (single final END, rebased LOOP references), separated imported patch sessions from authored projects, added pattern trust/catalog and desktop UX requirements, and established [`PATTERN_VALIDATION_PLAN.md`](PATTERN_VALIDATION_PLAN.md). DOD@384 and module SOC cutoff (`fEndC@36`) now require separate controlled pairs before SOC-dependent pattern approval |
| 2026-09-09 | Gate E workspace shipped: one window (설정 → 프로토콜 → 절차 → 검증 → 내보내기) on a Qt/QML default shell with a Tk fallback, both driving a shell-free `ui/workspace_model.py`. Added `spec/` ParameterSpec, lenient `ir/loader.py`, `ir/procedure.py`, `ir/equipment_profile.py` (schproj v2), staged export gates in `release.py`, and Korean summaries in `report/`. CI now installs the `[gui]` extra so the default UI is actually exercised. E2.4/E3 → ✅ |
| 2026-09-09 | Gate E2.1/E2.3/E4 and F5 closed: primitive palette (fragment-local repeat instead of a bare LOOP), append-only method library keyed to equipment, byte-preserving `.sch` import session (2 bytes changed for one field edit; CTSPro header untouched), and release labels bound to a content hash so an approval cannot follow an edited file |

---

## 1. Goal

Enable creation of `.sch` binary schedule files for PNE cyclers **without using the native CTSEditorPro workflow as the primary authoring tool**.

### 1.1 Product vision (target UX)

**UI design inspiration (not a product clone):** schedule authoring should *feel* like building a method in **Autolab Nova** and wiring experiment blocks in **LabVIEW** — because that workflow already matches how battery schedules are composed from reusable modules.

What that means in practice:

| Feel we want | In this product |
|--------------|-----------------|
| Drop / place **modules** then tune parameters | Experiment modules (Formation, Cycle Life, RPT, HPPC, …) expand to steps |
| Ordered **procedure** of commands | Step list: CC, CCCV, Rest, Loop, END, … with a property pane |
| Library of reusable methods | Versioned `.schproj` / module templates |
| Clear cell / setup before editing | Explicit **Cell Profile** (1C = mA, limits, equipment) — never inferred for write |
| Check readiness before leaving the editor | Pre-export validation + manifest + release labels |

**Out of scope (clarified 2026-09-03):** realtime potentiostat-style instrument control, live I–V plots, CTSMonPro replacement. Export `.sch` → open/run on CTS remains the execution path. “Autolab” here is **visual/interaction language for making schedules**, nothing more.

Nova and LabVIEW are **co-equal metaphors** for the same idea: modular composition. Prefer a clean procedure + module palette first; a free-form campaign canvas can follow if needed.

### 1.2 Functional goals

- Users author **schedules from primitives + modules**, not raw binary fields
- Users enter a **C-rate**; current (mA) is calculated from an **explicit** reference capacity (1C = ___ mA)
- Generated `.sch` files must be **CTSPro-reopen-verified** (and later equipment-verified) before any “executable” label
- Dual authoring paths: **`patch-sch`** (template-preserving, preferred near-term) and experimental from-scratch **`build`**

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
| P1 | **Autolab/LabVIEW-feel schedule workspace** | Procedure + module palette + property pane + library (authoring UX only) | Trusted IR + Gate C exit |
| P2 | **Parameter sweep and batch export** | Produces controlled variants after one template is verified | Safe patcher and manifest |
| P2 | **Approval/audit bundle** | Packages SCH hash, human-readable step table, diff report, screenshots, and operator approval | Stable export workflow |
| P3 | **Campaign / multi-module canvas** | Extra LabVIEW-like graph if procedure+modules UI is not enough | Gates D–E |

Features that should not be prioritized yet are live hardware control, automatic upload to
cycler PCs, realtime run plots, and broad 0x00010007/EIS generation. Their failure modes are
harder to inspect than offline file generation and they depend on unresolved schemas
or are simply outside the intended UX (authoring only).

### 5.6 Lessons from Gates A–C → permanent planning checks

These are **recurring failure modes** observed while closing A–C. Every later gate plan and
status update must pass this checklist (also use before claiming an exit criterion).

> A topic-grouped reading view of these lessons plus §8/§11 (evidence discipline,
> writer safety, status honesty, currently-open items) lives in
> [`GUARDRAILS.md`](GUARDRAILS.md). This table stays the authoritative source.

| # | Lesson (what went wrong or almost went wrong) | Permanent check |
|---|-----------------------------------------------|-----------------|
| L1 | Assumed Excel / ASSB / Ensol / corpus agreed on offsets & units | Require an **evidence hierarchy**: controlled pair > reopen-verified fixture > corpus majority > Excel name. Document conflicts; do not silently pick one |
| L2 | Compiler wrote V while fixtures store mV (unit contract drift) | Any new packed field needs **unit + scale tests** before `writer_ready` |
| L3 | Invented / guessed maps (LOOP `+84`, DCR Excel offsets, 696 nonzero tails) without bytes | **No speculative packing.** Missing evidence → IR-only, waiver, or deferral in §11 |
| L4 | Marked tasks “done” against stronger wording than delivered (C6 “lab parity”, thin C4) | Exit criteria must match **deliverable depth**; if scope shrinks, **reframe the bar** and record waiver |
| L5 | Status tables went stale after code advanced (round-trip, Gate B blockers) | Status refresh is part of the change: ROADMAP §6 / §9 / §11 updated in the same PR as the claim |
| L6 | From-scratch `build` looked “done” before equipment reopen | **Never** label executable without C5/F-class reopen for that artifact class |
| L7 | Filename / stack inference tempting for Q_nom and equipment | Writer path: **explicit profile only**; inference is viewer/analysis-only |
| L8 | Skipping evidence promotion process burned time; waivers unblocked correctly | Controlled-pair **or** documented waiver before promoting `writer_ready` |
| L9 | Dual writer paths confused risk (patch vs build) | Prefer **`patch-sch`** for near-term lab edits; keep `build` experimental until reopen proves framing |
| L10 | Software work continued past the only true blocker (C5) | When lab-blocked, **pause non-support software** and push user action items |
| L11 | Hosted CI / badge lag treated as Gate A “done” signal | Local green ≠ release; F6 is separate |
| L12 | UX/export prioritized before trusted writer | **No semantic export UX (E3+)** until Gate C exit (or explicit waiver) |
| L13 | Worse than L11 anticipated: hosted CI didn't just lag, it existed, was active, and was **red for 12 consecutive commits** (2026-09-02→03) while ROADMAP still claimed Gate F6 "not started" — nothing in the process ever checked GitHub's actual workflow status against the doc | Periodically verify external status (CI, badges) against ROADMAP claims, not just local `pytest`; use a real GitHub Actions status badge in README (not a static hand-set one) so silent red CI is visible on the repo front page instead of requiring someone to remember to check |

**Gate planning template (paste into new gate notes):**

```text
[ ] Evidence hierarchy named for each new packed field
[ ] Unit/scale tests added or N/A justified
[ ] No invented offsets (corpus or pair cited)
[ ] Exit criteria wording matches actual depth
[ ] ROADMAP status rows updated with the claim
[ ] Executable / equipment-ready label? → reopen record required
[ ] Writer uses explicit CellProfile / equipment profile only
[ ] writer_ready promotion: pair or §11 waiver
[ ] Near-term path: patch-sch vs experimental build stated
[ ] If blocked on lab/user: USER_ACTION_ITEMS updated; software paused
```

**Can these checks govern future plans?** **Yes.** They are process constraints, not one-off notes.
Gate D/E/F task definitions below already inherit them; new work that fails the template should
not be marked done.

---

## 6. Implementation Roadmap

Work proceeds **Gate A → B → C → D → E → F** in order for anything that reads on
an equipment-readiness claim. That said, most of D/E/F's *individual tasks* have
no equipment dependency at all. The remaining physical checkpoints are pattern PV1/PV4
(controlled pairs and CTSPro batch reopen), optional PV6/F3 execution, and any new exact-artifact
release approval. E3/E3.1 **UI implementation itself** is software-only; applying a verified label
inherits the pattern/F-gate evidence. **2026-09-06: user authorized starting
equipment-independent D/E/F work in parallel with the C5 wait** instead of waiting for C5 to close Gate C first.
Do not start a later Gate's *equipment-dependent* tasks until the current gate's
exit criteria are met (or an explicit waiver is recorded in §11) — the ordering
rule is about claims and equipment-facing work, not about every line item.

```
Gate A  개발 기반          ✅ complete (local)
  ↓
Gate B  바이너리 스키마    ✅ complete
  ↓
Gate C  호환 SCH writer    ✅ exited 2026-09-08 (C5 PNE02)
  ↓                         (parallel track below can run now, per-task)
Gate D  모듈 픽스처 검증   ✅ software exit 2026-09-08 (P0/P1)
  ↓
Gate E  모듈형 스케줄 UX   🔄 active — workspace shipped 2026-09-09; E2.1/E2.3/E4 remain
  ↓
Gate F  운영 릴리스 / 추적성  F5/F6 unblocked; F1–F4 now released by C5, need release-record work
```

Before claiming any gate **exit**, run the §5.6 checklist — this still applies in
full; only the "when can I start the next gate's software-only tasks" question
changed.

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
| Test execution environment | **Restored, hosted CI green** | Local `pytest` green (264+). `.github/workflows/ci.yml` (live since 2026-09-02) was red for 12 consecutive commits on an `access_parser` collection bug; fixed and pushed 2026-09-06 (`d60ea3b`) — [run #33](https://github.com/Hwiho/pne_scheduler/actions/runs/34037824999) is green (Ruff + Pytest + corpus smoke) |

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
| A2 | Establish the test command and CI baseline | ✅ | `python -m pytest tests/ -q` passes; README shows a live GitHub Actions status badge (2026-09-06, replacing a static hand-set count that could go stale) |
| A3 | Add fixture inventory tests | ✅ | ZIP counts (8, 93) + HPPC presence verified automatically |

**Notes:** A hosted CI workflow already exists (`.github/workflows/ci.yml`, since 2026-09-02) — "hosted CI" is not a Gate A/F gap in the sense of "not built," only in the sense of "not currently green" (see §6.1, §11). Full CI maturity (F6: packaging, schema-invariant checks, doc checks on every PR) remains future work. Local pass count is not equipment-compatibility evidence regardless of CI color.

**Progress record**
- A1: package/subpackage imports verified from editable install and clean-target wheel
- A3: 8 + 93 + 1 HPPC = 102 fixtures locked
- A2: 252 tests pass locally (1 skipped, lab-only); README badge synced (2026-09-06)

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
| **Status** | ✅ **Exited 2026-09-08** (C5 PNE02 smoke passed; gaps documented) |
| **Depends on** | Gate B exit (`gate_b_passed=true`) |
| **Exit criteria (original)** | 612 writer round-trips semantically; 696 lab parity; PNE PC smoke test recorded; no placeholder header |
| **Exit criteria (accepted 2026-09-03 / closed 2026-09-08)** | Software slice C0–C4 + C6 framing; **C5 signed on PNE02**; remaining gaps: DCR IR-only, 696 tail unused, CLI header 54-byte unexplained region |
| **Next gate** | Gate D (in progress) |

| # | Task | Status | Completion criteria | Honest note |
|---|------|--------|---------------------|-------------|
| C0 | Guard experimental output | ✅ | Default CLI blocks `build`; explicit flag + warning | Solid |
| C0.1 | Build validation manifest | ✅ | Manifest on every write path | Solid |
| C0.2 | Template-preserving patch slice | ✅ | Writer-ready allowlist + byte preservation | **Preferred near-term lab path** vs from-scratch `build` |
| C1 | Full header for `0x00010003` | ✅ | No 512-byte placeholder; 1760 B framing | Solid |
| C2 | Step compiler | ✅ | mode, end, loop/goto, sampling, SOC | **DCR not packed** (Excel≠Ensol); intentional |
| C3 | Internal round-trip | ✅ | Semantic write→read on Ensol offsets | Covers smoke/intent fields; not every module E2E (that is Gate D) |
| C4 | ASSB cross-check | ✅ | Layout + step-count + overlapping fields | **Thin**: shared ASSB candidate compare is mostly `fEndC`; currents checked via ASSB helpers. Do not read as full ASSB semantic parity |
| C5 | PNE PC smoke test | ✅ | CTSEditorPro reopen (+ optional run) recorded | **Passed PNE02 2026-09-08** — checklist filled; DOD/SOC UI optional not shown |
| C6 | `0x00010004/696` | ✅ *reframed* | Header 1844 + 696 steps (612 prefix + zero tail) | Original “696 lab parity / semantically verified” **not** fully claimed. Secured corpus tails are all-zero; writer matches that. Nonzero-tail mapping deferred until evidence appears |

**Recommended order:** ~~run C5~~ → Gate D module fidelity → Gate E authoring UX.

#### Gate C honest assessment (2026-09-03; C5 closed 2026-09-08)

**What went right (direction is sound)**
1. Gate order respected: B evidence → C0 safety → C1 header → C2 compiler → C3/C4 validators before equipment.
2. Dual writer strategy is correct: `patch-sch` (template-preserving, evidence-gated) is safer for near-term lab use; from-scratch `build` stays experimental until C5.
3. Refusing to invent DCR / 696-tail semantics without bytes in corpus was the right call.
4. C5 equipment reopen closed Gate C — capacity slot fix (`+12`) and Cycle-free LOOP probe were the last lab lessons.

**Where status was overstated (corrected here)**
1. **C6** was marked done against a stronger original bar (“696 lab parity / semantically verified”). Accepted bar is now: **framing + corpus-aligned zero-tail policy**. Full 696 semantic parity of complex lab schedules remains future work if tails become nonzero or if module E2E (Gate D) requires it.
2. **C4** is a useful smoke cross-check, not deep ASSB field-by-field validation of writer outputs.
3. **§6.1** previously still said round-trip was incomplete — that was stale after C3.
4. **§11** still listed some Gate B items as open/blocking after `gate_b_passed` — cleaned below.

**Optimal next moves**
| Priority | Action | Why |
|--------:|--------|-----|
| 1 | Gate D P0 harness + Formation/Rest/Cycle Life | Software-only module fidelity |
| 2 | Prefer `patch-sch` for real schedule edits until CLI `build_sch_header` gap is understood | Lower risk than from-scratch builds for production edits |
| 3 | OCV/Impedance/Balance controlled pairs when lab time allows | Type codes stubbed; field map empty in corpus |
| 4 | Do **not** invent 696-tail or DCR binary maps | Wait for nonzero evidence / controlled pairs |
| 5 | Documented Gate C gaps remain: DCR IR-only; 696 tail unused; 54 header bytes | Keeps exit criteria honest |

**Rules**
- Label CLI `build` as equipment-smoke-verified for the probe class only; new type classes (OCV/Imp/…) need their own reopen
- C6 “complete” means framing/corpus policy only unless upgraded later
- Apply §5.6 checklist when claiming any further C/D work complete

**Progress record**
- C0 / C0.1 / C0.2 / C1 / C2 / C3 / C4: implemented 2026-09-03 (see git history `dbf7fed`…`1eeceb3`)
- C5: checklist [`GATE_C_EQUIPMENT_SMOKE_CHECKLIST.md`](../legacy/planning/GATE_C_EQUIPMENT_SMOKE_CHECKLIST.md); smoke assets `example/smoke_rest_cc_end.*` (kept as a fallback)
- C5 (2026-09-06): field-by-field evidence audit against `schema/fields.py`,
  `GATE_B_CORPUS_EVIDENCE.json`, `GOLDEN_SEMANTIC_EXPECTATIONS.json`, and all 9
  reopen-verified PNE02 pairs — see [`GATE_C5_EVIDENCE_COVERAGE.md`](../legacy/planning/GATE_C5_EVIDENCE_COVERAGE.md).
  Conclusion: every writer-ready/high-confidence field was already individually
  reopen- or corpus-verified; the only genuinely untested axis was a from-scratch
  build combining charge+discharge+LOOP+per-step sampling in one header. Added a
  single combinatorial fixture (`modules/smoke_writer_probe.py`,
  `example/smoke_writer_probe.sch`) so one physical reopen covers that instead of
  several separate sessions; checklist rewritten around it. Byte-diffing
  `build_sch_header()` against a real lab header also surfaced 54/1760 unexplained
  header bytes (see §11) — logged, not packed (no evidence for their meaning yet).
- **C5 (2026-09-08):** PNE02 CTSEditorPro smoke **passed** on `smoke_writer_probe.sch`
  (open/save, capacity 800 mAh, charge/discharge/LOOP/END, optional channel run).
  DOD/SOC 40% not shown in UI (optional). Common-safety Cap confirmed at `+12`.
- C6: [`SCH_696_TAIL_ANALYSIS.md`](../legacy/planning/SCH_696_TAIL_ANALYSIS.md) — 92 catalog fixtures / 2056 steps, zero nonzero tails
- Extended types: [`STEP_TYPES_EXTENDED.md`](STEP_TYPES_EXTENDED.md)
- User action list: [`USER_ACTION_ITEMS.md`](USER_ACTION_ITEMS.md)

---

### 6.5 Gate D — Experiment Module Fixture Fidelity

| | |
|---|---|
| **Status** | ✅ **P0/P1 software exit 2026-09-08** — re-verified via [`GATE_D_VERIFICATION.md`](GATE_D_VERIFICATION.md) (`gate_d_passed=true`) |
| **Depends on** | Gate C2 + C3 (both done) — **not** blocked on equipment |
| **Exit criteria** | Every P0 module passes `validate → expand → compile → parse → semantic compare` in one integration test |
| **Next gate** | Gate E |
| **Verification** | Method + audit + runner: [`GATE_D_VERIFICATION.md`](GATE_D_VERIFICATION.md), [`GATE_D_VERIFICATION_AUDIT.md`](GATE_D_VERIFICATION_AUDIT.md), `python -m pne_scheduler.tools.run_gate_d_verification` → [`GATE_D_VALIDATION_REPORT.json`](GATE_D_VALIDATION_REPORT.json) |

Gate D is software-only. Module expands are **protocol templates**; golden compares use step-type *families* (`validate/topology.py`), not byte-identical clones. DCR binary packing stays IR-only (L3).

| Priority | Module / harness | Status | Validation fixture / criteria | Needs equipment? |
|----------|------------------|--------|-------------------------------|:---:|
| P0 | Integration harness | ✅ | `validate/gate_d_harness.py` + `tests/test_gate_d_harness.py` | No |
| P0 | Capacity model contract | ✅ | `tests/test_capacity_contract.py` — writer Q_nom only; viewer may disagree (L7) | No |
| P0 | Formation, Cycle Life, Rest | ✅ | Harness topology/I/V + golden family (`golden-formation-696`, `golden-cycle-612-long`) | No |
| P0 | RPT, DC-IR | ✅ | SOC ladder + pulse topology; DCR warnings; Excel DCR offsets remain 0 | No |
| P1 | HPPC | ✅ | Harness + `HPPC_Full range.sch` family (charge/discharge/rest) | No |
| P1 | capacheck, QPEED, in-situ | ✅ | Harness + golden families; QPEED `full`/`soc_setting`; in-situ label | No |

**Recommended order inside Gate D:** ~~harness → capacity → modules~~ done.

**Planning check:** §5.6 (especially L3 DCR evidence, L7 capacity contract, L4 honest exit depth). Extended step types (OCV/Imp/Balance) remain stubbed pending lab pairs (`STEP_TYPES_EXTENDED.md`) — outside Gate D module rows.

**Honest gaps remaining after Gate D software exit**
- Modules ≠ full lab schedule length/order (templates by design)
- `fEndC@36` packs but stays `semantic_unverified` (warnings expected on RPT/DCIR/HPPC)
- DCR window never packed without controlled pairs
- Capacheck module order is CYCLE→LOOP; some goldens differ — family match only
- HPPC full, QPEED full/SOC-setting topology와 QC 3종은 2026-09-09 구현되어 각각
  62, 167/11 및 17/18/24–26 step shape를 검사한다. 다만 기존 family-template의
  exact recipe, DOD/fEndC/CC mode-limit 의미와 CTSPro 표시 검증은 pattern acceptance에 남는다 — see
  [`PATTERN_VALIDATION_PLAN.md`](PATTERN_VALIDATION_PLAN.md).

---

### 6.6 Gate E — Modular Schedule UX (Nova + LabVIEW feel)

| | |
|---|---|
| **Status** | 🔄 **Partial** (E0/E0.5/E2.1/E2.3/E2.4/E3/E3.1/E4 ✅; E1/E2/E2.2 in progress; E5–E7 ⏳) |
| **Depends on** | **Nothing blocking as of 2026-09-08** — E0–E2.4 never needed a trusted writer, and E3/E3.1's Gate C exit dependency was satisfied by the C5 PNE02 pass. Export UX is now gated by *evidence discipline* (§5.6 L6/L9), not by an unmet gate |
| **Exit criteria** | Schedule authoring feels like **module + procedure** composition (Nova/LabVIEW-like); multi-module END/LOOP composition is safe; pattern trust is visible; unsafe export blocked; library + Cell setup; byte-preserving imported patch session |
| **Next gate** | Gate F |
| **UX intent** | §1.1 — design *feel* for making schedules with modules; **not** Autolab instrument control |

Framing history: Gate E was once blanket-marked "depends on Gate C exit," which
over-blocked the authoring-UI tasks (E0–E2.4) — none of them write or export a
`.sch`, so none needed a trusted writer. That split was corrected 2026-09-06, and
on **2026-09-08 the C5 pass cleared the remaining E3/E3.1 dependency too**, so no
Gate E task is gate-blocked any more. What still constrains export is the standing
evidence discipline, not a pending gate: prefer `patch-sch` over from-scratch
`build` for production edits (L9), and never label output equipment-ready without
a reopen record for that exact artifact (L6, §6.7 F1–F4).

| # | Task | Status | Completion criteria | UX cue | Needs equipment? |
|---|------|--------|---------------------|--------|:---:|
| E0 | UX contract & IA | ✅ | Screens: Setup / Procedure / Modules / Library / Validate / Export; map to `ui/` | Clean authoring layout | No |
| E0.5 | Composer / catalog / validator contract | ✅ | One final END; module-local LOOP refs rebased; structured issues; pattern metadata/trust | Safe foundation | No |
| E1 | Viewer/resume/bulk editor regression | 🔄 | Fixture-based GUI/CLI regression coverage | Review existing schedules | No |
| E2 | **Procedure editor** (ordered steps) | 🔄 | Insert/reorder/delete primitives; property pane; C-rate ↔ mA preview | Nova-like step list | No |
| | ↳ 2026-09-09: module-level add/duplicate/remove/move/reorder/detach, spec-driven property forms and C-rate ↔ mA preview all shipped in `ui/workspace_model.py`. **Primitive-level** step insert/delete is still absent — `detach()` freezes a preset into `custom_steps` but nothing edits an individual step yet. | | | |
| E2.1 | Primitive palette | ✅ | REST, CC, CCCV, CV, LOOP, END, OCV… with validated forms | Command blocks | No |
| | ↳ 2026-09-09: `modules/primitive.py` ships REST/OCV/CC/CCCV/CV charge and CC discharge as one-step modules with spec-driven forms. **LOOP and END are deliberately absent** as palette items: the composer owns the final END, and a LOOP target must resolve inside its own fragment (`1 <= target < position`), so repetition is `repeat_count`, which emits the LOOP and its target together. The catalog entry states both exclusions. | | | |
| E2.2 | **Module/pattern palette** | 🔄 | Variant + units + evidence status; only accepted Formation/Cycle/QC/RPT/HPPC/QPEED recipes promoted | LabVIEW-like modules | No |
| | ↳ 2026-09-09: `protocol/recipes.py` gives a purpose-first goal catalog carrying `trust_status`, surfaced in the UI via `TRUST_LABELS_KO`. Promotion stays open: no pattern has a CTSPro reopen record, so everything still shows as `prototype`. | | | |
| E2.3 | Method / project library | ✅ | Save/load versioned procedures & modules per equipment profile | Reusable methods | No |
| | ↳ 2026-09-09: `library.py` stores methods as append-only versions under `~/.pne_scheduler/library`, each recording the unit and SCH layout it was written for. Loading onto a different profile warns rather than blocks, ids are reassigned to avoid collision, and every load states that saved ≠ verified. `pne_scheduler library` lists them. | | | |
| E2.4 | Cell / equipment setup pane | ✅ | Explicit 1C mA, V limits, PNE unit/range, layout target; blocks export if missing | Setup before edit | No (the pane itself; it just *displays* a profile that later needs equipment-verified export) |
| E3 | Pre-export validation UX | ✅ | Block invalid loops, missing END, V/I violations | Readiness before export | No — **unblocked by the 2026-09-08 C5 pass** |
| E3.1 | Export path choice | ✅ | Default **patch-sch** onto approved template; optional experimental `build` | PNE safety | No — unblocked, but keep `patch-sch` as the default path per L9 |
| | ↳ 2026-09-09: template patch now precedes the from-scratch build in the ladder and carries `recommended=True` — a 권장 badge and highlighted button in the export tab, a `← 권장` marker in `pne_scheduler summary`. The build is retitled 실험적 and keeps `danger=True`. Tests assert the ordering and that exactly one option is recommended. | | | |
| E4 | `.sch` imported patch session | ✅ | Preserve source hash/raw bytes; writer-ready edits only; lossy `Clone as draft` separate | Open existing schedule | No — parser exists; safe session model does not |
| | ↳ 2026-09-09: `import_session.py` holds the source bytes and digest, offers only `get_writer_ready_fields()` for in-place editing, and emits an `SchPatchPlan` bound to the digest it read. Measured on a real 0x00010004 lab file: one float edit changes **2 bytes** and the 1760-byte CTSPro header is untouched. `Clone as draft` is a separate exit that names everything it discards. `pne_scheduler import-sch` reports both. | | | |
| E5 | Advanced: 0x00010007/EIS, fingerprint | ⏳ | Deferred until explicit schema evidence | Later | No (blocked on schema evidence, not equipment) |
| E6 | pne_studio2 integration | ⏳ | Shared cell profile and export workflow | Host embedding | Partial — integration itself is No; the export half inherits E3's block |
| E7 | Campaign canvas (optional) | ⏳ | Free-form multi-module graph **only if** E2–E2.2 is insufficient | Extra LabVIEW canvas | No |

**Progress record**
- 2026-09-09: **the unified workspace shipped** — one window for 설정 → 프로토콜 → 절차 → 검증 →
  내보내기, with PySide6/QML (`ui/workspace_qt.py` + `ui/qml/`) as the default shell and the Tk
  build (`ui/workspace.py`) as the fallback where PySide6 is absent. Neither shell decides
  anything: both drive `ui/workspace_model.py`, which has no Qt and no Tk import and is covered by
  `tests/test_workspace_model.py`. New supporting contracts: `spec/` (one declaration per
  parameter — unit, allowed/recommended range, basis, affected steps, verification level),
  `ir/loader.py` (lenient load that lists every repair), `ir/procedure.py` (module list is
  authoritative over the wiring), `ir/equipment_profile.py` (schproj v2 carries the target
  cycler; v1 migrates on save), `release.py`/`exporting.py` (staged export gates) and
  `report/summary.py` (Korean prose summary). 424 passed, 1 skipped; ruff clean.
  CI now installs the `[gui]` extra and asserts PySide6 is importable, so the default UI's
  coverage cannot silently skip — the L13 failure mode applied to a new surface.
- Detailed re-audited execution order and acceptance criteria:
  [`GATE_E_PLAN.md`](GATE_E_PLAN.md). Pattern implementation/reopen is a linked track:
  [`PATTERN_VALIDATION_PLAN.md`](PATTERN_VALIDATION_PLAN.md).
- 2026-09-09: E0.5 composer/catalog/preflight complete; HPPC 62-step, QPEED 167/11-step and QC 3종
  candidates implemented. Deterministic 10-pattern PNE02 batch is at
  [`../example/pattern_review_pack/2026-09-09/INDEX.md`](../example/pattern_review_pack/2026-09-09/INDEX.md).
  Every manifest remains `equipment_executable=false`; user PV4 reopen is still required.
- `pne_scheduler flow` / `run_pne_scheduler_flow.py`: linear graph, `.schproj` load/save, Cell Profile, step preview — **seed** for E2/E2.2
- 2026-09-06: found 3 abandoned Cursor Cloud branches with substantial unmerged UI work directly relevant to E2/E2.2/E2.3 (theming, recipe editing, schedule explanation) — see §6.6.1
- 2026-09-06: **ported the `cursor/update-roadmap-5ac9` theming + attach/detach work** (§6.6.1's first recommendation) — `ui/flow_theme.py` (per-module-type card colors/icons, rounded-card Tk Canvas rendering), `engine/duration.py` (schedule duration estimate with loop/CV-taper caveats surfaced as warnings, not silently dropped), and `FlowProjectModel.rewire()` (LabVIEW-style click-port-then-click-port attach/detach, reusing existing cycle validation). Added `ModuleStyle` entries for `smoke_rest_cc_end`/`smoke_writer_probe` (module types that didn't exist when the branch was written). 273 tests pass (was 264); GUI construction + rewire + duration estimate smoke-tested non-interactively (`tk.Tk()` + `withdraw()`, no visible window in this environment — a human should still open it once to confirm the visual result)
- Remaining for the intended feel: module palette prominence (E2.2), richer property forms (E2.1, still raw JSON), library (E2.3, `cursor/module-recipes-presets-5ac9`'s recipe concept is the recommended next port per `UI_UX_NOTES.md`), validation/export UX (E3 — **no longer gate-blocked** since the 2026-09-08 C5 pass), full undo/redo (the new `rewire()`'s returned notes are a natural logging seam for this, not yet wired to an undo stack)

**Rules**
- E3/E3.1 semantic export is **unblocked** (C5 passed 2026-09-08), but keep `patch-sch` the default export path and `build` explicitly experimental until the CLI header's 54-byte unexplained region is understood (L9, §11)
- Do not treat Gate D family-level green as protocol-pattern approval. SOC-dependent patterns
  also require separate DOD@384 and `fEndC@36` evidence as specified in the pattern plan.
- “Nova/LabVIEW-like” means **authoring interaction**, not feature parity with those products
- Apply §5.6 checklist on every E-task completion claim

#### 6.6.1 Prior art to check before building E0–E2.4 (found 2026-09-06)

Six unmerged `cursor/*` remote branches exist (Cursor Cloud background-agent runs,
never merged, diverged from master by up to 53 commits). Three touch the UI
directly and should be reviewed **before** starting fresh implementation of the
authoring UI, to avoid redoing work that already exists in some form:

| Branch | Touches | Relevance |
|--------|---------|-----------|
| `cursor/update-roadmap-5ac9` | `ui/flow_theme.py` (new, doesn't exist on master), heavy `ui/flow_editor.py` rework | Direct prior attempt at LabVIEW-style visual theming + wire/port interaction — exactly E2.2's "LabVIEW-like modules" cue |
| `cursor/module-recipes-presets-5ac9` | `ui/flow_editor.py`, `ui/flow_model.py`, `validate/roundtrip.py` | "Recipe" concept for charge/discharge/rest presets + a "pattern overview" — overlaps E2.1 (primitive palette) and E2.3 (library) |
| `cursor/explain-schedules-5ac9` | `ui/schedule_viewer.py`, `protocol/infer.py` | Plain-language schedule explanation — a plausible E3/Validate-screen feature once Gate C exits |

All three are **stale relative to current master** (diverged well before this
session's bug fixes and the C5 probe work) — treat them as design reference /
cherry-pick candidates, not as branches to merge wholesale. See
[`UI_UX_NOTES.md`](UI_UX_NOTES.md) for the extracted patterns and concrete
recommendations. The other 3 branches (`cursor/create-gate-b-baseline-dfb2`,
`cursor/gate-c-safety-manifest-eccb`, `cursor/mine-internal-dataset-dfb2`) touch
Gate B/C validation tooling, not UI — lower priority to review, listed in §11.

---

### 6.7 Gate F — Operational Release and Traceability

| | |
|---|---|
| **Status** | ⏳ **Not started on F1–F5**; **F6 done**. The C5 probe artifact can enter release-record work. A product release containing HPPC/QPEED/QC/Cycle presets still depends on the selected pattern pack's acceptance evidence |
| **Depends on** | For the exact C5 smoke artifact: record/hash work only. For authored pattern output: [`PATTERN_VALIDATION_PLAN.md`](PATTERN_VALIDATION_PLAN.md) PV4–PV5, plus PV6 if `equipment-run-verified` is claimed |
| **Exit criteria** | Equipment-verified artifact with immutable hash, documented profile, hosted CI |
| **Next gate** | — (maintenance / version bumps) |

| # | Task | Status | Completion criteria | Needs equipment? |
|---|------|--------|---------------------|:---:|
| F1 | Target equipment compatibility report | ⏳ | PNE unit/range, CTSPro version, layout, pattern/release scope, open assumptions | No for the C5 probe write-up; pattern scope waits on PV4–PV5 records |
| F2 | Reopen approval record | ⏳ | Exact SHA-256 opens in CTSPro; operator result logged | C5 source record exists for the smoke probe; every released pattern candidate needs its own hash/result in the batch pack |
| F3 | Equipment smoke-test protocol | ⏳ | Dummy-cell procedure, abort criteria, signed result | Partly — the C5 reopen is done; a *run* protocol (dummy cell, abort criteria) still needs a lab session if execution is to be claimed |
| F4 | Artifact immutability | ⏳ | Released hash == smoke-tested hash; reapproval on change | No — pin the C5-verified `smoke_writer_probe.sch` hash and gate re-release on change |
| F5 | Release status labels | ✅ | `analysis-only` / `CTSPro-reopen-verified` / `equipment-verified` in CLI/UI | No — the label enum/plumbing can be built now; only *applying* `equipment-verified` needs F1–F4 |
| F6 | Hosted CI | 🔄 **exists, green, now self-reporting** | `.github/workflows/ci.yml` runs Ruff + pytest + `tools/compare_pne_units.py` on push/PR since 2026-09-02; was red for 12 commits on the `access_parser` collection bug, fixed and pushed 2026-09-06 (`d60ea3b`, [run #33](https://github.com/Hwiho/pne_scheduler/actions/runs/34037824999) success). README now shows the workflow's own live status badge instead of a static hand-set count, so a future red run is visible on the repo front page. Remaining F6 scope: packaging checks, schema-invariant checks, doc checks on every PR | No |

**Rule:** No “equipment-ready” label until F1–F4 pass for the **exact** artifact, recipe
version, and target profile. The C5 combinatorial probe proves shared writer assembly; it does not
automatically approve a different HPPC/QPEED/QC/Cycle topology. F5's label mechanism can exist
before that — it just cannot promote an unapproved pattern.

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
│   ├── workspace_model.py       # every workspace action; no Qt and no Tk import
│   ├── document.py              # undo/redo, dirty state, autosave, crash recovery
│   ├── workspace_qt.py + qml/   # default shell (PySide6/QML), draws only
│   ├── workspace.py             # Tk shell of the same screens; fallback
│   ├── schedule_viewer.py
│   ├── project_editor.py
│   ├── resume_wizard.py
│   └── flow_editor.py           # secondary graph view under 고급 도구
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
| Mismatch between lab format and writer target | **Mitigated** | C6 framing for `0x10004/696`; full 696 schedule semantic parity not claimed |
| Automatic selection of 612 vs 696 byte step size | Partially understood | Validate version→size mapping against the 102 secured measured sch files |
| PNE raw current unit (mA vs A) | Depends on ini range | Compare Cell range profile with ASSB `unit_scale` |
| PNE voltage/L-level encoding | **Partially resolved (612)** | Ensol map: `+12` mV (not `+16`); L-level fVref heuristic only for 15–80 V range; QPEED still needs pair |
| Dual capacity models | **Writer path resolved** | Writer uses explicit `cell_capacity_mAh` (= 1C mA); viewer may still infer Q_nom |
| Internal structure of `FILE_GRADE`, `STRUCT_EIS_SET` | Only names are present in Excel | Defer 0x00010007 to Phase 4 |
| Recommended Δt/ΔV/ΔQ values | UNKNOWN in cyclediag | Reverse-extract from internal standard sch samples |
| Writer validation on physical equipment | **Closed — C5** | PNE02 2026-09-08; checklist signed |
| External ASSB parser availability | Dependency outside the repository | Make the internal parser the default source of truth and optionally cross-validate |
| Drift between fixture names and test expectations | **Confirmed** | Do not hide with skips; stabilize with manifest-based fixture lookup |
| Experimental output mistaken for production | **Mitigated, not resolved** | Default-block `build`; require manifest, reopen verification, and exact-hash release gates |
| Binary changes after parsed END ignored by diff | **Resolved** | Compare and report unparsed tails in addition to header and step records |
| Equipment profile inferred from filenames | **Prohibited** | Require explicit provenance/profile metadata and retain unknown when unavailable |
| Controlled-pair metadata is incomplete or inconsistent | Open | Add schema validation before evidence promotion (B5) |
| Resume renumbers steps without proven goto remapping | **Resolved (2026-09-06)** | `resume/splice.py::_remap_loop_goto_targets` now rewrites LOOP goto (@48 + Ensol mirror @564) to the post-splice numbering, and raises before writing if the original target falls before the resume point (unrepresentable). `io/sch_binary.patch_loop_goto` added; covered by `tests/test_resume.py::test_resume_remaps_loop_goto_target_within_resumed_range` / `test_resume_blocks_when_loop_target_would_be_dropped` |
| Documentation language/status drift | Partially resolved | README and user guide are English; audit remaining public docs and derive test status in CI |

---

## 9. Current focus (active gate)

**Active gate: E — modular schedule UX (Nova + LabVIEW feel).**
Gate C exited 2026-09-08 (C5). Gate D software exit 2026-09-08 (P0/P1 harness +
capacity contract + golden families). Pattern acceptance now runs as a linked track; the first
lab checkpoint is separate DOD@384 and `fEndC@36` controlled pairs.

| Step | Gate | Action |
|------|------|--------|
| 1 | C5 | ✅ Passed — `GATE_C_EQUIPMENT_SMOKE_CHECKLIST.md` |
| 2 | C exit | ✅ Gaps: DCR IR-only; 696 tail unused; CLI header 54-byte region |
| 3 | D | ✅ Software P0/P1 complete; see §6.5 honest gaps |
| 4 | **E foundation** | E0/E0.5: IA + composer END/LOOP + catalog + validator |
| 5 | **Pattern PV0–PV3** | Canonical HPPC/QPEED/QC/Cycle recipes + reopen candidate pack |
| 6 | **E workspace** | Setup / Procedure / Inspector / import-patch / Validate / Export |
| 7 | **User PV4** | Batch CTSPro reopen + save-as files; run은 별도 PV6 |
| 8 | F | Exact pattern hash/profile 범위로 release |

Completed: Gate A; Gate B (`gate_b_passed`); Gate C (C5 signed); Gate D (software).

Process: use §5.6 lessons checklist on every future gate claim.

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
| 2026-09-03 | C | **blocking** | C5 equipment smoke still required before executable builds | **resolved 2026-09-08** | PNE02 passed `smoke_writer_probe.sch`; see checklist |
| 2026-09-03 | C | normal | C6 original “696 semantic lab parity” stronger than delivered | **accepted waiver** | Reframed: framing + zero-tail corpus policy; see §6.4 honest assessment |
| 2026-09-03 | C | normal | C4 ASSB cross-check is thin (layout/steps/`fEndC`) | accepted | Enough as smoke; deepen only if C5 or lab diffs demand it |
| 2026-09-03 | C | normal | 696-byte tail (612–695) all-zero in secured corpus | resolved | Writer zero-pad matches corpus; `SCH_696_TAIL_ANALYSIS.md` |
| 2026-09-03 | C | normal | DCR binary offsets unresolved | accepted deferral | IR-only until controlled evidence; blocks DC-IR fidelity (Gate D), not C5 |
| 2026-08-31 | E | safety | Resume may renumber steps without goto remap proof | **resolved (2026-09-06)** | LOOP goto now remapped to post-splice numbering, or resume is blocked with a clear error when the original target would be dropped; see §8 row and `resume/splice.py` |
| 2026-09-01 | B | low | README test badge lags actual count | resolved | Badge synced to 252 passed (2026-09-06) |
| 2026-09-06 | A | normal | `tools/analyze_schedule_mdb.py` imported `access_parser` unconditionally at module scope, so its absence aborted **all** test collection (not just the skipped MDB test), contradicting the "local pytest green" claim | resolved | Import made lazy (`TYPE_CHECKING` + in-function import); `access_parser` registered as the `mdb` optional extra in `pyproject.toml` |
| 2026-08-31 | C | normal | 89/93 lab fixtures use `0x10004/696`, not 612-byte layout | mitigated | C6 framing writer exists; full schedule parity deferred |
| 2026-09-01 | B | normal | fEndV unit mismatch (fixture mV vs compiler V) | resolved | Ensol adoption; `tests/test_unit_contract.py` |
| 2026-09-01 | B/D | normal | Golden fixtures locked from user intake (7 selected, PNE02+PNE16) | done | `planning/GOLDEN_FIXTURES_LOCKED.json` |
| 2026-09-03 | E | normal | UX intent clarified: Nova + LabVIEW *feel* for modular schedule authoring (not live Autolab control) | accepted | §1.1 rewritten; Gate E retitled; E8 removed as false target |
| 2026-09-06 | C | normal | C5 required a physical reopen per field/module shape; most of that risk was already closed by existing PNE02 pairs and corpus mining but never consolidated | resolved | [`GATE_C5_EVIDENCE_COVERAGE.md`](../legacy/planning/GATE_C5_EVIDENCE_COVERAGE.md) audits every step field; `smoke_writer_probe` module/fixture combines charge+discharge+LOOP+per-step sampling into one from-scratch build so a single reopen replaces several |
| 2026-09-06 | C | normal | `build_sch_header()` (CLI `build` path) leaves 54/1760 header bytes at zero where a real lab-authored header has non-zero content (concentrated ~0x2D8-0x361, past `HOFF_NAME`'s window — plausibly the second `FILE_TEST_INFORMATION` name/description block from §2.3) | open, no action needed yet | Not packed — no controlled-pair/corpus evidence for their meaning (L3). `tools/rebuild_smoke_sch_from_lab_header.py` sidesteps this by cloning a real header instead of using `build_sch_header()`; a clean C5 on `smoke_writer_probe.sch` does **not** clear this for the plain CLI `build` path specifically. Revisit only if `build_sch_header()`'s output needs to go to equipment directly |
| 2026-09-06 | D | normal | `dcir`/`hppc`/`rpt`/`qpeed` modules SOC-target via `end_capacity_fraction`, which packs `fEndC`@36 -- a field `schema/fields.py` marks `semantic_unverified` with **no nonzero example in the corpus** (weaker evidence than DCR, which at least gets a warning). `compile_step_warnings()` already warns for DCR and `goto_step_id` but silently skipped this one | resolved | Added the missing warning in `engine/compiler.py::compile_step_warnings`; also fixed `io/writer.py::write_sch` discarding `compile_step_warnings()`'s result (`_ = ...`) instead of returning it, so the CLI `build` path had **zero** visibility into any of these warnings even though the compiler always computed them. `build` now prints `WARN:` lines and the manifest's `warnings` include them |
| 2026-09-06 | D | normal | `modules/insitu_cycle.py::expand()` checked `steps[0].label is None` to decide whether to relabel the inherited cycle marker, but `StepIntent.label` defaults to `""` (never `None`) and `CycleLifeModule` always sets a real label -- the condition could never be true, so in-situ projects always kept the generic "cycle marker" label instead of "in-situ cycle marker (no RPT)" | resolved | Condition changed to `steps[0].step_type == "cycle"`; `tests/test_insitu_cycle.py` added |
| 2026-09-06 | E | normal | `edit/bulk_edit.py::coerce_param_for_field` compared a dataclass field's `.type` against the real `int`/`float`/`str`/`bool` type objects, but every module uses `from __future__ import annotations`, which makes `.type` the annotation **string** (e.g. `"int"`) -- the comparison never matched, so `target_type` was always `None` and coercion fell back to guessing from string content alone. Concretely, bulk-editing an `int` field with a negative value (e.g. `loop_count=-5`) silently stored the **float** `-5.0` instead of the int `-5` (`"-5".isdigit()` is `False`) | resolved | Resolve by annotation name via a small `int`/`float`/`str`/`bool` lookup instead of identity comparison; `tests/test_bulk_edit.py::test_coerce_param_for_field_keeps_int_fields_as_int` added |
| 2026-09-06 | B | **blocking (evidence integrity)** | `validate/intake.py::validate_intake_with_compare_report` recorded an `expected_field` vs. actual-changed-field mismatch as a **warning**, not an error. `IntakeValidationResult.valid = not errors` ignores warnings, so `tools/run_gate_b_validation.py`'s `_controlled_pair_evidence()` (`pair_clean = combined.valid`) could mark a pair `evidence_complete` and register the **wrong** offset under `covered[equipment]` even when the observed byte change landed on a different field entirely -- defeating the controlled-pair evidence tier the whole B5 gate exists to enforce | resolved | Changed to `errors.append(...)`; re-ran `run_gate_b_validation` and confirmed `gate_b_passed=true` still holds (all 9 real PNE02 pairs already had a correctly-matching `expected_field`, so nothing was actually promoted on bad evidence -- this closes the loophole for future pairs). `tests/test_validation_intake.py::test_intake_with_compare_report_rejects_wrong_expected_field` added |
| 2026-09-06 | analysis | normal | `stack/levels.py::_L_EXPLICIT` regex (`L[\s._-]*(\d...)`) had no token boundary before `L`, so it matched an `L`/`l` preceded by *any* other letter -- e.g. "Cell01" → spurious `l0`, "Model3350" → spurious `l3`. Confirmed on the real 102-file corpus: `set3_bimodal-30_45도 0.5C cycle.sch` and `bimodal_0.5C cycle.sch` both got a wrong filename-based L-level guess from the trailing "l" in "bimodal". It could also let a false match earlier in the name shadow a real explicit L-level later in the same name (`re.search` returns the leftmost match) | resolved | Added a negative lookbehind (`(?<![A-Za-z])L...`) requiring the character before `L` not be a letter. Viewer/analysis-only per L7 (writer path never uses filename inference), so this never affected binary output -- only the viewer's displayed L-level/C-rate guess. `tests/test_stack_levels.py` parametrized regression tests added |
| 2026-09-06 | F | **resolved (process integrity)** | `.github/workflows/ci.yml` had existed and been active since 2026-09-02 (commit `be373a8`), but ROADMAP.md §6.1/§6.7 claimed hosted CI was "not started" -- meanwhile the workflow had actually been **failing for 12 consecutive commits** (`0aa9b6f` through `64dddd8`, all of Gate C's work) on the `access_parser` collection bug. Neither the failure nor the workflow's existence was ever reflected in ROADMAP.md | resolved | Fix pushed as commit `d60ea3b`; [run #33](https://github.com/Hwiho/pne_scheduler/actions/runs/34037824999) completed **success** (Ruff, Pytest, corpus-smoke all green) -- hosted CI restored after 12 consecutive red runs. Remaining optional follow-up: replace the static hand-set shields.io test badge in README with a real Actions status badge so silent red CI can't recur unnoticed (not done yet, low priority) |
| 2026-09-06 | E | normal | 6 unmerged `cursor/*` remote branches discovered (abandoned Cursor Cloud agent runs, diverged up to 53 commits from master) | open — needs human review | 3 touch UI (`cursor/update-roadmap-5ac9` theming/wiring, `cursor/module-recipes-presets-5ac9` recipe editing, `cursor/explain-schedules-5ac9` schedule explanation) — patterns extracted to `UI_UX_NOTES.md`, too stale to merge wholesale. 3 touch Gate B/C validation tooling (`cursor/create-gate-b-baseline-dfb2`, `cursor/gate-c-safety-manifest-eccb`, `cursor/mine-internal-dataset-dfb2`) — not reviewed in depth, may contain unmerged evidence/tooling work worth checking before deleting the branches |
| 2026-09-08 | C | **blocking→fixing** | CTS “공통 안전조건 용량” offset mis-mapped; PNE16 vs PNE02 UI units/slots differ | **resolved** | Cap at `0x3D8+12` / `0x458+12`; PNE02 C5 showed **800 mAh** |
| 2026-09-08 | D | normal | OCV/Impedance/Pattern/Balance have CTS UI types but **zero** corpus samples | open (stubs) | Type codes in `SCH_STEP_TYPES`; shared prefix packing + warnings; [`STEP_TYPES_EXTENDED.md`](STEP_TYPES_EXTENDED.md) — need lab controlled pairs |
| 2026-09-08 | D | normal | Gate D module expands are templates, not full lab schedule clones | accepted | Family topology tests + harness E2E; byte-faithful module cloning deferred |
| 2026-09-08 | D | **blocking (verification integrity)** | Gate D mutation backtest: `_check_v6_families()` read only the static golden fixture and never the module's expansion, so every `family_*` check passed even when modules were broken to emit a single `rest` step. The method doc claimed the module comparison the code never did (L4) | resolved | V6 now compares required families against **both** golden and live module expansion (`module_ref` rows in `GATE_D_FAMILY_CHECKS`); `tests/test_gate_d_verification_sensitivity.py` pins the sensitivity |
| 2026-09-08 | D | **blocking (verification integrity)** | `gate_d_passed` was `all(status != "fail")`, so skips did not block it — deleting every golden fixture still produced `gate_d_passed=true` with **zero** golden comparisons executed (L4) | resolved | Skips now block the exit claim and V8 names the checks that never ran; report still distinguishes skip from mismatch |
| 2026-09-08 | C | normal | Header safety-block layout is PNE02-specific (capacity `0x3D8+12`/`0x458+12`; PNE16 reads `+16` as 최소 전류) but `build_sch_header()` takes no unit and the build manifest recorded `equipment: null` — the conflict lived only in source comments (L1: document conflicts, don't silently pick one) | resolved | `SAFETY_BLOCK_CONVENTION` exported from `io/header.py`; build manifest now records `target_profile.safety_block_convention` and carries the PNE02-only caveat in `warnings`. No PNE16 offsets invented (L3) |
| 2026-09-08 | D/PV1 | normal→pattern-blocking | C5에서 `dod_percent`@384(프로브 40%)가 **CTSEditorPro UI에 표시되지 않음**("확인 못함"). 현재 HPPC full/QPEED는 이 DOD 경로를, dcir/hppc:legacy/rpt는 별도 `fEndC`@36 경로를 사용하므로 한 번의 확인으로 두 의미를 함께 승인할 수 없음 | open, timing assigned | Pattern acceptance 첫 lab checkpoint에서 두 value-only controlled pair 수행: **A)** DOD/SOC percent `30→40%`로 @384 확인, **B)** capacity cutoff `24→32 mAh`(80 mAh 기준; 또는 UI percent 30→40)로 `fEndC`@36과 단위 확인. off/on은 enable/cap-ref flag용 보조 pair. 그 전까지 각각 `corpus_inferred`/`semantic_unverified`, 관련 SOC-dependent pattern의 reopen 승격 금지. [`PATTERN_VALIDATION_PLAN.md`](PATTERN_VALIDATION_PLAN.md) §4 |
| 2026-09-08 | E | high | 모듈 합성 계약 부재: 일부 모듈이 자체 END를 내보내고 LOOP target을 모듈-local raw 번호로 저장해, 여러 모듈 연결 시 non-final END나 잘못된 goto가 생길 수 있음. `qpeed:soc_setting` LOOP는 target/count도 없음 | resolved 2026-09-09 | Composer가 단일 최종 END 소유; fragment-local reference와 legacy local target을 절대 step으로 resolve; invalid LOOP 차단; 다중 loop-module 회귀 추가. [`GATE_E_PLAN.md`](GATE_E_PLAN.md) §3.1/§5 |
| 2026-09-08 | D/E | high | Gate D family-level green과 실제 protocol-pattern 충실도가 분리되지 않음: QPEED full은 짧은 HPPC 상속 구현이었고 golden은 167 step, HPPC golden은 62 step, QC module은 없었음 | partial 2026-09-09 | HPPC 62-step, QPEED 167/11-step 및 QC 3종 구현, trust catalog/preflight와 10-pattern reopen pack 생성 완료. 기존 family-template exact recipe와 PV1/PV4는 open. [`PATTERN_VALIDATION_PLAN.md`](PATTERN_VALIDATION_PLAN.md) |
| | | | *(add new rows here)* | | |
