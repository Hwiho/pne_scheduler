"""Visual language for flow-editor module cards."""

from __future__ import annotations

from dataclasses import dataclass

from ..modules.base import list_module_types

CARD_WIDTH = 232
CARD_HEIGHT = 128
CARD_RADIUS = 22
CARD_GAP_X = 76
CARD_GAP_Y = 52
PORT_RADIUS = 8


@dataclass(frozen=True, slots=True)
class ModuleStyle:
    title: str
    icon: str
    fill: str
    fill_selected: str
    accent: str
    ink: str
    mute: str


DEFAULT_STYLE = ModuleStyle(
    title="Module",
    icon="◆",
    fill="#f4efe8",
    fill_selected="#fff7ea",
    accent="#7a6452",
    ink="#3b2f27",
    mute="#7c6b5d",
)

MODULE_STYLES: dict[str, ModuleStyle] = {
    "formation": ModuleStyle(
        "Formation",
        "🌱",
        "#ffe4d6",
        "#fff0e6",
        "#e08a5d",
        "#5a321c",
        "#a06646",
    ),
    "cycle_life": ModuleStyle(
        "Cycle life",
        "🔁",
        "#eadcff",
        "#f4ecff",
        "#8b6cc9",
        "#3d2a63",
        "#6d5b8e",
    ),
    "insitu_cycle": ModuleStyle(
        "In-situ cycle",
        "🔬",
        "#d9f6ea",
        "#e9fbf3",
        "#3fa37a",
        "#1d4d3a",
        "#4d7d66",
    ),
    "capacheck": ModuleStyle(
        "Capacheck",
        "📏",
        "#fff1b8",
        "#fff8d6",
        "#d4a017",
        "#5c4300",
        "#8a6a1a",
    ),
    "rpt": ModuleStyle(
        "RPT",
        "📊",
        "#d7e9ff",
        "#eaf3ff",
        "#4f8fd0",
        "#1d3f66",
        "#4d6d91",
    ),
    "dcir": ModuleStyle(
        "DC-IR",
        "⚡",
        "#ffe1c4",
        "#fff0de",
        "#e0893c",
        "#5a3410",
        "#8a5a2b",
    ),
    "hppc": ModuleStyle(
        "HPPC",
        "💗",
        "#ffd9e8",
        "#ffebf3",
        "#d96b98",
        "#5a243c",
        "#8d5670",
    ),
    "qpeed": ModuleStyle(
        "QPEED",
        "🚀",
        "#e5f7c4",
        "#f2fbd9",
        "#7aa31f",
        "#33470d",
        "#5d7340",
    ),
    "rest": ModuleStyle(
        "Rest",
        "💤",
        "#e7eef8",
        "#f4f7fc",
        "#6b84a8",
        "#24344c",
        "#5b6c82",
    ),
}


def module_style(module_type: str) -> ModuleStyle:
    return MODULE_STYLES.get(module_type, DEFAULT_STYLE)


def rounded_rect_points(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float = CARD_RADIUS,
) -> tuple[float, ...]:
    radius = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
    return (
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
        x1 + radius,
        y1,
    )


def validate_module_styles() -> tuple[str, ...]:
    missing = [
        module_type
        for module_type in list_module_types()
        if module_type not in MODULE_STYLES
    ]
    return tuple(f"missing style: {name}" for name in missing)
