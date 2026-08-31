from __future__ import annotations

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
    assert "not equipment-ready" in capsys.readouterr().err


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
    assert "Do not load or execute" in capsys.readouterr().out
