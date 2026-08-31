from pathlib import Path

import pytest

from pne_scheduler.io.sch_parser import parse_schedule_file
from pne_scheduler.stack import infer_l_from_filename, l_from_fvref

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "example" / "fixtures" / "capacheck_zip"


def test_filename_l4_36_explicit() -> None:
    guess = infer_l_from_filename("임효진_3350_L.4.36_NP1.08_RPT_SOC50.sch")
    assert guess is not None
    assert guess.l_value == pytest.approx(4.3)


def test_filename_explicit_l5() -> None:
    guess = infer_l_from_filename("test_3350_L5.0_cycle.sch")
    assert guess is not None
    assert guess.l_value == pytest.approx(5.0)


def test_filename_6040_is_not_l_level() -> None:
    guess = infer_l_from_filename("9)Bimodal_SJ1300_6040_NCN_capacheck.sch")
    assert guess is None


def test_fvref_inference_l65_from_qpeed() -> None:
    guess = l_from_fvref(36.293)
    assert guess is not None
    assert guess.l_value == pytest.approx(6.5, abs=0.2)


def test_parse_capacheck_fixture_has_c_rate() -> None:
    path = FIXTURE_ROOT / "9)Bimodal_SJ1300_6040_NCN_capacheck.sch"
    if not path.exists():
        pytest.skip("fixture not extracted")
    doc = parse_schedule_file(path)
    assert doc.classification.category.value == "capacheck"
    assert doc.stack_level.primary.l_value == pytest.approx(5.0, abs=0.1)
    assert doc.stack_level.primary.source.value == "default_mono"
    assert doc.geometry.footprint.fp_id == "3350"  # default when not in name
    charge_steps = [s for s in doc.steps if s.step_type == "CCCV" and s.f_iref > 0]
    assert charge_steps
    assert charge_steps[0].c_rate is not None
    assert charge_steps[0].c_rate == pytest.approx(0.86, abs=0.1)
