# PNE 스케줄 워크스페이스 — 웹 UI

```powershell
# 1) API (랩 PC, localhost 전용)
python run_pne_scheduler_api.py

# 2) 화면
cd web
npm install
npm run dev          # http://localhost:3000
```

`next.config.ts` proxies `/api/*` to the Python process, so the browser stays on
one origin and the API needs no CORS surface.
The default dev/start commands bind the web UI to `127.0.0.1` too; this local
resource editor is not intended to be exposed to the LAN.

**The proxy target is baked at build time.** `npm run build` reads `PNE_API` and
writes it into the route manifest, so `next start` ignores a later change — set it
before building, or use `npm run dev`.

## What lives where

The screens hold no rules. Every gate — what may be exported, whether a file is
equipment-executable, which patterns are trusted — is computed by `release.py` and
`validate/` and arrives as data. Forms are rendered from the `spec/` metadata, so
a new parameter appears with its unit, range, basis and verification level intact
rather than needing markup written for it.

Undo/redo and autosave live in the browser: an undo entry is just a past project,
so the server stays stateless and a restart loses nothing.

The Protocol screen now centers on a **box-and-connector method flow**: click a
module in the palette to append it, drag it into the flow, or use `+` to insert
it between boxes. The pointer drag selects the nearest connector in the visible
canvas, so the drop target is not limited to the small `+` button. To change
the execution order, click a box's **연결** button then a connector, drag the
box by its top handle, or use the arrow buttons.
Selecting a box opens its
parameter form below. The visible chain is the actual `.schproj` module order;
the server rewrites its connections when order changes. This is a **linear
execution path**, not a branching instrument-control graph. The goal picker,
cycle/RPT campaign, duration planner and detailed step table remain available
below the flow. The goal picker opens a scrollable list. Validation remains
enforced by the API; findings are shown in the Export screen instead of a
separate navigation step.

**고온저장** stores sample, nominal temperature, start and target time in a
local SQLite database on the API PC (`~/.pne_scheduler/storage.sqlite3`). It
recomputes elapsed time in the browser; a separate Windows user-session
companion can request a due/overdue notification after the browser closes.
The old browser-only records appear as a one-time, explicit import option.
Import never deletes the browser original and imported records have alerts off.
This is not a chamber controller or verified temperature log. It does not
sync to other PCs, and Windows notification visibility depends on OS settings.

On the Windows lab PC, install this package into the same Python environment
used by the API. Run `pythonw -m pne_scheduler.storage_companion` to test the
companion in the current user session. After confirming notifications work,
run `windows/install_storage_notifier.ps1 -PythonwPath 'C:\path\to\pythonw.exe'`
from the repo root to opt in to login startup. The script refuses to overwrite
an existing startup shortcut. Removing that shortcut stops future auto-start;
the current process must still be stopped separately. Notification failures
are logged beside the SQLite database as `storage.notifier.log`. Due notices
missed while the PC is off are retried at the next companion run, not delivered
while the PC is powered down. This Windows path still needs a real-PC test.

The Export screen saves a draft, step preview, or review candidate into an
existing **empty** directory on the PC running the API. It refuses a nonempty
directory so an existing output cannot be overwritten. A draft can be saved
even while validation errors remain.

The cell batch panel is separate: paste one `cell ID, reference capacity (mAh)`
row per cell, choose the recipe phase, preview 1C/current and blockers, then
generate into a **new** absolute-path directory. The reference capacity is
used directly for every C-rate step in that cell file; no activation/derating
result import or design-capacity field is required. Entered values are unverified. Each batch
has a manifest; review-candidate SCHs remain reopen-only, not executable.

For regression tests, run `python -m pytest tests/ -q` from the repository root,
then start API + web and run `npm run test:ui` in `web`. The browser test
requires the `playwright` Node package (`npm install --no-save playwright`) and
locally installed Chrome; it uses a
fresh, non-persistent browser context. The test checks goal picker, box
duplicate/undo, batch preview, storage status and 1280/390 px layout.

## Existing SCH files

Open **기존 SCH 열기** and enter an absolute `.sch` path on the PC running the API.
The screen shows an evidence-labeled explanation and the fields approved for
byte-preserving edits. A patch creates a separate analysis-only `.sch` and a
validation manifest; it never replaces the source file. The 0x00010005/720
layout can be opened and explained, but currently has no approved patch fields
because no controlled writer/reopen evidence exists for it.
