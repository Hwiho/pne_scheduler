from __future__ import annotations

import json
from pathlib import Path

from pne_scheduler.__main__ import main
from pne_scheduler.classify import (
    ScheduleCategory,
    classify_schedule_filename,
    extract_filename_soc_percents,
)
from pne_scheduler.io.sch_parser import parse_schedule_file
from pne_scheduler.protocol import (
    EvidenceKind,
    InferredProtocol,
    explain_schedule,
    format_explanation,
    infer_protocol_from_schedule,
    rest_duration_s,
    voltage_v_from_raw,
)
from pne_scheduler.protocol.explain import step_end_voltage_v

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "example" / "fixtures"
HPPC = FIXTURES / "hppc" / "HPPC_Full range.sch"
QPEED_FULL = (
    FIXTURES
    / "capacheck_zip"
    / "07100766_260617_Set2_bimodal-SJ1300-40um_80C_QPEED-2.sch"
)
QPEED_SOC = (
    FIXTURES
    / "capacheck_zip"
    / "07100766_260713_Set9_QPEED_SOC_setting_BM_SJ1300_6040_C_NCN.sch"
)
RPT_SOC50 = next(FIXTURES.joinpath("capacheck_zip").glob("*RPT_SOC50*"))
FORMATION = FIXTURES / "capacheck_zip" / "3.BM_C1%_FM.sch"


def test_filename_soc_percents_ignore_soc_setting() -> None:
    assert extract_filename_soc_percents("RPT_SOC50 End.sch") == (50,)
    assert extract_filename_soc_percents("FM_SOC30.sch") == (30,)
    assert extract_filename_soc_percents("QPEED_SOC_setting_BM.sch") == ()
    assert extract_filename_soc_percents("HPPC_Full range.sch") == ()


def test_classify_hppc_filename() -> None:
    match = classify_schedule_filename(HPPC)
    assert match.category == ScheduleCategory.HPPC
    assert match.suggested_module == "hppc"
    assert match.filename_soc_percents == ()


def test_infer_protocol_hppc_and_qpeed() -> None:
    hppc = infer_protocol_from_schedule("HPPC_Full range.sch", [], filename_category="hppc")
    assert hppc.protocol == InferredProtocol.HPPC
    qpeed = infer_protocol_from_schedule(
        "set_QPEED-2.sch",
        [],
        filename_category="qpeed",
    )
    assert qpeed.protocol == InferredProtocol.QPEED


def test_voltage_raw_is_millivolts_in_corpus() -> None:
    assert voltage_v_from_raw(3318.0) == 3.318
    assert voltage_v_from_raw(2500.0) == 2.5
    assert voltage_v_from_raw(4.2) == 4.2
    assert voltage_v_from_raw(0.0) is None


def test_hppc_explain_is_full_range_not_soc_staircase() -> None:
    explanation = explain_schedule(parse_schedule_file(HPPC))
    text = format_explanation(explanation).lower()

    assert explanation.family == "hppc"
    assert explanation.confidence >= 0.9
    assert "90/50/10" in text
    assert "does not match" in text or "not an soc 90/50/10" in text
    percents = {c.percent for c in explanation.soc_checkpoints if c.percent not in (0, 100)}
    assert percents == set()
    voltages = {c.voltage_v for c in explanation.soc_checkpoints if c.voltage_v is not None}
    assert 2.5 in voltages
    assert 4.2 in voltages
    assert "inferred for analysis only" in text
    doc = parse_schedule_file(HPPC)
    rest = next(s for s in doc.steps if s.step_type == "REST")
    assert rest_duration_s(rest) == 10800.0


def test_qpeed_full_uses_3318_mv_not_stored_soc_percent() -> None:
    explanation = explain_schedule(parse_schedule_file(QPEED_FULL))
    text = format_explanation(explanation).lower()

    assert explanation.family == "qpeed"
    assert explanation.variant == "full"
    partial = [c for c in explanation.soc_checkpoints if c.source == EvidenceKind.VOLTAGE_SETPOINT]
    assert partial
    assert partial[0].voltage_v == 3.318
    assert partial[0].percent is None
    assert partial[0].count == 13
    assert "3.318" in text
    assert "fendc" in text
    assert "not a stored soc percentage" in text or "percent is unknown" in text
    assert "identical blocks" in text
    assert text.count("1.5c cc charge to 4.200 v") <= 3


def test_qpeed_soc_setting_is_conditioning_not_pulse_train() -> None:
    explanation = explain_schedule(parse_schedule_file(QPEED_SOC))
    text = format_explanation(explanation).lower()

    assert explanation.family == "qpeed"
    assert explanation.variant == "soc_setting"
    assert "conditioning" in text
    named = [c for c in explanation.soc_checkpoints if c.source == EvidenceKind.FILENAME]
    assert named == []
    assert all(c.percent in (0, 100, None) for c in explanation.soc_checkpoints)


def test_rpt_soc50_is_filename_only() -> None:
    explanation = explain_schedule(parse_schedule_file(RPT_SOC50))
    text = format_explanation(explanation).lower()

    assert explanation.family == "rpt"
    named = [c for c in explanation.soc_checkpoints if c.source == EvidenceKind.FILENAME]
    assert [c.percent for c in named] == [50]
    assert "80/50/20" in text
    assert "cannot be confirmed" in text


def test_formation_explain_does_not_invent_soc() -> None:
    explanation = explain_schedule(parse_schedule_file(FORMATION))
    assert explanation.family == "formation"
    assert all(
        c.source != EvidenceKind.FILENAME or c.percent is None
        for c in explanation.soc_checkpoints
    )


def test_cli_explain_text_and_json(tmp_path: Path, capsys) -> None:
    result = main(["explain", str(HPPC)])
    assert result == 0
    out = capsys.readouterr().out
    assert "HPPC" in out
    assert "inferred for analysis only" in out.lower()

    json_path = tmp_path / "hppc.json"
    result = main(["explain", str(QPEED_FULL), "--json", "-o", str(json_path)])
    assert result == 0
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["family"] == "qpeed"
    assert payload["variant"] == "full"
    assert any(
        item["voltage_v"] == 3.318 and item["source"] == "voltage_setpoint"
        for item in payload["soc_checkpoints"]
    )


def test_qpeed_partial_voltage_comes_from_end_v() -> None:
    doc = parse_schedule_file(QPEED_FULL)
    charges = [
        s
        for s in doc.steps
        if s.step_type == "CC_CHG" and step_end_voltage_v(s) == 3.318
    ]
    assert len(charges) == 13
    assert all(s.f_end_c == 0.0 for s in charges)
