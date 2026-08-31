from __future__ import annotations

import pytest

from pne_scheduler.modules.capacheck import CapacheckModule
from pne_scheduler.modules.cycle_life import CycleLifeModule
from pne_scheduler.modules.formation import FormationModule
from pne_scheduler.modules.rpt import RptModule
from pne_scheduler.protocol import (
    CAPACHECK_INITIAL_C_RATE,
    CAPACHECK_MEASUREMENT_C_RATE,
    CYCLE_DEFAULT_C_RATE,
    FORMATION_C_RATE,
    RPT_DCIR_SOC_FRACTIONS,
    RPT_DISCHARGE_C_RATE,
    infer_protocol_from_schedule,
)
from pne_scheduler.classify import ScheduleCategory, classify_schedule_filename
from pne_scheduler.ir import CellProfile


CELL = CellProfile(nominal_capacity_mAh=80.0, v_max=4.2, v_min=2.5)


def test_formation_default_01c() -> None:
    mod = FormationModule()
    assert mod.charge_c_rate == pytest.approx(FORMATION_C_RATE)


def test_cycle_default_05c() -> None:
    mod = CycleLifeModule()
    assert mod.charge_c_rate == pytest.approx(CYCLE_DEFAULT_C_RATE)
    assert mod.discharge_c_rate == pytest.approx(0.5)


def test_capacheck_expands_01c_then_c3() -> None:
    mod = CapacheckModule(measurement_cycles=1)
    steps = mod.expand(CELL)
    rates = [s.c_rate for s in steps if s.c_rate is not None]
    assert rates[0] == pytest.approx(CAPACHECK_INITIAL_C_RATE)
    assert CAPACHECK_MEASUREMENT_C_RATE in rates


def test_capacheck_double_c3() -> None:
    mod = CapacheckModule(measurement_cycles=2)
    steps = mod.expand(CELL)
    c3 = [s for s in steps if s.c_rate == pytest.approx(CAPACHECK_MEASUREMENT_C_RATE)]
    assert len(c3) >= 4  # charge + discharge × 2


def test_rpt_includes_dcir_at_soc_80_50_20() -> None:
    mod = RptModule()
    assert mod.soc_fractions == pytest.approx(list(RPT_DCIR_SOC_FRACTIONS))
    steps = mod.expand(CELL)
    pulse_labels = [s.label for s in steps if s.label and "DC-IR pulse" in s.label]
    assert len(pulse_labels) == 3
    ref_steps = [s for s in steps if s.c_rate == pytest.approx(RPT_DISCHARGE_C_RATE)]
    assert ref_steps


def test_classify_fm_and_derating() -> None:
    assert classify_schedule_filename("Monocell_FM_L5.0.sch").category == ScheduleCategory.FORMATION
    assert classify_schedule_filename("test_derating.sch").category == ScheduleCategory.CAPACHECK
    assert (
        classify_schedule_filename("0.1C capa_SJ1300.sch").category == ScheduleCategory.CAPACHECK
    )


def test_infer_protocol_cycle_05c() -> None:
    class Step:
        def __init__(self, iref: float, crate: float, label: str = "1C") -> None:
            self.f_iref = iref
            self.c_rate = crate
            self.c_rate_preset = crate
            self.c_rate_label = label
            self.step_type = "CCCV"

    steps = [Step(10000, 0.5, "0.5C"), Step(10000, 0.5, "0.5C")]
    result = infer_protocol_from_schedule("SJ1300_no1_0.5C cycle.sch", steps)
    assert result.protocol.value in ("cycle_life", "insitu_cycle")


def test_infer_protocol_capacheck_pattern() -> None:
    class Step:
        def __init__(self, iref: float, crate: float, label: str) -> None:
            self.f_iref = iref
            self.c_rate = crate
            self.c_rate_preset = crate
            self.c_rate_label = label
            self.step_type = "CCCV"

    steps = [
        Step(2500, 0.1, "0.1C"),
        Step(8300, 1 / 3, "C/3"),
    ]
    result = infer_protocol_from_schedule("test.sch", steps)
    assert result.protocol.value == "capacheck"
