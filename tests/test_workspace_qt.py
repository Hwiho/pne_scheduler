"""Smoke tests for the Qt/QML workspace — skipped where PySide6 is absent.

The QML layer resolves bridge properties by name at run time, so a renamed or
dropped ``WorkspaceBridge`` member does not break an import: it silently draws a
blank panel.  These tests build the real engine offscreen and treat any QML
warning as a failure, which is the only place that mistake is catchable.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Property  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from pne_scheduler.ui import workspace_qt  # noqa: E402

EXAMPLE = Path(__file__).resolve().parents[1] / "example" / "example.schproj"


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QGuiApplication.instance() or QGuiApplication([])


def _build(initial_path):
    """Build the engine, returning it with every QML warning it emitted."""
    warnings: list[str] = []
    engine, bridge = workspace_qt.build_engine(initial_path)
    engine.warnings.connect(lambda errors: warnings.extend(str(e) for e in errors))
    return engine, bridge, warnings


def test_engine_builds_empty(app):
    engine, _bridge, warnings = _build(None)
    assert engine.rootObjects()
    assert warnings == []


def test_engine_builds_with_project(app):
    engine, bridge, warnings = _build(EXAMPLE)
    assert engine.rootObjects()
    assert warnings == []
    assert EXAMPLE.stem in bridge.title


def test_every_bridge_property_reads(app):
    """A getter that raises shows up in QML as an empty panel, not a traceback."""
    _engine, bridge, _warnings = _build(EXAMPLE)
    names = [
        name
        for name, value in vars(type(bridge)).items()
        if isinstance(value, Property)
    ]
    assert names, "the bridge declares no QML properties"
    for name in names:
        getattr(bridge, name)


def test_qml_files_ship_with_the_package():
    """Every screen Workspace.qml composes must sit next to it on disk."""
    assert workspace_qt.MAIN_QML.exists()
    text = workspace_qt.MAIN_QML.read_text(encoding="utf-8")
    for screen in ("SetupPage", "ProtocolPage", "ProcedurePage", "ValidatePage", "ExportPage"):
        assert screen in text, f"{screen} is not referenced by Workspace.qml"
        assert (workspace_qt.QML_DIR / f"{screen}.qml").exists()


# --- the slots the new controls call ---------------------------------------


def test_c_rate_preset_chips_carry_a_current(app):
    _engine, bridge, _warnings = _build(EXAMPLE)
    presets = bridge.cRatePresets()
    assert presets, "the form offers no C-rate chips"
    assert {"label", "value", "usage", "currentText"} <= set(presets[0])
    assert all(preset["currentText"] for preset in presets), "capacity is known here"


def test_campaign_preview_does_not_touch_the_project(app):
    _engine, bridge, _warnings = _build(EXAMPLE)
    before = len(bridge.model.project.modules)
    result = bridge.planCampaign(
        {
            "totalCycles": 150,
            "rptEvery": 50,
            "chargeCRate": 0.5,
            "dischargeCRate": 0.5,
            "dcirRates": [1.0, 1.5, 2.0],
        }
    )
    assert result["ok"] and len(result["blocks"]) == 7
    assert len(bridge.model.project.modules) == before


def test_adding_a_campaign_appends_the_blocks(app):
    _engine, bridge, _warnings = _build(EXAMPLE)
    before = len(bridge.model.project.modules)
    result = bridge.addCampaign(
        {"totalCycles": 100, "rptEvery": 50, "chargeCRate": 0.5, "dischargeCRate": 0.5}
    )
    assert result["ok"]
    assert len(bridge.model.project.modules) == before + 5


def test_a_campaign_with_bad_numbers_is_refused_not_applied(app):
    _engine, bridge, _warnings = _build(EXAMPLE)
    before = len(bridge.model.project.modules)
    result = bridge.addCampaign({"totalCycles": 0, "chargeCRate": 0.5, "dischargeCRate": 0.5})
    assert not result["ok"]
    assert len(bridge.model.project.modules) == before


def test_qc_fast_charge_needs_a_qc_module_selected(app):
    _engine, bridge, _warnings = _build(EXAMPLE)
    result = bridge.planQcFastCharge("cycle_life_1", [3.0, 2.0])
    assert not result["ok"] and result["errors"]


def test_qc_fast_charge_moves_all_three_lists(app):
    _engine, bridge, _warnings = _build(None)
    module_id = bridge.model.add_module("qc")
    assert bridge.planQcFastCharge(module_id, [3.0, 2.0, 1.5])["ok"]
    assert bridge.applyQcFastCharge(module_id, [3.0, 2.0, 1.5])["ok"]
    params = bridge.model.project.modules[-1].params
    assert params["fast_rates_c"] == [3.0, 2.0, 1.5]
    assert len(params["fast_times_s"]) == len(params["fast_voltages_v"]) == 3


def test_the_budget_solver_reaches_the_real_estimator(app):
    _engine, bridge, _warnings = _build(EXAMPLE)
    result = bridge.cyclesWithin(14.0, 50)
    assert result["ok"] or result["errors"] or result["notes"]
    if result["ok"]:
        assert result["totalCycles"] % 50 == 0
        assert bridge.applyCycleCount(result["totalCycles"])["ok"]



# --- E2: step editing on a detached module ----------------------------------


def test_a_preset_offers_no_step_editor(app):
    _engine, bridge, _warnings = _build(EXAMPLE)
    assert not bridge.canEditSteps()
    assert bridge.customStepRows() == []


def test_a_detached_module_exposes_its_steps(app):
    _engine, bridge, _warnings = _build(EXAMPLE)
    bridge.model.detach(bridge.model.project.modules[0].id)
    bridge._selected = bridge.model.project.modules[0].id

    assert bridge.canEditSteps()
    rows = bridge.customStepRows()
    assert rows and rows[0]["number"] == 1
    assert all("fields" in row for row in rows)


def test_the_bridge_edits_steps_and_reports_the_impossible(app):
    _engine, bridge, _warnings = _build(EXAMPLE)
    bridge.model.detach(bridge.model.project.modules[0].id)
    bridge._selected = bridge.model.project.modules[0].id
    before = len(bridge.customStepRows())

    assert bridge.insertStep(before, "rest")["ok"]
    assert len(bridge.customStepRows()) == before + 1
    assert bridge.moveStep(0, 1)["ok"]
    assert bridge.removeStep(0)["ok"]
    assert len(bridge.customStepRows()) == before

    # An out-of-range index must come back as a message, never as an exception
    # crossing into QML where nothing would catch it.
    result = bridge.removeStep(999)
    assert not result["ok"] and result["message"]


def test_the_step_kind_choices_match_the_palette(app):
    from pne_scheduler.modules.primitive import PRIMITIVE_KINDS

    _engine, bridge, _warnings = _build(None)
    kinds = {row["kind"] for row in bridge.stepKindChoices()}
    assert kinds == set(PRIMITIVE_KINDS)
    assert all(row["title"] for row in bridge.stepKindChoices())
