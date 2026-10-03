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

The Export screen saves a draft, step preview, or review candidate into an
existing **empty** directory on the PC running the API. It refuses a nonempty
directory so an existing output cannot be overwritten. A draft can be saved
even while validation errors remain.

## Existing SCH files

Open **기존 SCH 열기** and enter an absolute `.sch` path on the PC running the API.
The screen shows an evidence-labeled explanation and the fields approved for
byte-preserving edits. A patch creates a separate analysis-only `.sch` and a
validation manifest; it never replaces the source file. The 0x00010005/720
layout can be opened and explained, but currently has no approved patch fields
because no controlled writer/reopen evidence exists for it.
