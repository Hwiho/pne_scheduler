from pne_scheduler.modules.base import list_module_types
from pne_scheduler.ui.flow_theme import (
    CARD_HEIGHT,
    CARD_WIDTH,
    module_style,
    rounded_rect_points,
    validate_module_styles,
)


def test_every_registered_module_has_a_visual_style() -> None:
    assert validate_module_styles() == ()
    for module_type in list_module_types():
        style = module_style(module_type)
        assert style.icon
        assert style.title
        assert style.fill.startswith("#")


def test_rounded_card_geometry_is_closed_and_inset() -> None:
    points = rounded_rect_points(10, 20, 10 + CARD_WIDTH, 20 + CARD_HEIGHT)
    assert points[0] > 10
    assert points[1] == 20
    assert points[-2] == points[0]
    assert points[-1] == points[1]
    assert len(points) >= 24
