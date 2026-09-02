"""Categorize unknown SCH files per PNE unit and export training artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from pne_scheduler.classify.unknown_categorize import (  # noqa: E402
    apply_verified_labels,
    build_report,
    export_training_csv,
    export_training_jsonl,
    load_verified_labels,
    scan_zip_corpus,
    signature_model_to_json,
)
from pne_scheduler.schema.corpus_paths import default_corpus_zip_map  # noqa: E402

DEFAULT_OUT = ROOT / "planning" / "UNKNOWN_SCH_CATEGORIZATION.json"
TRAINING_DIR = ROOT / "example" / "training"
VERIFIED_PATH = TRAINING_DIR / "verified_filename_labels.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--units",
        nargs="*",
        help="PNE units to scan (default: all corpus zips)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUT,
        help="Summary JSON report path",
    )
    parser.add_argument(
        "--training-dir",
        type=Path,
        default=TRAINING_DIR,
        help="Directory for JSONL/CSV/signature model exports",
    )
    parser.add_argument(
        "--verified-labels",
        type=Path,
        default=VERIFIED_PATH,
        help="Optional verified label JSON to overlay on exports",
    )
    args = parser.parse_args()

    zip_map = default_corpus_zip_map(args.units or None)
    records, signature_model = scan_zip_corpus(zip_map)
    verified = load_verified_labels(args.verified_labels)
    if verified:
        records = apply_verified_labels(records, verified)

    report = build_report(zip_map, records=records, signature_model=signature_model)
    if verified:
        report["verified_labels_applied"] = len(verified)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    training_dir = args.training_dir
    export_training_jsonl(records, training_dir / "unknown_sch_dataset.jsonl")
    export_training_csv(records, training_dir / "unknown_sch_dataset.csv")
    (training_dir / "signature_category_map.json").write_text(
        json.dumps(
            {
                "schema": "pne_scheduler.signature_category_map/v1",
                "description": "Step-signature votes from classified files; reuse for auto-labeling.",
                "signatures": signature_model_to_json(signature_model),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (training_dir / "rule_promotion_candidates.json").write_text(
        json.dumps(
            {
                "schema": "pne_scheduler.rule_promotion_candidates/v1",
                "candidates": report.get("rule_promotion_candidates", []),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Wrote {args.output}")
    print(f"Wrote {training_dir / 'unknown_sch_dataset.jsonl'}")
    print(f"Wrote {training_dir / 'unknown_sch_dataset.csv'}")
    print(
        "unknown:",
        report["total_unknown"],
        "| resolved:",
        report["resolved_pct"],
        "%",
        "| high confidence:",
        report["high_confidence_pct"],
        "%",
    )
    for unit, detail in report["per_unit"].items():
        print(
            unit,
            detail["unknown_count"],
            "unknown →",
            detail["resolved_suggestions"],
            "suggested,",
            detail["high_confidence"],
            "high-conf",
        )


if __name__ == "__main__":
    main()
