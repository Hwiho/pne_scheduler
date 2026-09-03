"""Ensol sch_maker 612-byte step layout (validated against golden capacheck).

Source: vendor/ensol_sch_maker_ref/battery_scheduler/sch_core.py
Cross-checked: 9)Bimodal_SJ1300_6040_NCN_capacheck.sch (PNE02 golden, 0x00010003/612).

Legacy names in schema/fields.py (fVref@16, fIref@20) predate this map and are
misleading; prefer the constants below for reader/writer work.
"""

from __future__ import annotations

from dataclasses import dataclass

# Step block (612 bytes, version 0x00010003 payload @ 1760 in corpus)
STEP_SIZE = 612

OFF_STEP_NO = 0
OFF_STEP_TYPE = 8
OFF_VOLT_OR_VLIM_MV = 12  # CCCV: charge voltage mV; CCDi: discharge V-limit mV
OFF_CURRENT_MA = 16
OFF_TIME_OR_REST_S = 20  # CCCV/CC: time limit s; REST: duration s
OFF_VOLTAGE_CUTOFF_MV = 28  # CCDi end voltage mV
OFF_CV_CUTOFF_MA = 32
OFF_END_CAPACITY = 36  # rarely nonzero in corpus
OFF_LOOP_GOTO_LEGACY = 48
OFF_LOOP_COUNT = 52
OFF_LOOP_RESET_FLAG = 88
OFF_RECORD_DV_MV = 332
OFF_RECORD_TIME_S = 340
OFF_DOD_PERCENT = 384
OFF_CAP_MODE = 496  # 0x01 = default cap flag in Ensol writer
OFF_CAP_REF_STEP = 497
OFF_LOOP_GOTO_ENSOL = 564  # Ensol writer sets goto=1 here

# Header (0x00010003 corpus uses 1760-byte payload; Ensol writer uses 1632)
HEADER_SIZE_V2 = 1632
HEADER_SIZE_V3 = 1760
HEADER_SIZE_V4 = 1844
HEADER_MAGIC = bytes([0x71, 0x4D, 0x0B, 0x00, 0x02, 0x00, 0x01, 0x00])
FILE_SIGNATURE = b"PNE CTSPro Schedule File."
HOFF_SIGNATURE = 0x48
HOFF_AUTHOR = 0x150
HOFF_TIMESTAMP_2 = 0x250
HOFF_NAME = 0x298
HOFF_TIMESTAMP_3 = 0x398
HOFF_SAFETY = 0x3D8  # Ensol-style: max V mV, min V mV, max I mA, min I mA, max cap mAh, max temp C
# CTS 1760-byte files (lab corpus): timestamp @0x418, common safety @0x458, step hint @0x484
HOFF_CTS_TIMESTAMP = 0x418
HOFF_CTS_COMMON_SAFETY = 0x458
HOFF_CTS_STEP_HINT = 0x484


CCDI_VLIM_DEFAULT_MV = 2000.0


@dataclass(frozen=True, slots=True)
class EnsolFieldSlot:
    name: str
    offset: int
    dtype: str
    unit: str
    note: str


ENSOL_V612_STEP_FIELDS: tuple[EnsolFieldSlot, ...] = (
    EnsolFieldSlot("step_no", OFF_STEP_NO, "int32", "", "1-based step index"),
    EnsolFieldSlot("step_type", OFF_STEP_TYPE, "uint16", "", "low 16 bits at +8"),
    EnsolFieldSlot(
        "volt_or_vlim_mV",
        OFF_VOLT_OR_VLIM_MV,
        "float32",
        "mV",
        "CCCV charge V; CCDi discharge V-limit",
    ),
    EnsolFieldSlot("current_mA", OFF_CURRENT_MA, "float32", "mA", "CCCV/CCCh/CCDi current"),
    EnsolFieldSlot(
        "time_or_rest_s",
        OFF_TIME_OR_REST_S,
        "float32",
        "s",
        "CC time limit or REST duration",
    ),
    EnsolFieldSlot("voltage_cutoff_mV", OFF_VOLTAGE_CUTOFF_MV, "float32", "mV", "CCDi end V"),
    EnsolFieldSlot("cv_cutoff_mA", OFF_CV_CUTOFF_MA, "float32", "mA", "CCCV CV cutoff"),
    EnsolFieldSlot("loop_count", OFF_LOOP_COUNT, "int32", "", "LOOP repeat count"),
    EnsolFieldSlot("record_dV_mV", OFF_RECORD_DV_MV, "float32", "mV", "sampling ΔV"),
    EnsolFieldSlot("record_time_s", OFF_RECORD_TIME_S, "float32", "s", "sampling Δt"),
    EnsolFieldSlot("dod_percent", OFF_DOD_PERCENT, "float32", "%", "SOC/DOD capacity step"),
    EnsolFieldSlot("cap_mode", OFF_CAP_MODE, "uint8", "", "capacity reference mode"),
    EnsolFieldSlot("cap_ref_step", OFF_CAP_REF_STEP, "uint8", "", "reference step no"),
)


def legacy_offset_aliases() -> dict[str, str]:
    """Map legacy schema/fields.py names to Ensol semantics."""
    return {
        "mode_value@12": "volt_or_vlim_mV",
        "fVref@16": "current_mA",
        "fIref@20": "time_or_rest_s",
        "fEndV@28": "voltage_cutoff_mV",
        "fEndI@32": "cv_cutoff_mA",
        "fEndC@36": "end_capacity (unverified)",
        "loop_target@48": "loop_goto_legacy (corpus uses +564 in Ensol writer)",
        "loop_count@52": "loop_count",
        "bUseActualCapa@512": "see cap_mode@496 in Ensol map (offset shift)",
    }
