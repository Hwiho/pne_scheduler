# HPPC schedule fixture

| File | Category | Steps | SCH version | Step size |
|------|----------|------:|-------------|-----------|
| `HPPC_Full range.sch` | HPPC (full voltage range) | 62 | 0x00010002 | 612 |

This file is a **full 2.5–4.2 V** characterization with residual ~30 mA CC steps at
the same voltage limits. `fEndC` is unused, so it is **not** a stored SOC 90/50/10
pulse staircase. The HPPC module generator still defaults to that staircase as a
template for new projects; do not treat the two as the same.

```powershell
python -m pne_scheduler explain "example/fixtures/hppc/HPPC_Full range.sch"
python -m pne_scheduler view "example/fixtures/hppc/HPPC_Full range.sch"
```
