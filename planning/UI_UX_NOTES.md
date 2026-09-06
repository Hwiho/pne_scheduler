# UI/UX reference notes for Gate E (2026-09-06)

Context: Gate E wants the schedule-authoring UI to feel like **Autolab Nova +
LabVIEW** — module/procedure composition, not instrument control (ROADMAP.md
§1.1, §6.6). This doc collects two kinds of input before anyone builds E0–E2.4
from scratch: (1) concrete prior art already sitting unmerged in this exact
repo, and (2) general patterns from the named reference products. Read this
before starting E2/E2.1/E2.2 implementation.

## 1. Prior art already in this repo (found 2026-09-06)

Six `cursor/*` remote branches exist from earlier Cursor Cloud runs, never
merged, never deleted. Three touch the UI directly. None should be merged
wholesale (all are stale against current master in different ways — see
per-branch staleness note) but each contains a concrete, evaluated pattern.

### `cursor/update-roadmap-5ac9` — theming + attach/detach wiring (recommended first pick)

**Staleness: low.** `ui/flow_editor.py` and `ui/flow_model.py` are untouched
by master since this branch split off — the relevant diff applies cleanly.

- `ui/flow_theme.py` (new, 171 lines): a real small design system, not a
  sketch. Per-module-type `ModuleStyle` records (fill, fill_selected, accent,
  ink, mute, icon, title) for every module type — formation🌱, cycle_life🔁,
  rpt📊, dcir⚡, hppc💗, qpeed🚀, rest💤, capacheck📏, insitu_cycle🔬 — on a
  warm cream/terracotta palette (`#f4efe8` base, per-type pastel fills, e.g.
  HPPC pink `#ffd9e8`/`#d96b98`). Fixed card geometry (`CARD_WIDTH=232`,
  `CARD_RADIUS=22`, `PORT_RADIUS=8`), a `rounded_rect_points()` helper for true
  rounded cards on a Tk `Canvas` via `create_polygon(..., smooth=True)`, and a
  `validate_module_styles()` self-check that every registered module type has
  a style (fails loudly instead of silently falling back to a default look).
- **Attach/detach interaction**: each module card gets two canvas ovals
  (`port-out:{id}` / `port-in:{id}`). Click an output port → pending-attach
  state, port highlights amber, status bar prompts "Click an input port to
  attach after X". Click an input port → `FlowProjectModel.rewire(source,
  target)` atomically detaches any existing wire on either port and attaches
  the new one, returning human-readable notes ("Detached A→B", "Attached
  A→C") for the status bar. `Escape` cancels. Wires are elbow/orthogonal
  splines; click to select (turns orange, thicker), double-click to remove.
- Also adds `engine/duration.py` (`estimate_step_duration` /
  `combine_duration_estimates`) — a running total-schedule-duration estimate,
  tolerant of unknown/approximate steps. Directly useful for E2's "C-rate ↔ mA
  preview" cue and any Validate-screen summary.

**Recommendation:** port this first. It maps directly onto E2.2 ("LabVIEW-like
modules" cue) and gives E2 real drag/attach interaction instead of the current
seed's simpler connection model, with essentially zero merge conflict.

### `cursor/module-recipes-presets-5ac9` — recipes, presets, pattern overview

**Staleness: mixed.** The UI/data pieces are additive and clean to port; the
binary-export wiring is not (see below).

- A **recipe** (`modules/recipe.py`) is a small ordered program inside one
  module: `ModuleRecipe(setup, repeat, repeat_count, after)` of `RecipeUnit`s
  (charge/discharge/rest/cycle/loop/end with `c_rate`, `mode`, `end_voltage_v`,
  `end_time_s`, `cv_cutoff_c_rate`, and a `.summary()` like `"C/3 CCCV → 4.2
  V"`). `.expand()` turns it into `StepIntent`s. `modules/presets.py` builds
  named recipes procedurally (e.g. `build_qpeed_full_3318` mirrors the real
  QPEED fixture sequence).
- UI: a Preset combobox + "Rebuild from preset/knobs" button, plus an "Inside
  this module" notebook with Setup/Repeat/After tabs (each a `Treeview` of
  unit summaries, +Charge/+Discharge/+Rest, Up/Down/Delete, double-click →
  edit dialog). Raw JSON survives as a collapsed "Advanced" fallback — good
  precedent for E2.1's palette (structured editing, not raw JSON, as the
  primary path).
- **Pattern overview** (`protocol/overview.py::compose_overview`): plain-text
  "what this schedule does" block — flow summary, per-module Setup/Repeat/
  After lines, expanded step count, caveats. This is close to what E3's
  "readiness before export" screen wants as a human-readable pre-flight
  summary.
- **"Reload-safe experimental SCH export"**: `write_sch_reloadable()` writes,
  then immediately re-parses with the repo's own parser and raises if that
  fails — i.e. gates "export" on "our own reader can read it back," not on
  equipment compatibility, and the dialog explicitly warns it isn't
  equipment-ready. A cheap, good pattern regardless of which UI code survives.

**Why not a clean port:** `engine/compiler.py::_compile_one_step` and
`io/writer.py` were independently rewritten on both sides since this branch
split off master — master now packs the Gate-B-verified Ensol v612 field map
(`schema/ensol_v612.py` offsets, `compile_step_warnings()`), while this branch
uses an older ad hoc offset scheme. Porting the recipe/preset/overview UI is
low-risk; porting "recipe → binary" wiring needs a real redo against master's
current compiler, not a cherry-pick.

**Recommendation:** port `modules/recipe.py` + `presets.py` + the notebook UI
and "reload-safe export" pattern (rewritten against master's current
`write_sch`, not copied); treat as a design reference for E2.1/E2.3, not a
drop-in.

