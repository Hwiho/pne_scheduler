from __future__ import annotations

import hashlib
import struct
from pathlib import Path

from pne_scheduler.io.sch_binary import read_sch_binary
from pne_scheduler.io.template_writer import SchPatchPlan, apply_sch_patch

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (
    ROOT
    / "example"
    / "fixtures"
    / "capacheck_zip"
    / "9)Bimodal_SJ1300_6040_NCN_capacheck.sch"
)
BASELINE_DIR = ROOT / "example" / "gate_b_pairs" / "_baseline"
PLAN = BASELINE_DIR / "pne02-v612-baseline.patch.json"
BASELINE = BASELINE_DIR / "PNE02_V612_BASELINE_ANALYSIS_ONLY.sch"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_pne02_baseline_is_reproducible_and_structurally_preserved(
    tmp_path: Path,
) -> None:
    regenerated = tmp_path / BASELINE.name
    result = apply_sch_patch(
        TEMPLATE,
        SchPatchPlan.load(PLAN),
        regenerated,
        allow_analysis_output=True,
        allow_unverified_fields=True,
    )

    assert regenerated.read_bytes() == BASELINE.read_bytes()
    assert _sha256(BASELINE) == "8feb6d12184cb76978afc85bfc1c496e3fec244668602b0c2786cccbf8f6e784"
    assert result.report["header_preserved"] is True
    assert result.report["file_length_preserved"] is True
    assert result.report["changed_byte_count"] == 21


def test_pne02_baseline_contains_intended_before_values() -> None:
    document = read_sch_binary(BASELINE)
    steps = {step.step_no: step.record for step in document.steps}

    assert document.sch_version == 0x00010003
    assert document.payload_offset == 1760
    assert document.step_size == 612
    assert document.step_count == 15
    assert struct.unpack_from("<f", steps[1], 20)[0] == 60.0
    assert struct.unpack_from("<f", steps[4], 16)[0] == 10.0
    assert struct.unpack_from("<f", steps[4], 32)[0] == 2.0
    assert struct.unpack_from("<f", steps[4], 340)[0] == 1.0
    assert struct.unpack_from("<f", steps[6], 16)[0] == 10.0
    assert struct.unpack_from("<f", steps[6], 28)[0] == 3000.0
    assert struct.unpack_from("<f", steps[6], 340)[0] == 1.0
    assert struct.unpack_from("<I", steps[14], 52)[0] == 2
    assert struct.unpack_from("<I", steps[14], 564)[0] == 2
