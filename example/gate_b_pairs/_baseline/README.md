# PNE02 v612 controlled-pair baseline

`PNE02_V612_BASELINE_ANALYSIS_ONLY.sch` is a template-preserving, offline seed for
creating the PNE02 controlled pairs listed in `../CONTROLLED_PAIR_QUEUE.md`.

It is derived from the CTSPro-authored PNE02 fixture
`example/fixtures/capacheck_zip/9)Bimodal_SJ1300_6040_NCN_capacheck.sch`. The original
header, file length, step topology, and every undeclared byte are preserved.

Intended baseline values:

| Step | Type | Setting | Value |
|---:|---|---|---:|
| 1 | Rest | Duration | 60 s |
| 4 | CCCV charge | Current | 10 mA |
| 4 | CCCV charge | CV cutoff current | 2 mA |
| 4 | CCCV charge | Sampling interval | 1 s |
| 6 | CC discharge | Current | 10 mA |
| 6 | CC discharge | End voltage | 3000 mV |
| 6 | CC discharge | Sampling interval | 1 s |
| 14 | LOOP | Count | 2 (already present in source) |
| 14 | LOOP | Target | Step 2 |

## Required CTSPro conversion

This seed was patched offline with corpus-inferred fields. It is **not** equipment-ready
and must never be executed.

1. Open the seed in the target PNE02 CTSPro build without connecting it to a running
   channel.
2. Confirm every value in the table. If CTSPro displays a different LOOP target, set
   Step 14's target to Step 2 in the UI.
3. Save as `PNE02_V612_BASELINE_CTSPRO.sch`.
4. Close and reopen that exact file, confirm all displayed values, and record its SHA-256.
5. Use the reopened CTSPro-saved file—not this offline seed—as `before.sch` for each pair.
6. Change exactly one UI setting for each `after.sch`; never run either file on equipment.

The reproducible input is `pne02-v612-baseline.patch.json`. The generated report records
the source and output hashes and all modified byte ranges.
