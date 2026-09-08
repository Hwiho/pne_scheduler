# Gate C5 — Evidence Coverage Analysis (why one optimized reopen is enough)

Generated 2026-09-06 while preparing an optimized C5 smoke artifact. This document
answers one question with data already in the repository: **for the from-scratch
writer, what genuinely still requires a physical CTSEditorPro reopen, and what has
already been settled by controlled pairs or corpus mining?** The goal is to shrink
the number of future lab sessions to the minimum the data allows — not to skip C5,
which stays mandatory per `ROADMAP.md` §6.4/§11.

Evidence tiers (per `ROADMAP.md` §5.6 L1): **controlled pair > reopen-verified
fixture > corpus majority > filename/Excel name.** Nothing below is promoted past
what its cited tier supports.

## 1. Per-field coverage matrix

| Field (offset) | Confidence (`schema/fields.py`) | Strongest evidence on file | In `smoke_writer_probe.sch`? | Residual physical-test need |
|---|---|---|---|---|
| `mode_value`/charge V @12 | corpus_inferred | `pne02-end-voltage` pair (reopen-verified) | Yes — charge target 4.200 V | None — already reopen-verified; probe re-confirms in a from-scratch build |
| `mode_value`/discharge V-limit @12 | corpus_inferred | 4 of 5 `GOLDEN_SEMANTIC_EXPECTATIONS.json` fixtures = 2000 mV (one outlier 2400 mV); no discharge-V-limit controlled pair exists | Yes — reads back 2.000 V | Low — corpus-majority only; this run also serves as the first equipment look at this specific sub-field |
| `fVref`/current @16 | corpus_inferred, writer_ready | `pne02-charge-current` **and** `pne02-discharge-current` pairs (both reopen-verified) | Yes — 8.00 mA charge, 8.00 mA discharge | None on the value; only the from-scratch assembly is unverified |
| `fIref`/time_or_rest_s @20 | corpus_inferred, writer_ready | `pne02-rest-duration` pair (reopen-verified) | Yes — 50 s and 35 s (two distinct rests) | None on the value |
| `fEndV`/voltage_cutoff @28 | corpus_inferred, writer_ready | `pne02-end-voltage` pair (reopen-verified); 5/5 golden fixtures = 2500 mV | Yes — discharge cutoff 2.500 V | None |
| `fEndI`/cv_cutoff @32 | corpus_inferred, writer_ready | `pne02-cv-cutoff` pair (reopen-verified) | Yes — 4.00 mA | None |
| `loop_target` @48 | corpus_inferred, writer_ready | `pne02-loop-goto` pair (reopen-verified) | Yes — goto step 1 | **This is the one genuinely new axis**: prior pairs verified loop fields via `patch-sch` on an existing template, never inside a from-scratch-built header |

| `loop_count` @52 | corpus_inferred, writer_ready | `pne02-loop-count` pair (reopen-verified) | Yes — count 2 | Same as above |
| `record_time_s` @340 | corpus_inferred, writer_ready | `pne02-sampling-interval` **and** `pne02-sampling-interval-discharge` pairs (both reopen-verified, independently, for charge vs. discharge) | Yes — 30/25/15/10 s, four distinct values across four steps | None on the value; probe additionally checks the field is read per-step, not defaulted |
| `record_dV_mV` @332 | corpus_inferred | 79 near-pairs; golden capacheck fixture = 10 mV | Yes — 20 mV charge, 5 mV discharge (both non-default) | Low |
| `dod_percent` @384 | corpus_inferred (not yet writer_ready) | 554/856 filename-SOC matches; supersedes legacy `fSocRate`@392 per `GATE_B_CORPUS_EVIDENCE.json` | Yes — 40.0 (bonus/observational; not required for pass/fail) | Optional — recording what CTSEditorPro shows here is new evidence toward promoting it to writer_ready |
| `cap_mode` @496 | corpus_inferred | Golden capacheck fixture + 658 near-pairs; auto-set by the compiler on every active step | Yes — 1 on charge/rest/discharge | None |
| Whole-header framing (magic, version, name, timestamps, CTS common-safety @0x458 as Vmax/Vmin/Imax/Imin/Cap/Temp, step hint @0x484) | Framing corpus-matched, never physically reopened as a **from-scratch** assembly | `SCH_696_TAIL_ANALYSIS.md`, `docs/GATE_B.md` | Yes — this is the actual thing C5 tests | **This is the real remaining unknown.** See §3. |

