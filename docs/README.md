# pne_scheduler documentation

User guide, protocol rules, and resume workflow in one place.

> [!WARNING]
> The from-scratch writer is experimental and does not produce equipment-ready files.
> Prefer read-only analysis and template-preserving operations until the writer passes
> CTSPro reopen and equipment smoke tests.

---

## Installation

```powershell
git clone https://github.com/Hwiho/pne_scheduler.git
cd pne_scheduler
pip install -e ".[dev]"
```

## CLI

| Command | Description |
|------|------|
| `python -m pne_scheduler workspace [file.schproj]` | Open the unified workspace |
| `python -m pne_scheduler summary file.schproj` | Print a Korean summary and export gate status |
| `python -m pne_scheduler view [file.sch]` | Open the schedule viewer |
| `python -m pne_scheduler edit [file.schproj]` | Open the project bulk editor |
| `python -m pne_scheduler flow [file.schproj]` | Open the module connection editor |
| `python -m pne_scheduler info file.schproj` | Show a project summary |
| `python -m pne_scheduler compare before.sch after.sch` | Compare a controlled SCH pair |
| `python -m pne_scheduler patch-sch template.sch plan.json -o out.sch` | Apply an evidence-gated, template-preserving patch |
| `python -m pne_scheduler build ... --allow-experimental-output` | Produce offline-only experimental output |
| `python -m pne_scheduler bulk-edit ...` | Edit compatible module parameters in bulk |
| `python -m pne_scheduler pattern-review-pack DIR` | Generate deterministic PNE02 reopen-only pattern review files |
| `python -m pne_scheduler resume sch data.csv -o resumed.sch` | Build a resume schedule |

## Launcher scripts

```powershell
python run_pne_scheduler_workspace.py
python run_pne_scheduler_viewer.py
python run_pne_scheduler_editor.py
python run_pne_scheduler_flow.py
python run_pne_scheduler_resume.py
```

## Workspace and the input contract

The workspace is the primary entry point. It has two drawing layers over one shared brain:

- `ui/workspace_qt.py` + `ui/qml/` — the default, a PySide6/QML shell whose bridge only
  converts model state into the lists and maps QML understands.
- `ui/workspace.py` — a reduced Tk build, used where PySide6 is not installed.
  `ui/__init__.py:launch_workspace()` picks between them. It carries the original five
  screens only: the campaign builder, QC fast-charge control, deadline solver, C-rate chips
  and step editor were added to the Qt shell and deliberately not back-ported, since the Tk
  workspace is scheduled for removal when the web UI lands.

Neither holds any decision. Both drive two testable pieces:

- `ui/workspace_model.py` — every action the UI can perform, with no Qt and no Tk import,
  so the behaviour is covered by `tests/test_workspace_model.py` rather than by clicking.
- `ui/document.py` — the editing session: snapshot undo/redo with named entries, dirty
  tracking, atomic autosave to `~/.pne_scheduler/recovery`, and crash recovery.

`tests/test_workspace_qt.py` builds the real QML engine offscreen and fails on any QML
warning, so a renamed bridge property cannot reach a user as a blank panel. It skips where
PySide6 is absent, as `tests/test_workspace_ui.py` skips without a display.

### ParameterSpec

`spec/module_params.py` declares every editable parameter of every user-visible module:

| Field | Meaning |
|------|------|
| `label` / `label_en` | Korean display name and the internal key |
| `kind` | `c_rate`, `voltage_v`, `duration_s`, `percent`, `count`, `choice`, list variants |
| `minimum` / `maximum` | Hard allowed range (an error outside it) |
| `recommended_min` / `recommended_max` | Soft range (a warning outside it) |
| `visible_when` | Sibling-value condition, e.g. only shown for `variant == "full"` |
| `help` / `basis` | What it does, and where the default value comes from |
| `affects` | Which steps move when it changes |
| `risk` | `normal` / `caution` / `critical` |
| `verification` | `software-checked`, `CTSPro-reopen-verified`, `unverified`, … |

`tests/test_parameter_specs.py` asserts the table covers every dataclass field of every
visible module and that declared defaults match the module dataclass, so a new parameter
cannot reach the UI as an undocumented JSON key.

Input parsing accepts what lab users type — `C/3`, `1.5C`, `30분`, `1시간 30분`, `1h30m`,
`4.2 V` — and every value is displayed with its derived counterpart (C-rate ↔ mA, seconds
↔ Korean duration, capacity fraction ↔ SOC).

### Procedure

`ir/procedure.py` presents the module list as a linear procedure. The module list order is
authoritative; `linearize()` rewrites the wiring to match it, and `adopt_connection_order()`
does the reverse once, at load time, so graph-editor projects normalize cleanly.
`detach_module()` freezes a preset into a `custom_steps` module whose expansion is
byte-identical to the preset's until the user edits it.

### Release ladder

`release.py` computes the current stage (초안 → 소프트웨어 검증 → CTSPro 확인 대기 →
CTSPro 확인 완료 → 장비 실행 승인) and, for each output path, whether it is allowed and
exactly what is blocking it. `exporting.py` holds the writers and re-checks the gate, so
calling a writer directly cannot bypass it. CTSPro review and equipment approval are
recorded in the project's `review` block — only a person can set them.

## Template-preserving writer

