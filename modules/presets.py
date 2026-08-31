"""Named experiment presets that fill a module's charge/discharge/rest recipe."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .recipe import ModuleRecipe, RecipeUnit, charge, discharge, end_step, rest

C_THIRD = 1.0 / 3.0


@dataclass(frozen=True, slots=True)
class PresetSpec:
    key: str
    module_type: str
    title: str
    detail: str
    builder: Callable[..., ModuleRecipe]


def _qpeed_condition(
    *,
    c_rate: float,
    rest_s: float,
    v_min: float,
    v_max: float,
    set_voltage_v: float | None,
    initial_rest_s: float = 600.0,
) -> list[RecipeUnit]:
    units: list[RecipeUnit] = []
    if initial_rest_s > 0:
        units.append(rest(initial_rest_s, "initial rest"))
    last_charge = (
        charge(c_rate=c_rate, mode="CC", end_voltage_v=set_voltage_v, label="SOC set")
        if set_voltage_v is not None
        else charge(c_rate=c_rate, mode="CC", end_voltage_v=v_max, label="SOC-setting charge")
    )
    units.extend(
        [
            discharge(c_rate=c_rate, end_voltage_v=v_min, label="empty"),
            rest(rest_s),
            charge(
                c_rate=c_rate,
                mode="CCCV",
                end_voltage_v=v_max,
                cv_cutoff_c_rate=0.05,
                label="capacity check",
            ),
            rest(rest_s),
            discharge(c_rate=c_rate, end_voltage_v=v_min, label="empty"),
            rest(rest_s),
            last_charge,
            rest(rest_s),
        ]
    )
    return units


def build_qpeed_full_3318(
    *,
    soc_voltage_v: float = 3.318,
    condition_c_rate: float = 1.0,
    pulse_c_rate: float = 1.5,
    rest_s: float = 1800.0,
    short_rest_s: float = 1.0,
    repeat_count: int = 12,
    v_min: float = 2.5,
    v_max: float = 4.2,
    **_: Any,
) -> ModuleRecipe:
    """Fixture-matched QPEED-2: set to 3.318 V, then high-C to 4.2 V, ×12."""
    condition = _qpeed_condition(
        c_rate=condition_c_rate,
        rest_s=rest_s,
        v_min=v_min,
        v_max=v_max,
        set_voltage_v=soc_voltage_v,
    )
    pulse_cycle = [
        charge(
            c_rate=pulse_c_rate,
            mode="CC",
            end_voltage_v=v_max,
            label="high-C to full",
        ),
        rest(short_rest_s, "1 s rest"),
        rest(rest_s),
        *_qpeed_condition(
            c_rate=condition_c_rate,
            rest_s=rest_s,
            v_min=v_min,
            v_max=v_max,
            set_voltage_v=soc_voltage_v,
            initial_rest_s=0.0,
        ),
    ]
    return ModuleRecipe(
        preset="qpeed.full_3318",
        setup=condition,
        repeat=pulse_cycle,
        repeat_count=repeat_count,
    )


def build_qpeed_soc_setting(
    *,
    condition_c_rate: float = 1.0,
    rest_s: float = 1800.0,
    v_min: float = 2.5,
    v_max: float = 4.2,
    **_: Any,
) -> ModuleRecipe:
    """Fixture-matched QPEED SOC_setting conditioning block (no pulse train)."""
    return ModuleRecipe(
        preset="qpeed.soc_setting",
        setup=_qpeed_condition(
            c_rate=condition_c_rate,
            rest_s=rest_s,
            v_min=v_min,
            v_max=v_max,
            set_voltage_v=None,
        ),
        repeat=[],
        repeat_count=1,
    )


def build_qpeed_soc_fraction(
    *,
    soc_fractions: list[float] | None = None,
    pulse_c_rate: float = 1.0,
    pulse_s: float = 10.0,
    rest_between_s: float = 40.0,
    **_: Any,
) -> ModuleRecipe:
    """Generator template: SOC-fraction staircase with timed pulses (not fixture-matched)."""
    fractions = list(soc_fractions or [0.5])
    units: list[RecipeUnit] = []
    previous = 1.0
    for soc in fractions:
        if soc < previous:
            units.append(
                discharge(
                    c_rate=C_THIRD,
                    end_capacity_fraction=previous - soc,
                    label=f"SOC adjust to {soc:.0%}",
                )
            )
            units.append(rest(rest_between_s))
        units.extend(
            [
                discharge(
                    c_rate=pulse_c_rate,
                    end_time_s=pulse_s,
                    label=f"discharge pulse @ {soc:.0%}",
                ),
                rest(rest_between_s),
                charge(
                    c_rate=pulse_c_rate,
                    end_time_s=pulse_s,
                    label=f"charge pulse @ {soc:.0%}",
                ),
                rest(rest_between_s),
            ]
        )
        previous = soc
    return ModuleRecipe(preset="qpeed.soc_fraction", setup=units, repeat_count=1)


def build_hppc_soc_90_50_10(
    *,
    soc_fractions: list[float] | None = None,
    pulse_c_rate: float = 1.0,
    pulse_s: float = 10.0,
    rest_between_s: float = 40.0,
    **kwargs: Any,
) -> ModuleRecipe:
    recipe = build_qpeed_soc_fraction(
        soc_fractions=soc_fractions or [0.9, 0.5, 0.1],
        pulse_c_rate=pulse_c_rate,
        pulse_s=pulse_s,
        rest_between_s=rest_between_s,
        **kwargs,
    )
    recipe.preset = "hppc.soc_90_50_10"
    return recipe


def build_hppc_full_range(
    *,
    pulse_c_rate: float = 1.0,
    rest_s: float = 1800.0,
    v_min: float = 2.5,
    v_max: float = 4.2,
    residual_c_rate: float = 0.001,
    **_: Any,
) -> ModuleRecipe:
    """Simplified full-range HPPC: voltage limits plus a residual-current approach."""
    return ModuleRecipe(
        preset="hppc.full_range",
        setup=[
            rest(10800.0, "initial rest"),
            charge(
                c_rate=pulse_c_rate,
                mode="CCCV",
                end_voltage_v=v_max,
                cv_cutoff_c_rate=0.05,
            ),
            rest(rest_s),
            discharge(c_rate=pulse_c_rate, end_voltage_v=v_min),
            rest(rest_s),
        ],
        repeat=[
            discharge(
                c_rate=residual_c_rate,
                end_voltage_v=v_min,
                label="residual to empty",
            ),
            rest(rest_s),
            charge(c_rate=pulse_c_rate, mode="CC", end_voltage_v=v_max),
            rest(rest_s),
            charge(
                c_rate=residual_c_rate,
                mode="CC",
                end_voltage_v=v_max,
                label="residual to full",
            ),
            rest(rest_s),
            discharge(c_rate=pulse_c_rate, end_voltage_v=v_min),
            rest(rest_s),
        ],
        repeat_count=1,
    )


def build_formation_default(
    *,
    charge_c_rate: float = 0.1,
    discharge_c_rate: float = 0.1,
    rest_s: float = 600.0,
    cycle_count: int = 3,
    v_min: float = 2.5,
    v_max: float = 4.2,
    **_: Any,
) -> ModuleRecipe:
    return ModuleRecipe(
        preset="formation.default",
        setup=[],
        repeat=[
            charge(
                c_rate=charge_c_rate,
                mode="CCCV",
                end_voltage_v=v_max,
                cv_cutoff_c_rate=0.05,
            ),
            rest(rest_s),
            discharge(c_rate=discharge_c_rate, end_voltage_v=v_min),
            rest(rest_s),
        ],
        repeat_count=max(int(cycle_count), 1),
    )


def build_cycle_life_default(
    *,
    charge_c_rate: float = 0.5,
    discharge_c_rate: float = 0.5,
    rest_s: float = 300.0,
    loop_count: int = 100,
    v_min: float = 2.5,
    v_max: float = 4.2,
    **_: Any,
) -> ModuleRecipe:
    return ModuleRecipe(
        preset="cycle_life.default",
        setup=[],
        repeat=[
            charge(
                c_rate=charge_c_rate,
                mode="CCCV",
                end_voltage_v=v_max,
                cv_cutoff_c_rate=0.05,
            ),
            rest(rest_s),
            discharge(c_rate=discharge_c_rate, end_voltage_v=v_min),
            rest(rest_s),
        ],
        repeat_count=max(int(loop_count), 1),
        after=[end_step()],
    )


def build_sequence_blank(**_: Any) -> ModuleRecipe:
    return ModuleRecipe(preset="sequence.blank")


PRESETS: tuple[PresetSpec, ...] = (
    PresetSpec(
        "qpeed.full_3318",
        "qpeed",
        "QPEED full · 3.318 V",
        "Condition to 3.318 V, then 1.5C to 4.2 V, repeated. Matches QPEED-2 topology.",
        build_qpeed_full_3318,
    ),
    PresetSpec(
        "qpeed.soc_setting",
        "qpeed",
        "QPEED SOC setting",
        "1C empty / CCCV / empty / charge. Conditioning block only.",
        build_qpeed_soc_setting,
    ),
    PresetSpec(
        "qpeed.soc_fraction",
        "qpeed",
        "QPEED SOC-fraction pulses",
        "Generator template using capacity fractions and timed pulses. Not fixture-matched.",
        build_qpeed_soc_fraction,
    ),
    PresetSpec(
        "hppc.full_range",
        "hppc",
        "HPPC full range",
        "2.5–4.2 V cycling with a residual-current approach. Simplified from HPPC_Full range.sch.",
        build_hppc_full_range,
    ),
    PresetSpec(
        "hppc.soc_90_50_10",
        "hppc",
        "HPPC SOC 90/50/10",
        "Generator template: timed charge/discharge pulses at SOC 90/50/10.",
        build_hppc_soc_90_50_10,
    ),
    PresetSpec(
        "formation.default",
        "formation",
        "Formation 0.1C",
        "CCCV charge and CC discharge with rest, repeated.",
        build_formation_default,
    ),
    PresetSpec(
        "cycle_life.default",
        "cycle_life",
        "Cycle life 0.5C",
        "CCCV / rest / discharge / rest inside a LOOP.",
        build_cycle_life_default,
    ),
    PresetSpec(
        "sequence.blank",
        "sequence",
        "Blank sequence",
        "Empty charge/discharge/rest list to edit by hand.",
        build_sequence_blank,
    ),
)

PRESETS_BY_KEY: dict[str, PresetSpec] = {spec.key: spec for spec in PRESETS}
DEFAULT_PRESET_FOR_TYPE: dict[str, str] = {
    "qpeed": "qpeed.full_3318",
    "hppc": "hppc.full_range",
    "formation": "formation.default",
    "cycle_life": "cycle_life.default",
    "sequence": "sequence.blank",
}


def presets_for(module_type: str) -> tuple[PresetSpec, ...]:
    return tuple(spec for spec in PRESETS if spec.module_type == module_type)


def build_preset(preset_key: str, knobs: dict[str, Any] | None = None) -> ModuleRecipe:
    spec = PRESETS_BY_KEY.get(preset_key)
    if spec is None:
        raise ValueError(f"Unknown preset: {preset_key}")
    return spec.builder(**(knobs or {}))
