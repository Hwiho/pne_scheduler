from __future__ import annotations

from pne_scheduler.ir import CellProfile, ModuleNode, ScheduleProject
from pne_scheduler.validate.preflight import validate_project


def _project(module_type: str, params: dict, *, max_current_mA: float = 2000.0) -> ScheduleProject:
    return ScheduleProject(
        name="preflight",
        cell_profile=CellProfile(80.0, 4.2, 2.5, max_current_mA=max_current_mA),
        modules=[ModuleNode("m1", module_type, params)],
    )


def test_preview_allows_software_checked_candidate_with_warning() -> None:
    result = validate_project(_project("qpeed", {"variant": "full"}))

    assert result.passed
    assert any(issue.code == "MODULE_TRUST" for issue in result.warnings)
    assert any(issue.code == "VOLTAGE_HEADROOM" for issue in result.warnings)


def test_production_blocks_unverified_pattern() -> None:
    result = validate_project(
        _project("qpeed", {"variant": "soc_setting"}),
        purpose="production",
    )

    assert not result.passed
    assert any(issue.code == "MODULE_TRUST" for issue in result.errors)
    assert any(issue.code == "DOD_UNVERIFIED" for issue in result.errors)


def test_current_limit_is_a_hard_error() -> None:
    result = validate_project(
        _project("qpeed", {"variant": "full"}, max_current_mA=500.0)
    )

    assert any(issue.code == "CURRENT_LIMIT" for issue in result.errors)


def test_dod_range_is_a_hard_error() -> None:
    result = validate_project(
        _project(
            "qpeed",
            {"variant": "soc_setting", "soc_dod_percent": 101.0},
        )
    )

    assert any(issue.code == "DOD_RANGE" for issue in result.errors)
