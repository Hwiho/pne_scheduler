from __future__ import annotations

from pathlib import Path

import pytest

from pne_scheduler.classify import QpeedVariant, ScheduleCategory, classify_schedule_filename

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "example" / "fixtures" / "capacheck_zip"


@pytest.mark.parametrize(
    ("filename", "expected", "qpeed_variant"),
    [
        ("9)Bimodal_SJ1300_6040_NCN_capacheck.sch", ScheduleCategory.CAPACHECK, None),
        ("3.BM_C1%_FM.sch", ScheduleCategory.FORMATION, None),
        ("set3_bimodal-30_45℃ 0.5C cycle.sch", ScheduleCategory.CYCLE_LIFE, None),
        ("00207966_260803_727도매석_Set8_45℃ Cycle.sch", ScheduleCategory.CYCLE_LIFE, None),
        ("07100766_260511_SJ1300_dry_40um_RPT_500cycle.sch", ScheduleCategory.RPT, None),
        (
            "임효진_3350_L.4.36_NP1.08_RPT_SOC50 End_챔버시험용.sch",
            ScheduleCategory.RPT,
            None,
        ),
        (
            "07100766_260713_Set9_QPEED_SOC_setting_BM_SJ1300_6040_C_NCN.sch",
            ScheduleCategory.QPEED,
            QpeedVariant.SOC_SETTING,
        ),
        (
            "07100766_260617_Set2_bimodal-SJ1300-40um_80C_QPEED-2.sch",
            ScheduleCategory.QPEED,
            QpeedVariant.FULL,
        ),
        ("HPPC_Full range.sch", ScheduleCategory.HPPC, None),
        ("0.05C+64.50mAh rate.sch", ScheduleCategory.RATE_TEST, None),
        ("0.05C+60.75mAh rate+Cycle.sch", ScheduleCategory.RATE_TEST, None),
        ("0.33C SOC30 setting.sch", ScheduleCategory.SOC_SETTING, None),
        ("ratetest_100mAh.sch", ScheduleCategory.RATE_TEST, None),
        ("[10.0] 0.1C RATE_se200.sch", ScheduleCategory.RATE_TEST, None),
        ("[10.0] 0.33C cycle_se200.sch", ScheduleCategory.CYCLE_LIFE, None),
        ("0.1C safety4-DISCHARGE.sch", ScheduleCategory.DISCHARGE, None),
        ("00217475_260210_OCV_rest.sch", ScheduleCategory.OCV, None),
        ("221011 Dry EIS cell.sch", ScheduleCategory.EIS, None),
        ("220526-LDJ-A334-STORAGE CAPA CHECK.sch", ScheduleCategory.STORAGE, None),
        ("07100395_260826_260821_tilt_asympads.sch", ScheduleCategory.DOE, None),
        ("0.1mAcm2_SoC20_4.3based.sch", ScheduleCategory.CHARGE, None),
        ("10min_rest_hold.sch", ScheduleCategory.REST, None),
        ("Form_RPT_100mAh_DCIR1.5C.sch", ScheduleCategory.RPT, None),
        ("3350 mono_L4.27_Form.sch", ScheduleCategory.FORMATION, None),
        ("07004627_260713_3350_Aging_Set 1_SOC100_Form.sch", ScheduleCategory.FORMATION, None),
        ("0.9Ah_FM.sch", ScheduleCategory.FORMATION, None),
        ("250916_Sample_3350_Formation+RC+HPPC+CC_Rev1.sch", ScheduleCategory.HPPC, None),
        ("07100395_260727_corner_50um_form_cycle.sch", ScheduleCategory.CYCLE_LIFE, None),
        ("07000872_250325_JHY_0_L1_L6_initial_check_28.sch", ScheduleCategory.CAPACHECK, None),
        ("00215570_230704_set3_20nmAg_2C.sch", ScheduleCategory.RATE_TEST, None),
        ("07004541_A 250410 proterial_SE binder aging 100oC_C.sch", ScheduleCategory.STORAGE, None),
        ("00219150_230407_stack_set15_1_mono preheating 1min.sch", ScheduleCategory.REST, None),
        ("00214700_221122_Set03-3_0'1C DCH for XRM.sch", ScheduleCategory.DISCHARGE, None),
        ("00215540_250116_Stack_L6_breathing_swelling_1.sch", ScheduleCategory.CYCLE_LIFE, None),
        ("07004581_260710_0.33C_SOC30_setting_활성화3MPa.sch", ScheduleCategory.SOC_SETTING, None),
        ("GS SOC50 pulse test.sch", ScheduleCategory.HPPC, None),
        ("3350_gitt_test.sch", ScheduleCategory.GITT, None),
    ],
)
def test_classify_capacheck_fixtures(
    filename: str,
    expected: ScheduleCategory,
    qpeed_variant: QpeedVariant | None,
) -> None:
    match = classify_schedule_filename(FIXTURE_ROOT / filename)
    assert match.category == expected
    assert match.qpeed_variant == qpeed_variant


def test_qpeed_soc_setting_is_sub_experiment_of_qpeed() -> None:
    name = "07100766_260713_Set9_QPEED_SOC_setting_BM.sch"
    match = classify_schedule_filename(name)
    assert match.category == ScheduleCategory.QPEED
    assert match.qpeed_variant == QpeedVariant.SOC_SETTING
    assert match.suggested_module == "qpeed"
    assert match.is_qpeed_soc_setting


def test_standalone_soc_setting_category() -> None:
    match = classify_schedule_filename("0.33C SOC30 setting.sch")
    assert match.category == ScheduleCategory.SOC_SETTING
    assert match.suggested_module == "soc_setting"
    assert match.is_qpeed_soc_setting


def test_hppc_before_cycle_keyword() -> None:
    match = classify_schedule_filename(
        "00207966_260121_45도 Full HPPC_before cycle_L4.3.sch"
    )
    assert match.category == ScheduleCategory.HPPC


def test_dry_cell_maps_to_cycle_with_dry_variant() -> None:
    match = classify_schedule_filename("00223213_220930 Set01 Dry C-LA.sch")
    assert match.category == ScheduleCategory.CYCLE_LIFE
    assert match.protocol_variant.value == "dry"


def test_dcir_in_rpt_stays_rpt() -> None:
    match = classify_schedule_filename("260821_Form_RPT_Cycle_100mAh_DCIR1.5C_84.2mAh.sch")
    assert match.category == ScheduleCategory.RPT
