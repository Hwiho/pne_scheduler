"""Promote high-confidence unknown categorizations into training artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from pne_scheduler.classify.signature_labels import (  # noqa: E402
    SIGNATURE_LABELS_SCHEMA,
    save_signature_labels,
)
from pne_scheduler.classify.training_labels import (  # noqa: E402
    VERIFIED_LABELS_SCHEMA,
    load_verified_labels,
    save_verified_labels,
)

DEFAULT_JSONL = ROOT / "example" / "training" / "unknown_sch_dataset.jsonl"
DEFAULT_SIGNATURE_OUT = ROOT / "example" / "training" / "signature_category_labels.json"
DEFAULT_VERIFIED_OUT = ROOT / "example" / "training" / "verified_filename_labels.json"


def promote_from_jsonl(
    jsonl_path: Path,
    *,
    min_confidence: float = 0.7,
    require_method: str = "binary_signature",
) -> tuple[dict[str, str], dict[str, dict], dict[str, str]]:
    signature_labels: dict[str, str] = {}
    signature_meta: dict[str, dict] = {}
    stem_labels: dict[str, str] = {}

    with jsonl_path.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row.get("confidence", 0) < min_confidence:
                continue
            if require_method and row.get("method") != require_method:
                continue
            category = row.get("suggested_category")
            if not category or category == "unknown":
                continue
            signature = row.get("step_signature")
            if signature:
                signature_labels[signature] = category
                signature_meta[signature] = {
                    "confidence": row["confidence"],
                    "method": row["method"],
                    "votes": row.get("signature_votes", []),
                }
            stem = row.get("stem")
            if stem:
                stem_labels[stem] = category

    return signature_labels, signature_meta, stem_labels


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", type=Path, default=DEFAULT_JSONL)
    parser.add_argument("--min-confidence", type=float, default=0.7)
    parser.add_argument(
        "--signature-out",
        type=Path,
        default=DEFAULT_SIGNATURE_OUT,
    )
    parser.add_argument(
        "--verified-out",
        type=Path,
        default=DEFAULT_VERIFIED_OUT,
        help="Merge stem labels into verified_filename_labels.json",
    )
    parser.add_argument(
        "--merge-verified",
        action="store_true",
        help="Keep existing verified labels; only add new stems",
    )
    args = parser.parse_args()

    sig_labels, sig_meta, stem_labels = promote_from_jsonl(
        args.jsonl,
        min_confidence=args.min_confidence,
    )
    save_signature_labels(
        sig_labels,
        args.signature_out,
        metadata=sig_meta,
        note=(
            f"Promoted from {args.jsonl.name}: confidence>={args.min_confidence}, "
            "method=binary_signature"
        ),
    )

    verified = load_verified_labels(args.verified_out) if args.merge_verified else {}
    verified.update(stem_labels)
    save_verified_labels(
        args.verified_out,
        verified,
        note="Includes high-confidence corpus promotions (signature + stem map)",
    )

    print(f"Wrote {args.signature_out} ({len(sig_labels)} signatures)")
    print(f"Wrote {args.verified_out} ({len(verified)} stems)")
    print("categories:", dict(Counter(sig_labels.values()).most_common(12)))


if __name__ == "__main__":
    main()
