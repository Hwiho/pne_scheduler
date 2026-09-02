# Ensol sch_maker (reference snapshot)

Vendored from `Ensol_sch_maker (1).zip` for Gate B binary-schema work in `pne_scheduler`.

**Do not treat as a runtime dependency.** Use `schema/ensol_v612.py` and tests as the
in-repo canonical adoption layer.

## Adopted into pne_scheduler

| Ensol artifact | pne_scheduler adoption |
|----------------|----------------------|
| `sch_core.py` offset map | `schema/ensol_v612.py` |
| mV / mA units | Gate B0 writer/reader contract |
| `crate_to_mA` | aligns with `engine/c_rate.current_mA_from_c_rate` |
| `sch_current_rescaler.py` | pattern for C-rate-preserving rescale (offset +16, +32) |
| Block expanders (capacity_check, soc_setting, pulse_test) | module naming reference |
| Header safety block @ `0x3D8` | Gate C1 header writer backlog |

## Key semantic correction

On 612-byte `0x00010003` steps (golden capacheck verified):

| Offset | Ensol name | Unit | Legacy mislabel |
|--------|------------|------|-----------------|
| +12 | volt / vlim | mV | `mode_value` |
| +16 | current | mA | `fVref` |
| +20 | time / rest | s | `fIref` |
| +28 | voltage cutoff | mV | `fEndV` ✓ |
| +32 | CV cutoff | mA | `fEndI` ✓ |
| +332 | record ΔV | mV | (new) |
| +340 | record Δt | s | (new) |
| +384 | DOD | % | near ASSB `fSocRate` region |
| +496/+497 | cap mode/ref | bytes | ASSB uses +512/+513 |

## Original entry points (reference only)

```text
battery_scheduler/sch_core.py      # JSON blocks -> .sch writer
battery_scheduler/sch_reader.py    # .sch -> JSON importer
battery_scheduler/sch_current_rescaler.py
```
