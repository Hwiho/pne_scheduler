"""Every subpackage must import on its own, from a cold interpreter.

The suite as a whole cannot catch an import cycle: pytest imports the package in
one order, and whichever module happens to load first hides the loop from every
test that follows.  `python tools/compare_pne_units.py` entered through
`pne_scheduler.classify` instead and died on a partially initialized module while
424 tests stayed green, so the check has to be a fresh process per subpackage.

The cycle that prompted this: io/__init__ → lab_header_writer → validate/__init__
→ assb_parser_diff → io.sch_parser → classify → … → io.layout → io/__init__.
`validate/` reads `io/`, so `io/` may not import `validate/` at module scope.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_PARENT = Path(__file__).resolve().parents[2]

SUBPACKAGES = [
    "classify",
    "edit",
    "engine",
    "io",
    "ir",
    "modules",
    "protocol",
    "report",
    "resume",
    "schema",
    "spec",
    "stack",
    "ui",
    "validate",
]


@pytest.mark.parametrize("subpackage", SUBPACKAGES)
def test_subpackage_imports_first(subpackage: str) -> None:
    """A subpackage imported before any sibling must not hit a partial module."""
    result = subprocess.run(
        [sys.executable, "-c", f"import pne_scheduler.{subpackage}"],
        cwd=REPO_PARENT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"import pne_scheduler.{subpackage} failed on its own:\n{result.stderr}"
    )


def test_io_does_not_import_validate_at_module_scope() -> None:
    """The layering rule itself, stated where a reviewer will see it break."""
    offenders = [
        path.relative_to(REPO_PARENT).as_posix()
        for path in (REPO_PARENT / "pne_scheduler" / "io").glob("*.py")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith(("from ..validate", "from pne_scheduler.validate", "import pne_scheduler.validate"))
    ]
    assert not offenders, (
        "io/ must not import validate/ at module scope (validate reads io.sch_parser); "
        f"move it inside the function that needs it: {offenders}"
    )
