from pne_scheduler.modules import FormationModule


def test_formation_module_is_available_from_public_package() -> None:
    assert FormationModule.__name__ == "FormationModule"
