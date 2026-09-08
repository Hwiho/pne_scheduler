from __future__ import annotations

from pne_scheduler.modules.base import list_module_types
from pne_scheduler.modules.catalog import (
    get_module_spec,
    validate_module_catalog,
    visible_module_types,
)


def test_catalog_covers_registry_and_hides_internal_probes() -> None:
    assert validate_module_catalog(list_module_types()) == ()
    visible = visible_module_types()
    assert "qc" in visible
    assert "qpeed" in visible
    assert "smoke_writer_probe" not in visible
    assert get_module_spec("qpeed").variants == (
        "full",
        "soc_setting",
        "legacy_pulse",
    )
