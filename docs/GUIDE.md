# pne_scheduler User Guide

Tools for reading, analyzing, editing, and resuming PNE cycler `.sch` schedules.

> [!WARNING]
> The from-scratch writer is experimental and does not produce equipment-ready files.
> Prefer read-only analysis and template-preserving operations until the writer passes
> CTSPro reopen and equipment smoke tests.

## Installation

```powershell
git clone https://github.com/Hwiho/pne_scheduler.git
cd pne_scheduler
pip install -e ".[dev]"
```

## CLI

| Command | Description |
|------|------|
| `python -m pne_scheduler view [file.sch]` | Open the schedule viewer |
| `python -m pne_scheduler edit [file.schproj]` | Open the project bulk editor |
| `python -m pne_scheduler flow [file.schproj]` | Open the module connection editor |
| `python -m pne_scheduler info file.schproj` | Show a project summary |
| `python -m pne_scheduler compare before.sch after.sch` | Compare a controlled SCH pair |
| `python -m pne_scheduler patch-sch template.sch plan.json -o out.sch` | Apply an evidence-gated, template-preserving patch |
| `python -m pne_scheduler build ... --allow-experimental-output` | Produce offline-only experimental output |
| `python -m pne_scheduler bulk-edit ...` | Edit compatible module parameters in bulk |
| `python -m pne_scheduler resume sch data.csv -o resumed.sch` | Build a resume schedule |

## Launcher scripts

```powershell
python run_pne_scheduler_viewer.py
python run_pne_scheduler_editor.py
python run_pne_scheduler_flow.py
python run_pne_scheduler_resume.py
```

## Template-preserving writer

1. Start from the exact CTSPro-authored SCH file to preserve.
2. Obtain its SHA-256 from a `compare` report.
3. Copy `example/sch-patch.template.json` and set the hash, expected version, step number,
   field, and raw value.
4. Run `patch-sch ... --allow-analysis-output`.
5. Review the generated `.report.json`.

The default path rejects fields that are not marked writer-ready. At present, semantic
fields still require controlled CTSPro evidence, so `--allow-unverified-fields` is strictly
for offline reverse-engineering. Every write separately requires `--allow-analysis-output`.
Neither acknowledgement makes a file safe to execute.

## Module flow editor

The flow editor provides a module palette, a visual canvas, linear connection validation,
module and Cell Profile JSON editors, `.schproj` load/save, and a step-intent preview.
Multiple inputs, multiple outputs, self-connections, and cycles are rejected because the
current execution model is a linear schedule.

## Cell interpretation pipeline

```
filename → FP (loading) → mono/multi → L-level → Q_nom → C-rate
```

| Item | Rule |
|------|------|
| **FP** | `1818`, `3350`, `70150`, `70295`, `101295` loading geometry |
| **Si composition** | `6040`, `6535`, `7030`; these are not FP values |
| **L-level** | Explicit filename values such as `L5.0` and `L.4.36`; omitted mono value defaults to **L5.0** |
| **Stack** | `8M1U`, `8M2U` → **K = M × U** double-sided electrode count |

## Default protocol C-rates

| Experiment | C-rate |
|------|--------|
| FM (formation) | 0.1C |
| Capacheck / derating | 0.1C → C/3, sometimes two C/3 cycles |
| Cycle / in-situ | 0.5C |
| RPT | C/3 discharge + DC-IR at SOC 80/50/20 (1.0–1.5C) |
| QPEED / QC | >2.5C |

See [PROTOCOL.md](PROTOCOL.md) and [RESUME.md](RESUME.md).

## Example data

- `example/fixtures/capacheck_zip/` — 8 capacheck/QPEED/RPT fixtures
- `example/fixtures/sch_lab_zip/` — 93 lab SCH fixtures
- `example/fixtures/hppc/` — 1 HPPC fixture
- `example/analysis/` — generated analysis reports

## Tests

```powershell
python -m pytest tests/ -q
```
