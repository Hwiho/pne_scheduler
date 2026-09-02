# PNE02 baseline3 — LOOP goto controlled pair

Use `baseline3-loop-goto.sch` when baseline2’s 4-step layout cannot expose multiple
LOOP goto targets in CTSEditorPro.

## Schedule layout (6 steps, 5432 B)

| Step | Type | Default values (500 mA tier) |
|-----:|------|------------------------------|
| 1 | CCCV | 4000 mV, 10 mA, CV cutoff 2 mA |
| 2 | REST | 60 s |
| 3 | CC_DCHG | 10 mA, end 2500 mV |
| 4 | REST | 60 s |
| 5 | LOOP | count 2, **goto step 1** (`loop_goto_ensol@564` = 1) |
| 6 | END | — |

Corpus template: `CCCV → REST → CC_DCHG → REST → LOOP → END` from PNE02.zip
(`0x00010003/612`, payload @ 1760).

## Controlled pair procedure

1. Open `baseline3-loop-goto.sch` in CTSEditorPro on **PNE02** → save as `before.sch`.
2. Edit **LOOP step 5** goto target: **step 1 → step 2** (or step 3) → save `after.sch`.
   On save CTSEditorPro may expand the schedule (observed: 18 steps); the controlled
   change lands on the outer LOOP step (step 17 in `goto_controlled_pair.zip`).
3. Create `example/gate_b_pairs/pne02-loop-goto/` with intake + comparison.
4. Expected field: `loop_target@48` on LOOP step 17 (CTSEditorPro writes legacy goto
   offset; `loop_goto_ensol@564` stays 1 in both files).

```powershell
python tools/export_baseline3_loop_goto_pne02.py
python -m pne_scheduler compare before.sch after.sch -o comparison.json
```

## Why not baseline2?

On `CCCV → CC_DCHG → LOOP → END`, CTSPro LOOP goto UI exposes only step 1.
This 6-step template adds REST steps before LOOP so steps **1–4** are selectable
goto targets.

## Regenerate

```powershell
python tools/export_baseline3_loop_goto_pne02.py
```

Output: [`baseline3-loop-goto.sch`](baseline3-loop-goto.sch) +
[`baseline3-loop-goto.meta.json`](baseline3-loop-goto.meta.json).

After reopen on PNE02, if CTSEditorPro re-saves as `0x10002/1632` (4080 B) that is
normal — same as other imported pairs.
