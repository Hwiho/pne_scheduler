"""Step-type family helpers for Gate D fixture vs module compares."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from ..ir.step_intent import StepIntent
from ..io.sch_parser import parse_schedule_file

ROOT = Path(__file__).resolve().parents[1]
LOCKED_PATH = ROOT / "planning" / "GOLDEN_FIXTURES_LOCKED.json"

# Normalize parser TYPE_NAMES / IR step_type into a small family vocabulary.
_FAMILY_ALIASES: dict[str, str] = {
    "charge": "charge",
    "discharge": "discharge",
    "rest": "rest",
    "ocv": "ocv",
    "impedance": "impedance",
    "pattern": "pattern",
    "balance": "balance",
    "cycle": "cycle",
    "loop": "loop",
    "end": "end",
    "CCCV": "charge",
    "CC_CHG": "charge",
    "CHARGE": "charge",
    "CC_DCHG": "discharge",
    "DISCHARGE": "discharge",
    "REST": "rest",
    "OCV": "ocv",
    "IMPEDANCE": "impedance",
    "PATTERN": "pattern",
    "BALANCE": "balance",
    "CYCLE": "cycle",
    "LOOP": "loop",
    "END": "end",
}


def normalize_step_type(name: str) -> str:
    return _FAMILY_ALIASES.get(name, name.lower())


def intent_type_family(intents: Iterable[StepIntent]) -> frozenset[str]:
    return frozenset(normalize_step_type(intent.step_type) for intent in intents)


def fixture_type_family(path: Path) -> frozenset[str]:
    doc = parse_schedule_file(path)
    return frozenset(normalize_step_type(step.step_type) for step in doc.steps)


def load_golden_by_id(golden_id: str) -> dict:
    payload = json.loads(LOCKED_PATH.read_text(encoding="utf-8"))
    for item in payload["selected"]:
        if item["id"] == golden_id:
            return item
    raise KeyError(f"Unknown golden id: {golden_id}")
