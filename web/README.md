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
