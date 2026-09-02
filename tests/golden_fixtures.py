"""Locked golden fixtures from user intake (example/gate_b_export/GOLDEN_FIXTURE_INTAKE.md)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCKED_PATH = ROOT / "planning" / "GOLDEN_FIXTURES_LOCKED.json"
FIXTURE_ROOT = ROOT / "example" / "fixtures"


def load_locked_golden_fixtures() -> dict:
    return json.loads(LOCKED_PATH.read_text(encoding="utf-8"))


def locked_fixture_paths() -> list[Path]:
    payload = load_locked_golden_fixtures()
    paths: list[Path] = []
    for item in payload["selected"]:
        path = FIXTURE_ROOT / Path(item["path"])
        paths.append(path)
    return paths
