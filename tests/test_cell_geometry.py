from pathlib import Path

import pytest

from pne_scheduler.stack.footprint import infer_footprint_from_filename
from pne_scheduler.stack.cell_mode import CellMode, infer_cell_mode_from_filename
from pne_scheduler.stack.capacity import c_rate_from_current, nominal_capacity_mAh
from pne_scheduler.stack.infer import infer_cell_geometry
from pne_scheduler.io.sch_parser import parse_schedule_file

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "example" / "fixtures" / "capacheck_zip"


def test_footprint_3350_from_leading_token() -> None:
    fp = infer_footprint_from_filename("임효진_3350_L.4.36_NP1.08_RPT.sch")
    assert fp is not None
    assert fp.fp_id == "3350"
    assert fp.width_mm == pytest.approx(33.0)
    assert fp.height_mm == pytest.approx(50.0)
    assert fp.area_cm2 == pytest.approx(16.5)


def test_footprint_1818_catalog() -> None:
    fp = infer_footprint_from_filename("test_1818_cycle.sch")
    assert fp is not None
    assert fp.area_cm2 == pytest.approx(3.24)


def test_mono_default_without_multi_keyword() -> None:
    mode = infer_cell_mode_from_filename("07100766_SJ1300_dry_40um_RPT.sch")
    assert mode.mode == CellMode.MONO
    assert mode.reaction_cells_k == 1


def test_multi_from_8m1u() -> None:
    mode = infer_cell_mode_from_filename("stack_8M1U_cycle.sch")
    assert mode.mode == CellMode.MULTI
    assert mode.n_sheets_m == 8
    assert mode.n_unit_stack_u == 1
    assert mode.reaction_cells_k == 8


def test_multi_from_8m2u() -> None:
    mode = infer_cell_mode_from_filename("preset_8M2U_multi.sch")
    assert mode.mode == CellMode.MULTI
    assert mode.n_sheets_m == 8
    assert mode.n_unit_stack_u == 2
    assert mode.reaction_cells_k == 16  # 8M2U → 8×2 양면전극


def test_capacity_scales_with_fp_and_multi() -> None:
    from pne_scheduler.stack.footprint import footprint_from_code

    fp_small = footprint_from_code("1818")
    fp_large = footprint_from_code("3350")
    mono = infer_cell_mode_from_filename("mono_test.sch")
    multi = infer_cell_mode_from_filename("8M2U.sch")

    q_small_mono = nominal_capacity_mAh(footprint=fp_small, cell_mode=mono, l_value=4.3)
    q_large_mono = nominal_capacity_mAh(footprint=fp_large, cell_mode=mono, l_value=4.3)
    q_large_multi = nominal_capacity_mAh(footprint=fp_large, cell_mode=multi, l_value=4.3)

    assert q_large_mono > q_small_mono
    assert q_large_multi > q_large_mono


def test_geometry_pipeline_capacheck_6040() -> None:
    path = FIXTURE_ROOT / "9)Bimodal_SJ1300_6040_NCN_capacheck.sch"
    if not path.exists():
        pytest.skip("fixture missing")
    geo = infer_cell_geometry(path.name, [], [])
    assert geo.stack_level.primary.l_value == pytest.approx(5.0, abs=0.1)
    assert geo.stack_level.primary.source.value == "default_mono"
    assert geo.cell_mode.mode == CellMode.MONO


def test_parse_l436_rpt_file_footprint_and_c_rate() -> None:
    matches = list(FIXTURE_ROOT.glob("*3350_L.4.36*RPT*.sch"))
    assert len(matches) == 1
    path = matches[0]
    doc = parse_schedule_file(path)
    assert doc.geometry.footprint.fp_id == "3350"
    assert doc.geometry.stack_level.primary.l_value == pytest.approx(4.3)
    charge = next(s for s in doc.steps if s.step_type == "CCCV" and s.f_iref > 1000)
    assert charge.c_rate is not None
    assert charge.c_rate == pytest.approx(1.0, abs=0.15)
