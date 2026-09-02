"""Unified schedule classification: verified labels, filename rules, signature labels."""

from __future__ import annotations

from pathlib import Path

from .schedule_filename import ScheduleFilenameMatch, classify_schedule_filename
from .signature_labels import classify_from_signature, load_signature_labels
from .training_labels import classify_with_verified_labels, load_verified_labels

DEFAULT_VERIFIED_PATH = (
    Path(__file__).resolve().parents[1] / "example" / "training" / "verified_filename_labels.json"
)


def classify_schedule(
    path: str | Path,
    data: bytes | None = None,
    *,
    verified_labels: dict[str, str] | Path | str | None = None,
    signature_labels: dict[str, str] | Path | str | None = None,
    use_signature_labels: bool = True,
) -> ScheduleFilenameMatch:
    """Classify a schedule path with optional binary data for signature fallback."""
    verified = verified_labels if verified_labels is not None else load_verified_labels(DEFAULT_VERIFIED_PATH)
    if verified:
        match = classify_with_verified_labels(path, verified)
        if match.matched_rule == "verified_label":
            return match

    match = classify_schedule_filename(path)
    if match.category.value != "unknown":
        return match

    if use_signature_labels and data is not None:
        sig_match = classify_from_signature(path, data, signature_labels)
        if sig_match is not None:
            return sig_match

    return match


def classify_schedule_paths(
    paths: list[str | Path],
    data_list: list[bytes | None] | None = None,
    **kwargs,
) -> list[ScheduleFilenameMatch]:
    if data_list is None:
        return [classify_schedule(path, **kwargs) for path in paths]
    return [
        classify_schedule(path, data, **kwargs)
        for path, data in zip(paths, data_list, strict=True)
    ]
