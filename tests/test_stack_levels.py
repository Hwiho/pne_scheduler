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


@pytest.mark.parametrize(
    "filename",
    [
        "Cell01_3350_FM.sch",
        "Model3350.sch",
    ],
)
def test_filename_letter_before_digit_is_not_l_level(filename: str) -> None:
    """`_L_EXPLICIT` used to match "L" preceded by any other letter (no token
    boundary), so ordinary names like "Cell01" ("l0") or "Model3350" ("l3")
    were mistaken for an explicit L-level marker."""
    guess = infer_l_from_filename(filename)
    assert guess is None


def test_filename_explicit_l_not_shadowed_by_earlier_letter_digit_run() -> None:
    """A real "L5.0" later in the filename must still be found even though an
    unrelated letter+digit run ("Cell1") appears earlier -- `re.search` only
    returns the leftmost match, so the false positive used to win."""
    guess = infer_l_from_filename("Cell1_multi_L5.0.sch")
    assert guess is not None
    assert guess.l_value == pytest.approx(5.0)


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
    assert charge_steps[0].f_iref == pytest.approx(7.655, rel=0.02)
    assert charge_steps[0].c_rate is not None
