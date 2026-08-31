# SCH Validation Data Intake

This workflow turns new CTSPro exports into reproducible binary-field evidence. It is
designed for incomplete schemas: unknown bytes remain opaque until a controlled file pair
isolates their meaning.

## Minimum data per equipment profile

For each relevant equipment profile (for example PNE02, PNE16, PNE21, or PNE22), collect:

1. Equipment label and current rating.
2. CTSPro version or an About-screen screenshot.
3. Channel range/profile or applicable INI settings.
4. One baseline SCH file that CTSPro can open.
5. A before/after pair where exactly one UI field changed.
6. Screenshots showing the changed field and both values.

Do not infer equipment identity from a schedule filename. Record the known source explicitly.

## Recommended controlled pairs

Start with a schedule that is saved but not executed:

```text
REST → CC Charge → REST → CC Discharge → END
```

Create a separate pair for each field:

| Pair | Example change |
|------|----------------|
| Rest duration | 60 s → 123 s |
| Charge current | 10 mA → 17 mA |
| Discharge current | 10 mA → 19 mA |
| End voltage | 3000 mV → 3123 mV |
| CV cutoff current | 2 mA → 3 mA |
| Sampling interval | 1 s → 2 s |
| Loop count | 2 → 3 |
| Loop target | One known step → another known step |
| Capacity termination | Disabled → one nonzero value |
| DCR window | One start/end pair → another pair |

Use values that are valid for the selected CTSPro profile. These files are schema probes,
not authorization to execute a schedule on a live cell.

## Metadata

Copy `example/validation-intake.template.json` next to each pair and fill in the known
values. `expected_field` may remain null when the purpose is discovery.

The `scope` value must distinguish a fixture-specific equipment source from a general
operational routing statement.

## Generate a binary diff report

```powershell
python -m pne_scheduler.tools.compare_sch `
  before.sch after.sch `
  -o comparison.json
```

The report includes:

- Version, payload offset, record size, and step count for each file.
- Header byte ranges that changed.
- Changed byte ranges grouped by step.
- Aligned 4-byte interpretations as hex, unsigned integer, signed integer, and float.
- Known field names and their current evidence confidence.

If layouts or step counts differ, the tool reports incompatibility instead of aligning
unrelated records.

## Evidence promotion rules

Do not mark a field as writable from one uncontrolled sample.

1. `semantic_unverified`: legacy name or observed slot without controlled evidence.
2. `corpus_inferred`: repeatable type/value pattern or one controlled pair.
3. `structural_verified`: framing or identity field confirmed across the fixture corpus.
4. Writer-ready: at least two controlled values, a CTSPro reopen check, and no unrelated
   byte changes after preserving metadata.

For equipment-dependent scaling, require the same displayed value from at least two channel
ranges or a matching INI definition.

## Applying new evidence

1. Add the raw pair and metadata outside the public fixture set if the data is sensitive.
2. Generate and review the comparison report.
3. Add or update the field in `schema/fields.py`.
4. Add a golden test using sanitized or approved fixtures.
5. Regenerate `example/fixtures/catalog.json` only when the checked-in fixture corpus changes.
6. Run the full test suite.
7. Confirm the generated or patched SCH reopens in CTSPro before any equipment execution.
