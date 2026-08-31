# pne_scheduler

Python tools for reading, analyzing, editing, and resuming PNE cycler `.sch` schedules.
The package also supports ASSB lab protocol classification (FM, capacheck, cycle, RPT,
QPEED, and others) and cell-geometry inference (FP, L-level, and xMyU).

[![Tests](https://img.shields.io/badge/tests-86%20passed-brightgreen)](#tests)

> [!WARNING]
> The from-scratch SCH writer still uses a placeholder header. Its output is not validated
> for CTSPro or equipment execution. Reading, comparison, and template-preserving resume
> operations are further along than new-file generation.

## Installation

```powershell
git clone https://github.com/Hwiho/pne_scheduler.git
cd pne_scheduler
pip install -e ".[dev]"
```

## Quick start

```powershell
# Schedule viewer
python run_pne_scheduler_viewer.py

# Project bulk editor
python run_pne_scheduler_editor.py

# Interrupted-experiment resume tool
python run_pne_scheduler_resume.py

# CLI
python run_pne_scheduler.py info example/example.schproj
python run_pne_scheduler.py view path\to\file.sch
python -m pne_scheduler compare before.sch after.sch -o comparison.json

# Offline writer development only; never execute this output on equipment
python run_pne_scheduler.py build example/example.schproj -o output.sch --allow-experimental-output
```

## CLI summary

| Command | Description |
|------|------|
| `view [file.sch]` | Show the step table and inferred FP/L/C-rate/protocol |
| `edit [file.schproj]` | Open the project bulk editor |
| `info file.schproj` | Show a project summary |
| `compare before.sch after.sch` | Generate a controlled binary-difference report |
| `build ... --allow-experimental-output` | Produce offline-only experimental writer output |
| `bulk-edit ...` | Edit compatible module parameters in bulk |
| `resume sch data.csv -o resumed.sch` | Build a template-preserving resume schedule |

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

See [docs/RESUME.md](docs/RESUME.md) for details.

## Lab protocol defaults

| Experiment | Default C-rate | Notes |
|------|-------------|------|
| **FM (formation)** | 0.1C | Charge and discharge |
| **Capacheck / derating** | 0.1C → C/3 | Sometimes two C/3 cycles |
| **Cycle** | 0.5C | Generation and interpretation default |
| **In-situ cycle** | 0.5C | No RPT block |
| **RPT** | C/3 discharge | DC-IR at SOC 80/50/20, 1.0–1.5C |

See [docs/PROTOCOL.md](docs/PROTOCOL.md) for details.

## Package structure

```
pne_scheduler/
├── schema/          # SCH binary fields and enums
├── ir/              # Schedule IR (.schproj)
├── engine/          # C-rate engine and compiler
├── modules/         # Formation, cycle life, RPT, DC-IR, QPEED, and others
├── protocol/        # Lab protocol defaults and inference
├── stack/           # FP, L-level, xMyU, and capacity inference
├── classify/        # Filename classification
├── edit/            # Bulk module editing
├── resume/          # Interrupted-experiment resume and splicing
├── io/              # reader / writer
├── ui/              # Viewer, editor, and resume wizard
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

## Documentation

- [User guide](docs/GUIDE.md)
- [Protocol and C-rate](docs/PROTOCOL.md)
- [Interrupted-experiment resume](docs/RESUME.md)
- [SCH validation intake](docs/SCH_VALIDATION_INTAKE.md)
- [Roadmap](planning/ROADMAP.md)

## Related repository

This package was split from the
[pne-studio](https://github.com/Hwiho/pne-studio) monorepo.
