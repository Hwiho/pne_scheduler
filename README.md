# pne_scheduler

Python tools for reading, analyzing, editing, and resuming PNE cycler `.sch` schedules.
The package also supports ASSB lab protocol classification (FM, capacheck, cycle, RPT,
QPEED, and others) and cell-geometry inference (FP, L-level, and xMyU).

[![Tests](https://img.shields.io/badge/tests-131%20passed-brightgreen)](#tests)

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

# Module connection flow editor
python run_pne_scheduler_flow.py

# Interrupted-experiment resume tool
python run_pne_scheduler_resume.py

# CLI
python run_pne_scheduler.py info example/example.schproj
python run_pne_scheduler.py view path\to\file.sch
python -m pne_scheduler compare before.sch after.sch -o comparison.json
python -m pne_scheduler explain path\to\file.sch
python -m pne_scheduler flow example/example.schproj

# Offline writer development only; never execute this output on equipment
python run_pne_scheduler.py build example/example.schproj -o output.sch --allow-experimental-output
```

## CLI summary

| Command | Description |
|------|------|
| `view [file.sch]` | Show the step table and inferred FP/L/C-rate/protocol |
| `explain file.sch` | Narrate what the schedule does (SOC hints, voltage setpoints, repeating blocks) |
| `edit [file.schproj]` | Open the project bulk editor |
| `flow [file.schproj]` | Arrange, connect, validate, and preview experiment modules |
| `info file.schproj` | Show a project summary |
| `compare before.sch after.sch` | Generate a controlled binary-difference report |
| `patch-sch template.sch plan.json -o out.sch` | Write a byte-preserving, analysis-only template clone |
| `overview file.schproj` | Summarize composed module recipes (what the pattern does) |
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
(FP)**, **mono/multi**, **C-rate**, **protocol**, and a narrative of **what the
schedule does**.

## Schedule explanation

```powershell
python -m pne_scheduler explain example\fixtures\hppc\HPPC_Full range.sch
python -m pne_scheduler explain example\fixtures\capacheck_zip\07100766_260617_Set2_bimodal-SJ1300-40um_80C_QPEED-2.sch --json
```

The explainer is a **read/analyze** helper. It does not make a schedule writer-ready.
SOC percentages are **not stored** in the current corpus (`fEndC` and `fSocRate` are
unused), so the tool reports:

| Source | What you get | Example |
|--------|----------------|---------|
| Filename | `SOC50`, `SOC30` | `RPT_SOC50 End…sch` → SOC 50% (filename only) |
| Voltage setpoints | Mid-window `fEndV` as an SOC stand-in | QPEED full charges to **3.318 V ×13**, then high-C to 4.2 V |
| Voltage limits | Typical 2.5 V / 4.2 V empty/full | HPPC full-range fixture |
| Module defaults | Generator templates only | HPPC 90/50/10 and RPT 80/50/20 are **not** read from these binaries |

Checked-in fixtures:

- **HPPC_Full range.sch** — full 2.5–4.2 V cycling plus 30 mA residual steps, **not** an SOC 90/50/10 pulse staircase.
- **QPEED-2.sch** — 1C condition, charge to 3.318 V (SOC stand-in, percent unknown), then ~1.5C to 4.2 V, repeated.
- **QPEED_SOC_setting…sch** — short conditioning block; filename is a sub-protocol name, not a percent.
- **RPT_SOC50…sch** — filename SOC 50%; binary has no 80/50/20 capacity ladder.

Every explanation is labeled inferred and repeats the equipment-safety caveat.

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
byte outside declared field ranges, then emits a JSON provenance report.

```powershell
python -m pne_scheduler compare template.sch template.sch
# Copy example/sch-patch.template.json and insert the reported SHA-256.

python -m pne_scheduler patch-sch template.sch patch.json -o patched.sch `
  --allow-analysis-output
```

No current semantic field is marked writer-ready because controlled CTSPro reopen evidence
has not been supplied. `--allow-unverified-fields` enables unresolved fields only for offline
research. The separate `--allow-analysis-output` acknowledgement is required for every write,
and the command always prints an equipment warning.

## Module flow editor

The flow editor shows **charge / discharge / rest units inside each module**.
QPEED, HPPC, formation, cycle life, and sequence modules ship with named
**presets**; pick one, then edit the units directly (or rebuild from the preset
and knobs). After the pattern is assembled, the **Overview** tab (and
`python -m pne_scheduler overview file.schproj`) summarizes what you composed.
**Export .sch…** writes an experimental file and reloads it in the in-repo
viewer parser; it is still not equipment-ready.

Default QPEED preset `qpeed.full_3318` matches the checked-in QPEED-2 topology:
1C condition to **3.318 V**, then 1.5C to 4.2 V, repeated. `qpeed.soc_fraction`
and `hppc.soc_90_50_10` are generator templates, not fixture matches.

```powershell
python run_pne_scheduler_flow.py
# or
python -m pne_scheduler flow example/qpeed.schproj
python -m pne_scheduler overview example/qpeed.schproj
python -m pne_scheduler flow example/example.schproj
```

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
├── modules/         # Formation, cycle life, RPT, DC-IR, QPEED, recipes, presets
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

- `example/example.schproj` — formation + cycle-life project
- `example/qpeed.schproj` — QPEED full 3.318 V preset (editable recipe)
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
