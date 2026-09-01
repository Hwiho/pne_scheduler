"""Vendored ASSB `.sch` parser constants (ASSB_Analyzer_dev).

Source: https://github.com/lgn0427-dev/ASSB_Analyzer_dev
File: assb_analyzer/io/pne_converter.py (SCH sections, 2026-09 snapshot)

Kept in-tree so pne_scheduler does not depend on an external assb_analyzer install.
"""

from __future__ import annotations

SCH_STEP_TYPE_REST = 3
SCH_STEP_TYPE_CCCV = 0x0101
SCH_STEP_TYPE_CC_CHARGE = 0x0201
SCH_STEP_TYPE_CC_DISCHARGE = 0x0202
SCH_STEP_TYPE_END = 6
SCH_STEP_TYPE_CYCLE_MARKER = 7
SCH_STEP_TYPE_LOOP = 8

SCH_STEP_TYPES = frozenset(
    {
        SCH_STEP_TYPE_REST,
        SCH_STEP_TYPE_CCCV,
        SCH_STEP_TYPE_CC_CHARGE,
        SCH_STEP_TYPE_CC_DISCHARGE,
        SCH_STEP_TYPE_END,
        SCH_STEP_TYPE_CYCLE_MARKER,
        SCH_STEP_TYPE_LOOP,
    }
)

SCH_STEP_SIZE_CANDIDATES = (612, 696)
SCH_FILE_VERSION_V3 = 0x00010003
SCH_LAYOUT_V3_612 = (SCH_FILE_VERSION_V3, 612)

SCH_REFERENCE_CURRENT_OFFSET = 16
SCH_END_CURRENT_OFFSET = 32

# ASSB name -> (dtype, byte offset) for 0x00010003 / 612 only.
SCH_V0X00010003_STEP612_CONDITION_FIELDS: dict[str, tuple[str, int]] = {
    "fEndC": ("float32", 36),
    "nLoopInfoEndSocGoto": ("uint32", 80),
    "nGotoStepID": ("uint32", 84),
    "fSocRate": ("float32", 384),
    "fMaxCapacity": ("float32", 412),
    "bUseActualCapa": ("uint8", 496),
    "bUseDataStepNo": ("uint8", 497),
}

SCH_CONDITION_CANDIDATE_FIELDS_BY_LAYOUT: dict[
    tuple[int, int], dict[str, tuple[str, int]]
] = {
    SCH_LAYOUT_V3_612: SCH_V0X00010003_STEP612_CONDITION_FIELDS,
}

SCH_DCIR_SOC_RULES_SCHEMA = "assb.sch-dcir-soc-rules/v1"
SCH_DCIR_SOC_RULES_LAYOUT_POLICY = "pne-sch-v0x00010003-step612-soc-v1"
SCH_DCIR_SOC_RULES_MAPPING_POLICY = "cts_step_no_equals_sch_step_no_plus_1_v1"
SCH_CURRENT_CONDITION_MAPPING_POLICY = (
    "cts_step_no_equals_sch_step_no_plus_1_type_mode_verified_v1"
)
