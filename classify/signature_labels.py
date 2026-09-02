"""Step-signature labels promoted from high-confidence corpus mining."""

from __future__ import annotations

import json
from pathlib import Path

from .schedule_filename import (
    CATEGORY_TO_MODULE,
    ScheduleCategory,
    ScheduleFilenameMatch,
)
from .sch_binary_profile import step_signature_from_data

SIGNATURE_LABELS_SCHEMA = "pne_scheduler.signature_category_labels/v1"
DEFAULT_SIGNATURE_LABELS_PATH = (
    Path(__file__).resolve().parents[1] / "example" / "training" / "signature_category_labels.json"
)


def load_signature_labels(path: Path | str | None = None) -> dict[str, str]:
    resolved = Path(path) if path is not None else DEFAULT_SIGNATURE_LABELS_PATH
    if not resolved.is_file():
        return {}
    data = json.loads(resolved.read_text(encoding="utf-8"))
    if isinstance(data, dict) and data.get("schema") == SIGNATURE_LABELS_SCHEMA:
        return {str(k): str(v) for k, v in data.get("labels", {}).items()}
    if isinstance(data, dict) and "labels" in data:
        return {str(k): str(v) for k, v in data["labels"].items()}
    raise ValueError(f"unsupported signature label format: {resolved}")


def save_signature_labels(
    labels: dict[str, str],
    path: Path | str | None = None,
    *,
    metadata: dict[str, dict] | None = None,
    note: str = "",
) -> None:
    resolved = Path(path) if path is not None else DEFAULT_SIGNATURE_LABELS_PATH
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": SIGNATURE_LABELS_SCHEMA,
        "note": note,
        "labels": dict(sorted(labels.items())),
        "metadata": metadata or {},
    }
    resolved.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def classify_from_signature(
    path: str | Path,
    data: bytes,
    labels: dict[str, str] | Path | str | None = None,
) -> ScheduleFilenameMatch | None:
    """Classify using promoted step-signature labels when filename rules miss."""
    label_map = (
        load_signature_labels(labels)
        if isinstance(labels, (str, Path)) or labels is None
        else labels
    )
    if not label_map:
        return None
    signature = step_signature_from_data(data)
    if not signature or signature not in label_map:
        return None
    resolved = Path(path)
    category = ScheduleCategory(label_map[signature])
    return ScheduleFilenameMatch(
        path=resolved,
        category=category,
        matched_rule="signature_label",
        suggested_module=CATEGORY_TO_MODULE.get(category, "unknown"),
    )
