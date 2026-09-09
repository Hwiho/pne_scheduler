# pne_scheduler

Python tools for reading, analyzing, editing, and resuming PNE cycler `.sch` schedules.
The package also supports ASSB lab protocol classification (FM, capacheck, cycle, RPT,
QPEED, and others) and cell-geometry inference (FP, L-level, and xMyU).

[![CI](https://github.com/Hwiho/pne_scheduler/actions/workflows/ci.yml/badge.svg)](https://github.com/Hwiho/pne_scheduler/actions/workflows/ci.yml)

> [!WARNING]
> The from-scratch SCH writer now emits a full `0x00010003`/1760-byte header, but
> step semantics and equipment smoke tests are still incomplete. Output is not
> validated for CTSPro or equipment execution. Prefer `patch-sch` for evidence-gated edits.

## Installation

```powershell
git clone https://github.com/Hwiho/pne_scheduler.git
cd pne_scheduler
pip install -e ".[dev]"
```

## Quick start

```powershell
# Unified workspace (start here)
python run_pne_scheduler_workspace.py
python -m pne_scheduler workspace example/example.schproj

# Schedule viewer
python run_pne_scheduler_viewer.py

# Project bulk editor
python run_pne_scheduler_editor.py

# Module connection flow editor
python run_pne_scheduler_flow.py

# Interrupted-experiment resume tool
python run_pne_scheduler_resume.py

# CLI
python run_pne_scheduler.py info example/example.schproj
python run_pne_scheduler.py view path\to\file.sch
python -m pne_scheduler compare before.sch after.sch -o comparison.json
python -m pne_scheduler flow example/example.schproj

# Offline writer development only; also writes output.sch.manifest.json
python run_pne_scheduler.py build example/example.schproj -o output.sch --allow-experimental-output
```

## CLI summary

| Command | Description |
|------|------|
| `workspace [file.schproj]` | Open the unified workspace (setup → protocol → procedure → validate → export) |
| `summary file.schproj` | Print a Korean plain-language summary and the export gate status |
| `view [file.sch]` | Show the step table and inferred FP/L/C-rate/protocol |
| `edit [file.schproj]` | Open the project bulk editor |
| `flow [file.schproj]` | Arrange, connect, validate, and preview experiment modules |
| `info file.schproj` | Show a project summary |
| `compare before.sch after.sch` | Generate a controlled binary-difference report |
| `patch-sch template.sch plan.json -o out.sch` | Write a byte-preserving, analysis-only template clone |
| `build ... --allow-experimental-output` | Produce offline-only experimental writer output |
| `bulk-edit ...` | Edit compatible module parameters in bulk |
| `resume sch data.csv -o resumed.sch` | Build a template-preserving resume schedule |
| `pattern-review-pack DIR` | Generate PNE02 reopen-only candidates, expectations, hashes, and review sheet |

The committed batch at
[`example/pattern_review_pack/2026-09-09/INDEX.md`](example/pattern_review_pack/2026-09-09/INDEX.md)
contains QPEED, QC, HPPC, Cycle, Formation, capacheck, and RPT candidates. These files are
for CTSPro display/Save-As review only and must not be started or run.

## Workspace

```powershell
# 1) API — lab PC, localhost only
python run_pne_scheduler_api.py

# 2) screens
cd web
npm install
npm run dev            # http://localhost:3000
```

One page with five steps, in the order the work actually happens:

| Tab | What it is for |
|------|------|
| **1. 설정** | PNE unit, CTSPro build, SCH layout, cell capacity and voltage window |
| **2. 프로토콜** | Pick an experiment by purpose, build a cycle+RPT campaign, edit as a structured form |
| **3. 절차** | The run order, a deadline solver, per-step editing of detached modules |
| **4. 검증** | Errors, warnings, and unverified evidence |
| **5. 내보내기** | The draft → software-checked → CTSPro → equipment ladder, each path gated separately |

Design rules the workspace follows:

- **Saving is never blocked.** A project with errors still opens and still saves; only
  export is gated. A file with bad values is repaired on load and every repair is listed.
- **The screens hold no rules.** Every gate is computed by `release.py` and arrives as
  data with its blockers attached; nothing in the browser recomputes one.
- **No JSON in the form.** Every parameter is declared once in `spec/module_params.py`
  with a Korean name, a unit, allowed and recommended ranges, the reason for its default,
  which steps it moves, and how far it has been verified — and the form renders from that.
- **C-rate and current are the same value.** Type either; the other is shown next to it.
- **Changes are previewed.** A plan is a separate request from applying it, so the
  warnings that must be read first arrive before anything is committed.
- **Presets stay presets.** To edit an individual step of a locked pattern, detach it
  explicitly; the module then carries its steps verbatim and is marked user-edited.
- **One answer, not twelve entries.** A cycle campaign is described as a rhythm and laid
  out as ordinary modules; cycle counts can be solved backwards from a deadline.

The desktop Tk and Qt workspaces were removed in Gate G4 — see
[`planning/WEB_PORT_PLAN.md`](planning/WEB_PORT_PLAN.md). The other tools (viewer, flow
canvas, bulk editor, resume wizard) remain Tk.

## Equipment profile

`.schproj` is now `pne_scheduler.schproj/v2` and carries the target cycler:

```json
"equipment": {
  "unit": "PNE02",
  "max_current_mA": 500.0,
  "ctspro_build": "CYCC-1004-S01-R004-N01",
  "sch_file_version": "0x00010003",
  "sch_step_size": 612,
  "layout_confirmed": true
}
```

v1 files load unchanged and are migrated on save; the loader reports that the equipment
profile is missing so the gap is visible rather than assumed. The binding current limit is
the smaller of the cell limit and the unit rating, and preflight enforces it — naming an
under-rated unit is now an error, not a surprise at export time.

## Export gates

| Output | Requires |
|------|------|
| 초안 저장 (`.schproj`) | nothing — always available |
| 미리보기 (steps.csv, summary.txt) | software preflight passes |
| CTSPro 검토용 SCH | preflight passes + a complete PNE02/0x00010003 profile |
| 템플릿 패치 | preflight passes + a CTSPro-authored template and its hash |
| 장비 실행용 | production preflight + recorded CTSPro review + recorded equipment approval |

## Schedule viewer

```powershell
python run_pne_scheduler_viewer.py
# or
python -m pne_scheduler view path\to\file.sch
```

The viewer displays the step table together with inferred **L-level**, **footprint
(FP)**, **mono/multi**, **C-rate**, and **protocol**.

### Inference pipeline

```
filename → FP (1818, 3350, …) → mono/multi (default: mono) → L-level → Q_nom → C-rate
```

| Item | Rule |
|------|------|
| **FP** | `1818`, `3350`, `70150`, `70295`, `101295` loading geometry |
| **Si composition** | `6040`, `6535`, `7030`; these are not FP values |
| **L-level** | `L5.0`, `L.4.36`, and similar; omitted mono value defaults to **L5.0** |
| **multi** | `8M1U`, `8M2U` → **K = M × U** double-sided electrode count |
| **C-rate** | `I / Q_nom`, `Q_nom = 21600 mAh × (area/16.5) × (L/4.3) × K` |

## Bulk edit (modules)

```powershell
# GUI
python run_pne_scheduler_editor.py

# Set all cycle_life modules to 0.5C
python -m pne_scheduler bulk-edit example/example.schproj --type cycle_life --set charge_c_rate=0.5

# Select module IDs
python -m pne_scheduler bulk-edit proj.schproj --ids cyc1,cyc2 --set loop_count=300

# All modules with compatible keys
python -m pne_scheduler bulk-edit proj.schproj --all --set rest_s=600
```

Values may be C-rate strings such as `C/3`, floats, integers, or JSON lists such as
`[0.8,0.5,0.2]`.

## Template-preserving SCH writer

The limited writer applies typed field patches to an exact CTSPro-authored template. It
requires the template SHA-256, preserves the header, file length, step topology, and every
byte outside declared field ranges, then emits `<output>.manifest.json`. The validation
manifest records the target profile, template and output hashes, changed fields, field
evidence, preservation checks, and equipment-test status.

```powershell
python -m pne_scheduler compare template.sch template.sch
# Copy example/sch-patch.template.json and insert the reported SHA-256.

python -m pne_scheduler patch-sch template.sch patch.json -o patched.sch `
  --allow-analysis-output
```

Gate B promoted these fields to writer-ready (controlled-pair + CTSEditorPro reopen):
`fVref`, `fIref`, `fEndV`, `fEndI`, `loop_target`, `loop_count`, `record_time_s`.
`--allow-unverified-fields` is still required for any other field, offline research only.
The separate `--allow-analysis-output` acknowledgement is required for every write,
and the command always prints an equipment warning. If the manifest cannot be written, the
CLI removes the SCH output so an untracked artifact is not left behind.

## Module flow editor

```powershell
python run_pne_scheduler_flow.py
# or
python -m pne_scheduler flow example/example.schproj
```

The first GUI version supports adding/removing modules, explicit connections, automatic
linear chaining, JSON property editing, Cell Profile editing, graph validation, `.schproj`
load/save, and expanded step preview. It intentionally does not send files to equipment.

## Resume interrupted experiment

The resume workflow combines an original `.sch` file with StepEnd/raw CSV data to locate
the interruption point and create a continuation schedule.

```powershell
python run_pne_scheduler_resume.py

python -m pne_scheduler resume original.sch channel_StepEnd.csv -o resumed.sch --plan-only
python -m pne_scheduler resume original.sch channel_StepEnd.csv -o resumed.sch
python -m pne_scheduler resume original.sch channel_StepEnd.csv -o resumed.sch --step 12 --loops 150
```

- The final StepEnd row determines the last completed CTS step (`SCH step = CTS - 1`).
- `* Complete` resumes from the next SCH step.
- A mid-step interruption resumes from the same SCH step.
- LOOP schedules estimate remaining loops; `--loops` overrides the estimate.

See [docs/README.md](docs/README.md) for resume, protocol, and CLI details.

## Lab protocol defaults

| Experiment | Default C-rate | Notes |
|------|-------------|------|
| **FM (formation)** | 0.1C | Charge and discharge |
| **Capacheck / derating** | 0.1C → C/3 | Sometimes two C/3 cycles |
| **Cycle** | 0.5C | Generation and interpretation default |
| **In-situ cycle** | 0.5C | No RPT block |
| **RPT** | C/3 discharge | DC-IR at SOC 80/50/20, 1.0–1.5C |

See [docs/README.md](docs/README.md) for protocol defaults and module rules.

## Package structure

```
pne_scheduler/
├── schema/          # SCH binary fields and enums
├── ir/              # Schedule IR (.schproj)
├── engine/          # C-rate engine and compiler
├── modules/         # Formation, cycle life, RPT, DC-IR, QPEED, and others
├── protocol/        # Lab protocol defaults, inference, experiment-goal catalog
├── spec/            # ParameterSpec, units, structured form model
├── report/          # Plain-language Korean summaries
├── stack/           # FP, L-level, xMyU, and capacity inference
├── classify/        # Filename classification
├── edit/            # Bulk module editing
├── resume/          # Interrupted-experiment resume and splicing
├── io/              # reader / writer
├── ui/              # Workspace, document controller, viewer, editors, resume wizard
├── tools/           # Batch analysis CLI tools
├── example/         # Fixtures and analysis reports
├── docs/            # User and validation guides
└── tests/
```

## Example data

- `example/fixtures/capacheck_zip/` — 8 capacheck/QPEED/RPT fixtures
- `example/fixtures/sch_lab_zip/` — 93 lab SCH fixtures
- `example/fixtures/hppc/` — 1 HPPC fixture
- `example/analysis/` — batch analysis JSON reports

## Tests

```powershell
python -m pytest tests/ -q
```

## Lint

```powershell
ruff check .
```

Minimal ruleset (unused/undefined names, a few pycodestyle basics) — see
`[tool.ruff]` in `pyproject.toml`. Runs in CI before the test suite.

## Documentation

- [User guide](docs/README.md) — CLI, protocol, resume
- [Gate B validation](docs/GATE_B.md)
- [Planning index](planning/README.md)
- [Roadmap](planning/ROADMAP.md)

## Related repository

This package was split from the
[pne-studio](https://github.com/Hwiho/pne-studio) monorepo.