Fields intentionally **not** packed anywhere in the writer, because 100% of the
23,275-file mined corpus and all 102 checked-in fixtures leave them zero (a
corpus-consensus decision, not an oversight): `fEndC`@36, `fSocRate`@392 (superseded
by `dod_percent`@384), `fMaxCapacity`@428, `bUseActualCapa`@512 (superseded by
`cap_mode`@496), `bUseDataStepNo`@513 (superseded by `cap_ref_step`@497),
`nGotoStepID`@92, `process_word`@4. There is nothing for C5 to check on these —
they are absent by design, matching every real file on record. Do not add packing
for them without new controlled-pair evidence (`ROADMAP.md` L3).

## 2. What the combinatorial probe actually buys

`example/smoke_writer_probe.schproj` / `.sch` (module `smoke_writer_probe`, see
`modules/smoke_writer_probe.py`) packs every writer-ready and high-confidence
corpus-inferred field above into **one** 6-step file, each with a distinct numeric
value so a single visual pass can attribute every displayed number to exactly one
field:

```
1. CCCV charge   -> 8.00 mA, 4.200 V, cutoff 4.00 mA, sample 30 s / 20 mV
2. rest          -> 50 s, sample 25 s
3. CC discharge  -> 8.00 mA, cutoff 2.500 V, sample 15 s / 5 mV, DOD 40% (bonus)
4. rest          -> 35 s, sample 10 s
5. loop          -> goto step 1, count 2
6. end
```

No leading Cycle marker: CTSEditorPro requires Cycle…Loop pairing, and PNE02
reopen-verified loop pairs omit Cycle (body→Loop→End). An earlier probe that
inserted Cycle failed save with "Loop 종료 없이 새로운 Cycle".

This step shape matches the **body** of `CycleLifeModule.expand()` without the
Cycle wrapper CTS rejects when unpaired —
noted as risk reduction only, **not** claimed as a Gate D pass (Gate D still
requires its own `validate -> expand -> compile -> parse -> semantic compare`
integration test per `ROADMAP.md` §6.5).

Internal software checks already pass before this ever reaches a lab PC:
`validate/roundtrip.py` compares every packed value against the intent
(`tests/test_c6_tail_and_smoke.py::test_smoke_writer_probe_project_roundtrips`),
and `schema.fields.validate_step_field_registry()` proves zero byte-range overlap
across the whole field map.

## 3. The one thing data cannot resolve: header framing bytes outside the modeled fields

Comparing the from-scratch `build_sch_header()` path (used by CLI
`build --allow-experimental-output`) against a real lab-authored header
(`example/fixtures/capacheck_zip/9)Bimodal_SJ1300_6040_NCN_capacheck.sch`,
byte-for-byte) shows **54 of 1760 header bytes** are non-zero in the real file but
left zero by `build_sch_header()`, concentrated in two clusters:

- `0x02D8`-`0x0361` (~44 bytes, spanning past `HOFF_NAME`'s declared 100-byte
  window): looks like a second name/description slot. `ROADMAP.md` §2.3 documents
  `FILE_TEST_INFORMATION (x2 blocks)` with `szName[]`/`szDescription[]` — this is
  plausibly the second block, which nothing in `schema/ensol_v612.py` currently
  maps.
- `0x0291`-`0x0298` (~6 bytes): just past `HOFF_TIMESTAMP_2`'s declared 63-byte
  window; likely incidental (a longer string in that specific file) rather than a
  distinct field, but not confirmed either way.

No offset name is being introduced for these — there isn't controlled-pair or
even corpus-majority evidence for what belongs there, only "a real file had bytes
here and our code doesn't." Per L3 (no speculative packing), the correct response
is to **not leave them zero for an equipment-facing test**, not to guess their
meaning. That is why `tools/rebuild_smoke_sch_from_lab_header.py` clones a real
lab header and only overwrites the offsets we do have evidence for, rather than
using `build_sch_header()`'s all-zero-elsewhere framing — it is strictly the safer
artifact to take into the lab, and it is what `smoke_writer_probe.sch` was built
with.

**Consequence for CLI `build`:** a clean C5 result on `smoke_writer_probe.sch`
confirms the lab-header-clone framing, not `build_sch_header()`'s all-zero
framing — those 54 bytes remain a genuine open question for the plain CLI `build`
path specifically. Logged as a new backlog row in `ROADMAP.md` §11; no action
needed unless `build_sch_header()` becomes the artifact that actually goes to
equipment.

## 4. Bottom line

Everything with a `writer_ready` flag or a PNE02 controlled pair was already
individually reopen-verified before this analysis — the risk left in Gate C is not
"is field X's value right," it is "does one from-scratch-assembled file combining
all of them still open cleanly." `smoke_writer_probe.sch` is built specifically to
answer that in one session, and its manifest/checklist reflect a single probe
in place of any need for one physical test per field or per future module shape.
