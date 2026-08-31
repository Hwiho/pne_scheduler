"""Build the checked-in SCH fixture structure and provenance catalog."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pne_scheduler.classify import classify_schedule_filename
from pne_scheduler.io.sch_binary import read_sch_binary

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "example" / "fixtures"
OUTPUT_PATH = FIXTURE_ROOT / "catalog.json"

EXPECTED_ARCHIVE_HASHES = {
    "9)Bimodal_SJ1300_6040_NCN_capacheck.zip": (
        "6c7e2d366f6ddf308db1009ae4244635538f6a0904253a431fe1fb3b3a44e37a"
    ),
    "sch.zip": "1b0ec17c4feaa3cba67e1a525e8e000dfbd13f5f6637176a1492e7625efd83fb",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _equipment_provenance(relative_path: str, filename: str) -> dict[str, str | None]:
    normalized_name = filename.casefold()

    if relative_path.startswith("sch_lab_zip/"):
        confirmed = "1ah" in normalized_name or (
            "qc" in normalized_name and "1n1q" in normalized_name
        )
        qc_cycle = "qc" in normalized_name and "cycle" in normalized_name
        if confirmed or qc_cycle:
            return {
                "equipment": "PNE16",
                "rating": "6A",
                "confidence": "confirmed",
                "source": "user_confirmed",
                "evidence": (
                    "The user confirmed this classification for the current fixture corpus only."
                ),
            }
        return {
            "equipment": "PNE16",
            "rating": "6A",
            "confidence": "probable",
            "source": "user_attributed",
            "evidence": (
                "The user attributed the current sch.zip corpus to PNE16, with uncertainty."
            ),
        }

    if relative_path.startswith("capacheck_zip/") and "qpeed" in normalized_name:
        return {
            "equipment": "PNE02",
            "rating": "500mA",
            "confidence": "probable",
            "source": "user_attributed",
            "evidence": (
                "The user attributed QPEED fixtures in the current corpus to PNE02, "
                "with uncertainty."
            ),
        }

    return {
        "equipment": None,
        "rating": None,
        "confidence": "unknown",
        "source": "unassigned",
        "evidence": "No equipment identity is encoded in the SCH file or confirmed by the user.",
    }


def build_catalog() -> dict:
    archive_root = ROOT / "example" / "archives"
    for archive_name, expected_hash in EXPECTED_ARCHIVE_HASHES.items():
        actual_hash = _sha256(archive_root / archive_name)
        if actual_hash != expected_hash:
            raise ValueError(
                f"Archive {archive_name} changed; review provenance before rebuilding the catalog"
            )

    fixtures = []
    for path in sorted(FIXTURE_ROOT.rglob("*.sch")):
        document = read_sch_binary(path)
        relative_path = path.relative_to(FIXTURE_ROOT).as_posix()
        fixtures.append(
            {
                "path": relative_path,
                "sha256": _sha256(path),
                "size": path.stat().st_size,
                "category": classify_schedule_filename(path.name).category.value,
                "layout": {
                    "version": f"0x{document.sch_version:08x}",
                    "payload_offset": document.payload_offset,
                    "step_size": document.step_size,
                    "step_count": document.step_count,
                },
                "equipment_provenance": _equipment_provenance(
                    relative_path,
                    path.name,
                ),
            }
        )

    return {
        "schema": "pne_scheduler.fixture_catalog/v1",
        "scope": (
            "Equipment provenance applies only to these exact checked-in fixtures. "
            "It must not be inferred for future files from filenames or protocol names."
        ),
        "equipment_summary": {
            "PNE02": "500mA cycler; probable attribution for current QPEED fixtures",
            "PNE16": "6A cycler; user attribution for the current sch.zip corpus",
            "PNE21": "100mA cycler; no fixture currently identified",
            "PNE22": "100mA cycler; no fixture currently identified",
        },
        "fixture_count": len(fixtures),
        "fixtures": fixtures,
    }


def main() -> None:
    catalog = build_catalog()
    OUTPUT_PATH.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(catalog['fixtures'])} fixtures to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