### `cursor/explain-schedules-5ac9` — schedule explainer

**Staleness: lowest** (2 commits from the shared split point; the constants it
depends on are unchanged in master's `schema/fields.py`).

- `protocol/explain.py::explain_schedule(document)` reverse-engineers an
  **existing/unknown `.sch` file** into a `ScheduleExplanation` (family,
  variant, confidence, SOC checkpoints, phases, caveats) where every claim
  carries an `EvidenceKind` (`filename`, `voltage_setpoint`, `step_topology`,
  `rest_duration_heuristic`, `unverified`). Concretely: for an HPPC file it
  says the pulses do *not* match a SOC 90/50/10 staircase; for a QPEED file it
  says a 3.318 V setpoint is not a stored SOC percentage; for an
  `RPT_SOC50`-named file it says the 50% SOC "cannot be confirmed" (filename
  evidence only). This evidence-labeling discipline matches the project's own
  `schema/fields.py` confidence tiers exactly — same philosophy, applied to
  prose.
- **Fit:** built for classifying legacy corpus files, not narrating a
  freshly-authored flow-editor graph. Genuinely useful for a Validate/Export
  screen ("here's what this schedule does, with confidence and caveats,
  before you export it") but needs a second front end that explains
  `StepIntent`s directly rather than a parsed binary — not a drop-in for E3,
  but the right shape of feature for it once Gate C exits.

## 2. General patterns from the named reference products

Autolab NOVA and LabVIEW are the project's own stated inspirations (§1.1) —
worth pulling concrete, well-established patterns from both rather than
guessing at "modular UX":

**Autolab NOVA procedure editor** (closest existing analogue to what E2/E2.1
already describe):
- Commands live in a palette organized by category; dragging one into the
  procedure list inserts it at that position — matches E2.1 directly.
- Each command shows a *collapsed* one-line summary in the list and expands
  inline for parameter editing, rather than opening a separate dialog for
  everything — the recipe branch's `.summary()` string is exactly this
  pattern, worth keeping regardless of which other code survives.
- Saved procedures are reusable templates ("Manager") — maps directly to
  E2.3; NOVA scopes these per instrument/technique the way this project
  should scope them per equipment profile (already noted in E2.3's criteria).

**LabVIEW block diagram** (informs the node/module-graph half, E2.2/E7):
- Wires are colored/styled by the type of thing they carry — this project's
  module-type color coding (from `flow_theme.py` above) is the direct
  equivalent for step/module graphs.
- A broken/invalid connection is a visible broken-wire glyph, not just a
  validation-panel error elsewhere on screen — worth applying to E3's
  "block invalid loops, missing END, V/I violations": surface the violation
  *on the offending node/wire*, not only in a separate list.
- SubVIs (encapsulated reusable node groups) are the direct LabVIEW analogue
  of this project's "module expands into steps" — already the core design,
  no change needed, just confirms the metaphor is sound.

**General modern node-editor conventions** (React Flow / Node-RED / Blender
shader editor — worth adopting selectively, not wholesale, given the
project's Tkinter constraint, see §3):
- Undo/redo via a command/edit-history stack — already flagged as missing in
  ROADMAP's Gate E progress record; the `rewire()` pattern from
  `update-roadmap-5ac9` (returns a description of what changed) is a natural
  seam for logging undoable operations.
- Keyboard shortcuts for duplicate/delete/connect reduce mouse-only friction
  significantly for a tool used repeatedly by the same lab operators.
- Inline per-node validation badges (not just a separate validation pass) —
  same point as the LabVIEW broken-wire note above, stated in modern terms.

## 3. What this means for the tech-stack question (§3.4)

ROADMAP §3.4 already considered and deferred Tkinter vs PySide6+NodeEditor vs
Web/React Flow+Electron, defaulting to Tkinter as the pragmatic seed. The
`update-roadmap-5ac9` branch proves the LabVIEW-style card/wire look is
achievable in plain Tkinter Canvas (`create_polygon(..., smooth=True)` for
rounded cards, tagged canvas items for ports/wires) without needing a bigger
stack change. **Recommendation: stay on Tkinter for E2/E2.2**, using that
branch's approach as the concrete proof it's sufficient; revisit the
Web/React Flow option only if a genuine need for a minimap, smooth bezier
wires, or heavier graphs (E7 campaign canvas) shows up later — don't
pre-optimize for that now.

## 4. Suggested sequencing

1. ~~Port `ui/flow_theme.py` + attach/detach wiring from `update-roadmap-5ac9`~~
   **Done 2026-09-06.** Also pulled in `engine/duration.py` (schedule duration
   estimate) since `flow_editor.py`'s port depended on it. Added
   `ModuleStyle` entries for `smoke_rest_cc_end`/`smoke_writer_probe` (added
   to this project after the branch was written). 273 tests pass; GUI
   construction and the new `rewire()`/duration-estimate calls were smoke
   -tested non-interactively — a human should still open
   `python -m pne_scheduler flow` once to confirm the visual result, since
   this environment cannot render/screenshot a Tk window.
2. Port `modules/recipe.py`/`presets.py` + the Setup/Repeat/After notebook UI
   from `module-recipes-presets-5ac9`, rewriting the export path against
   master's current `engine/compiler.py`/`io/writer.py` rather than copying
   the old offset logic (E2.1/E2.3).
3. Adapt `protocol/overview.py`'s plain-text summary as an authoring-time
   preview (distinct from `explain_schedule`, which stays a read-only-import
   feature for E4/E3 once Gate C exits).
4. Revisit `cursor/explain-schedules-5ac9` for E4 (`.sch` → IR import,
   software-only, no equipment needed) once E0–E2.4 give it something to
   feed into.

None of the above require Gate C exit or equipment access.
