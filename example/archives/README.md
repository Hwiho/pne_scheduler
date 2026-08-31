# Example schedule archives

Original `.zip` archives used to build the extracted fixtures under `fixtures/`.

| Archive | Contents | Extracted to |
|---------|----------|--------------|
| `sch.zip` | 93 lab `.sch` schedules | `fixtures/sch_lab_zip/` |
| `9)Bimodal_SJ1300_6040_NCN_capacheck.zip` | 8 bimodal SJ1300 reference schedules | `fixtures/capacheck_zip/` |

## Extract locally

```powershell
Expand-Archive -Path example/archives/sch.zip -DestinationPath example/fixtures/sch_lab_zip -Force
Expand-Archive -Path "example/archives/9)Bimodal_SJ1300_6040_NCN_capacheck.zip" -DestinationPath example/fixtures/capacheck_zip -Force
```

## Batch analysis (sch.zip)

```powershell
python -m pne_scheduler.tools.analyze_sch_zip example/archives/sch.zip
```

See also `example/analysis/sch_zip_report.json` for a pre-generated report.
