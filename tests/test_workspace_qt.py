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
