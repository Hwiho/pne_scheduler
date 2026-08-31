"""Lab protocol C-rate defaults (formation, capacheck, cycle, RPT)."""

from __future__ import annotations

C_THIRD = 1.0 / 3.0

# Formation (FM) — gentle charge/discharge
FORMATION_C_RATE = 0.1

# Capacheck / derating — 0.1C then C/3 (sometimes C/3 twice)
CAPACHECK_INITIAL_C_RATE = 0.1
CAPACHECK_MEASUREMENT_C_RATE = C_THIRD

# Cycle life / in-situ cycle — default aging rate
CYCLE_DEFAULT_C_RATE = 0.5

# RPT — reference discharge C/3, DC-IR pulse at SOC 80/50/20
RPT_DISCHARGE_C_RATE = C_THIRD
RPT_DCIR_SOC_FRACTIONS: tuple[float, ...] = (0.8, 0.5, 0.2)
RPT_DCIR_PULSE_C_RATE_DEFAULT = 1.5
RPT_DCIR_PULSE_C_RATE_ALT = 1.0

# QC / fast-charge experiments use higher rates (see engine.c_rate.FAST_CHARGE_MIN_C_RATE)

PROTOCOL_SUMMARY: dict[str, str] = {
    "formation": "FM — default 0.1C charge/discharge",
    "capacheck": "0.1C → C/3 (optional double C/3)",
    "derating": "same as capacheck (0.1C → C/3)",
    "cycle_life": "default 0.5C charge/discharge",
    "insitu": "0.5C cycle without RPT blocks",
    "rpt": "C/3 discharge ladder + DC-IR pulse @ SOC 80/50/20 (1.0–1.5C)",
}
