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
    assert match.filename_soc_percents == ()


def test_hppc_filename_is_hppc_not_unknown() -> None:
    match = classify_schedule_filename("HPPC_Full range.sch")
    assert match.category == ScheduleCategory.HPPC
    assert match.suggested_module == "hppc"


def test_filename_soc_percent_from_rpt_name() -> None:
    match = classify_schedule_filename("임효진_3350_L.4.36_NP1.08_RPT_SOC50 End.sch")
    assert match.category == ScheduleCategory.RPT
    assert match.filename_soc_percents == (50,)
