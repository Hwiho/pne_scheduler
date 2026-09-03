from __future__ import annotations

import json
from pathlib import Path

from pne_scheduler.__main__ import main

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "example" / "example.schproj"


def test_build_is_blocked_without_experimental_acknowledgement(
    tmp_path: Path,
    capsys,
) -> None:
    output = tmp_path / "blocked.sch"

    result = main(["build", str(PROJECT), "-o", str(output)])

    assert result == 2
    assert not output.exists()
    assert "equipment-ready" in capsys.readouterr().err


def test_experimental_build_emits_equipment_warning(
    tmp_path: Path,
    capsys,
) -> None:
    output = tmp_path / "experimental.sch"

    result = main(
        [
            "build",
            str(PROJECT),
            "-o",
            str(output),
            "--allow-experimental-output",
        ]
    )

    assert result == 0
    assert output.exists()
    assert len(output.read_bytes()) >= 1760
    manifest_path = output.with_suffix(".sch.manifest.json")
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema"] == "pne_scheduler.sch_validation_manifest/v1"
    assert manifest["writer"] == "experimental_from_scratch"
    assert manifest["equipment_executable"] is False
    assert manifest["template"] is None
    assert manifest["target_profile"]["status"] == "unspecified"
    assert manifest["validation"]["all_passed"] is True
    assert any("0x00010003/1760 header" in warning for warning in manifest["warnings"])
    assert "Do not load or execute" in capsys.readouterr().out


def test_build_removes_output_when_manifest_cannot_be_written(
    tmp_path: Path,
    capsys,
) -> None:
    output = tmp_path / "experimental.sch"
    missing_manifest = tmp_path / "missing" / "validation.json"

    result = main(
        [
            "build",
            str(PROJECT),
            "-o",
            str(output),
            "--manifest",
            str(missing_manifest),
            "--allow-experimental-output",
        ]
    )

    assert result == 2
    assert not output.exists()
    assert not missing_manifest.exists()
    assert "Manifest directory does not exist" in capsys.readouterr().err
