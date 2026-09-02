"""Apply human-verified filename labels on top of the rule-based classifier."""

from __future__ import annotations

import json
from pathlib import Path

from .schedule_filename import (
    CATEGORY_TO_MODULE,
    ScheduleCategory,
    ScheduleFilenameMatch,
    classify_schedule_filename,
)

VERIFIED_LABELS_SCHEMA = "pne_scheduler.verified_filename_labels/v1"


def load_verified_labels(path: Path | str) -> dict[str, str]:
    """Load ``stem → category`` map from a JSON review file."""
    resolved = Path(path)
    if not resolved.is_file():
        return {}
    data = json.loads(resolved.read_text(encoding="utf-8"))
    if isinstance(data, dict) and data.get("schema") == VERIFIED_LABELS_SCHEMA:
        labels = data.get("labels", {})
        return {str(k): str(v) for k, v in labels.items()}
    if isinstance(data, dict) and "labels" in data:
        return {str(k): str(v) for k, v in data["labels"].items()}
    if isinstance(data, dict):
        return {str(k): str(v) for k, v in data.items()}
    raise ValueError(f"unsupported verified label format: {resolved}")


def save_verified_labels(path: Path | str, labels: dict[str, str], *, note: str = "") -> None:
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": VERIFIED_LABELS_SCHEMA,
        "note": note,
        "labels": dict(sorted(labels.items())),
    }
    resolved.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def classify_with_verified_labels(
    path: str | Path,
    verified: dict[str, str] | Path | str | None = None,
) -> ScheduleFilenameMatch:
    """Classify a path, preferring verified human labels when present."""
    if verified is None:
        return classify_schedule_filename(path)
    label_map = load_verified_labels(verified) if isinstance(verified, (str, Path)) else verified
    resolved = Path(path)
    stem = resolved.name
    if stem not in label_map:
        return classify_schedule_filename(path)
    category = ScheduleCategory(label_map[stem])
    return ScheduleFilenameMatch(
        path=resolved,
        category=category,
        matched_rule="verified_label",
        suggested_module=CATEGORY_TO_MODULE.get(category, "unknown"),
    )
