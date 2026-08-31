from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pne_scheduler.__main__ import main
from pne_scheduler.io.template_writer import (
    SchFieldPatch,
    SchPatchPlan,
    apply_sch_patch,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (
    ROOT
    / "example"
    / "fixtures"
    / "capacheck_zip"
    / "9)Bimodal_SJ1300_6040_NCN_capacheck.sch"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _plan(**overrides) -> SchPatchPlan:
    values = {
        "template_sha256": _sha256(TEMPLATE),
        "expected_version": 0x00010003,
        "patches": (SchFieldPatch(step_no=6, field="fEndV", value=3123.0),),
    }
    values.update(overrides)
    return SchPatchPlan(**values)


def test_template_writer_blocks_unverified_field_by_default(tmp_path: Path) -> None:
    output = tmp_path / "blocked.sch"

    with pytest.raises(ValueError, match="not writer-ready"):
        apply_sch_patch(TEMPLATE, _plan(), output)

    assert not output.exists()


def test_template_writer_preserves_every_undeclared_byte(tmp_path: Path) -> None:
    output = tmp_path / "patched.sch"
    result = apply_sch_patch(
        TEMPLATE,
        _plan(),
        output,
        allow_unverified_fields=True,
    )

    before = TEMPLATE.read_bytes()
    after = output.read_bytes()
    changed = [index for index, pair in enumerate(zip(before, after)) if pair[0] != pair[1]]

    assert len(before) == len(after)
    assert changed
    assert set(changed).issubset(set(range(1760 + 5 * 612 + 28, 1760 + 5 * 612 + 32)))
    assert result.report["status"] == "analysis_only"
    assert result.report["header_preserved"] is True
    assert result.report["file_length_preserved"] is True
    assert result.report["warnings"]


def test_template_writer_requires_exact_template_hash(tmp_path: Path) -> None:
    output = tmp_path / "wrong-hash.sch"
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        apply_sch_patch(
            TEMPLATE,
            _plan(template_sha256="0" * 64),
            output,
            allow_unverified_fields=True,
        )


def test_patch_cli_writes_report_and_warns(tmp_path: Path, capsys) -> None:
    output = tmp_path / "patched.sch"
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema": "pne_scheduler.sch_patch/v1",
                "template_sha256": _sha256(TEMPLATE),
                "expected_version": "0x00010003",
                "patches": [{"step_no": 6, "field": "fEndV", "value": 3123.0}],
            }
        ),
        encoding="utf-8",
    )

    result = main(
        [
            "patch-sch",
            str(TEMPLATE),
            str(plan_path),
            "-o",
            str(output),
            "--allow-unverified-fields",
        ]
    )

    assert result == 0
    assert output.exists()
    assert output.with_suffix(".sch.report.json").exists()
    assert "Do not execute" in capsys.readouterr().out
