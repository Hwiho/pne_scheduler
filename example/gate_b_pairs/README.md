# Gate B controlled-pair drop location

Place real CTSPro save-only evidence here when it becomes available. The repository is
prepared to run without these files, but Gate B cannot exit until valid, reopen-verified
pairs are present.

Use one directory per pair:

```text
example/gate_b_pairs/
└── pne02-charge-current/
    ├── before.sch
    ├── after.sch
    ├── intake.json
    ├── comparison.json
    └── screenshots/
```

For each pair:

1. Open a CTSPro-authored baseline and save it as `before.sch`.
2. Change exactly one UI value and save as `after.sch`; do not execute either schedule.
3. Copy `example/validation-intake.template.json` to `intake.json` and record the CTSPro
   build, channel profile, field, values, and screenshot paths.
4. Generate `comparison.json`:

   ```bash
   python3 -m pne_scheduler compare before.sch after.sch -o comparison.json
   ```

5. Reopen the exact `after.sch` in CTSPro. Set `ctspro_reopen_verified` to `true` only
   after the displayed value and SHA-256 have been recorded.
6. Run:

   ```bash
   python3 tools/run_gate_b_validation.py --require-gate-exit
   ```

The fillable template outside this directory is never counted as evidence.