1. Start from the exact CTSPro-authored SCH file to preserve.
2. Obtain its SHA-256 from a `compare` report.
3. Copy `example/sch-patch.template.json` and set the hash, expected version, step number, field, and raw value.
4. Run `patch-sch ... --allow-analysis-output`.
5. Review the generated `.sch.manifest.json`, including the target profile,
   changed-field evidence, binary-diff checks, and equipment-test status.

The default path accepts Gate B writer-ready fields (`fVref`, `fIref`, `fEndV`, `fEndI`,
`loop_target`, `loop_count`, `record_time_s`) and rejects others.
`--allow-unverified-fields` is for offline reverse-engineering only. Every write requires
`--allow-analysis-output`. Neither makes a file safe to execute on equipment.

The `build`, `patch-sch`, and `resume` write paths all emit a required
`<output>.manifest.json` sidecar. The standalone current-rescaling tool does the
same. A newly created SCH is removed if its manifest cannot be written.

## Module flow editor

Module palette, visual canvas, linear connection validation, JSON editors, `.schproj` load/save, and step-intent preview. Branching and cycles are rejected (linear schedule model).

## Cell interpretation pipeline

```
filename → FP (loading) → mono/multi → L-level → Q_nom → C-rate
```

| Item | Rule |
|------|------|
| **FP** | `1818`, `3350`, `70150`, `70295`, `101295` loading geometry |
| **Si composition** | `6040`, `6535`, `7030`; these are not FP values |
| **L-level** | Explicit filename values such as `L5.0` and `L.4.36`; omitted mono defaults to **L5.0** |
| **Stack** | `8M1U`, `8M2U` → **K = M × U** double-sided electrode count |

## Example data

- `example/fixtures/capacheck_zip/` — capacheck/QPEED/RPT fixtures
- `example/fixtures/sch_lab_zip/` — lab SCH fixtures
- `example/fixtures/hppc/` — HPPC fixture
- `example/analysis/` — generated analysis reports

## Tests

```powershell
python -m pytest tests/ -q
```

---

## Protocol & C-rate rules

### Standard C-rate presets

**General:** 0.1C, 0.2C, C/3, C/2, 1C, 1.5C, 2C, 2.5C  
**Fast charge (QPEED/QC):** 3C, 3.5C, 4C, 4.5C, 5C, 5.5C, 6C

### Module defaults

| Experiment | C-rate | Module |
|------------|--------|--------|
| Formation (FM) | 0.1C charge/discharge | `formation` |
| Capacheck / derating | 0.1C then C/3 (sometimes 2× C/3) | `capacheck` |
| Cycle life | 0.5C | `cycle_life` |
| In-situ cycle | 0.5C, no RPT block | `insitu_cycle` |
| RPT | C/3 discharge + DC-IR @ SOC 80/50/20 (1.0–1.5C) | `rpt`, `dcir` |
| QPEED | >2.5C; `SOC_setting` is a QPEED sub-variant | `qpeed` |

### `.schproj` example

```json
{
  "modules": [
    { "id": "fm1", "module_type": "formation", "params": { "charge_c_rate": 0.1 } },
    { "id": "cyc1", "module_type": "cycle_life", "params": { "charge_c_rate": 0.5, "loop_count": 300 } }
  ]
}
```

### Bulk edit

```powershell
python -m pne_scheduler bulk-edit project.schproj --type cycle_life --set charge_c_rate=0.5
python -m pne_scheduler bulk-edit project.schproj --all --set rest_s=600
```

---

## Interrupted experiment resume

원본 `.sch` + 사이클러 데이터(StepEnd / raw CSV)로 재개 지점을 찾고 이어서 실험할 `.sch`를 만듭니다.

### GUI

```powershell
python run_pne_scheduler_resume.py
```

1. **Open .sch** — 원본 스케줄  
2. **Open data** — `*StepEnd.csv` 또는 `*_raw.csv`  
3. **Analyze** — 재개 스텝·남은 loop 확인  
4. **Export resumed .sch**

### CLI

```powershell
python -m pne_scheduler resume orig.sch channel_StepEnd.csv -o out.sch --plan-only
python -m pne_scheduler resume orig.sch channel_StepEnd.csv -o resumed.sch
python -m pne_scheduler resume orig.sch data.csv -o resumed.sch --step 12 --loops 150
```

### Checkpoint rules

| Data | Meaning |
|------|---------|
| StepEnd last row | Last completed CTS step |
| SCH step | `CTS StepNo - 1` |
| `* Complete` | Resume from next SCH step |
| Mid-step interrupt | Resume same SCH step |
| LOOP schedule | Remaining loops from completed discharge count |

### Notes

- Verify StepEnd vs `.sch` step numbers after Analyze.
- Resume splices the original binary (better equipment compatibility than the experimental writer stub).

---

## Related docs

| Doc | Content |
|-----|---------|
| [GATE_B.md](GATE_B.md) | Validation intake, ASSB vendor, Q_nom |
| [GATE_B_GENERATED.md](GATE_B_GENERATED.md) | Auto-generated layout/parser diff annex |
| [CURSOR_CLOUD.md](CURSOR_CLOUD.md) | Cursor Cloud / WSL setup |
| [../planning/README.md](../planning/README.md) | Policies, corpus, roadmap |
