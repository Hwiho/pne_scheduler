# Extended step types — OCV / Impedance / Pattern / Balance

Status: **IR + compiler stubs wired** (2026-09-08). Type codes are known from
Excel / CTSEditorPro. **No secured-corpus `.sch` samples** contain these types
(`planning/STEP_TYPES_OCV_IMP_BALANCE.json` → `target_samples: {}`).

Do **not** claim equipment-executable schedules that use these types until a
PNE02 controlled pair (or CTS reopen of a from-scratch probe) confirms field
meaning beyond `step_type@8`.

## Type codes (`schema/enums.py`)

| CTS UI Type | IR `step_type` | Code | Notes |
|-------------|----------------|------|-------|
| Ocv | `ocv` | `0x04` | Time-like hold; UI often shows no Mode |
| Impedance | `impedance` | `0x05` | Excel mentions `STRUCT_EIS_SET` on newer layouts; 612 map unknown |
| Pattern | `pattern` | `0x09` | Pattern file reference unknown |
| Balance | `balance` | `0x0A` | May use I/V like charge; unconfirmed |

Parser / layout detection accept these via `SCH_STEP_TYPES`.

## Addresses in use today (shared Ensol 612 prefix)

When the IR sets a value, the compiler packs the **same** offsets already verified
for Rest / Charge / Discharge. Confidence for these types: **corpus_inferred /
unverified** until pairs exist.

| Field | Offset | IR source | Confidence for OCV/Imp/Bal/Pat |
|-------|--------|-----------|--------------------------------|
| `step_no` | `+0` | auto | structural |
| `step_type` | `+8` | type code above | structural (enum/UI) |
| `volt_or_vlim_mV` | `+12` | `voltage_v` × 1000 | unverified for these types |
| `current_mA` | `+16` | `current_mA` / `c_rate` | unverified |
| `time_or_rest_s` | `+20` | `end_time_s` | unverified (likely for OCV) |
| `record_dV_mV` | `+332` | `record_dV_mV` | unverified |
| `record_time_s` | `+340` | `record_time_s` (default 60) | unverified |
| `cap_mode` | `+496` | set `0x01` for ocv/imp/balance | unverified |

Not packed for these types (no evidence): impedance EIS params, pattern path,
balance-specific end conditions, safety-panel impedance mOhm limits (header /
per-step safety blocks — separate from step body).

## Corpus mining

```text
python -m pne_scheduler.tools.mine_step_types_ocv_imp_balance
```

Writes `STEP_TYPES_OCV_IMP_BALANCE.json`. As of 2026-09-08: **zero** hits across
`example/` fixtures and Gate B pairs.

## Next lab action (optional, Gate D/F)

1. In CTSEditorPro on PNE02, author minimal schedules: Rest→**OCV**→END,
   Rest→**Impedance**→END, Rest→**Balance**→END (and Pattern if used).
2. Save + reopen; keep before/after bytes for controlled-pair intake (Gate B5).
3. Promote nonzero deltas into `schema/fields.py` with evidence strings.

Until then, `compile_step_warnings()` emits a per-step note pointing here.
