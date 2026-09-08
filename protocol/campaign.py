"""Campaign builder — one answer instead of a dozen repeated module entries.

A cycle-life campaign is a rhythm, not a list: run N cycles, measure, run N more,
measure again.  Composing it by hand means adding the same two modules over and
over and keeping the counts straight, which is exactly the kind of bookkeeping
that quietly goes wrong at cycle 150.

This module turns the rhythm into the blocks.  It builds nothing itself and
touches no project: it returns a plan the caller applies, so the result is the
same ordinary module list a user could have typed, and stays editable afterwards.
The alternating cycle/RPT layout it produces is the one the composer already
handles — each block keeps its own LOOP target and only the last block owns END.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .defaults import RPT_DCIR_SOC_FRACTIONS, RPT_DISCHARGE_C_RATE

# A measurement point costs real time, so the default rhythm is deliberately
# coarse; the lab tightens it when a cell is degrading fast.
DEFAULT_RPT_EVERY = 50


@dataclass(frozen=True, slots=True)
class CampaignBlock:
    """One module to append, with the Korean title the procedure list shows."""

    module_type: str
    params: dict
    title: str


@dataclass(frozen=True, slots=True)
class CampaignPlan:
    blocks: tuple[CampaignBlock, ...] = ()
    notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    total_cycles: int = 0
    rpt_count: int = 0
    cycle_block_count: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors and bool(self.blocks)


def _cycle_chunks(total_cycles: int, rpt_every: int) -> list[int]:
    """Split the run into cycle blocks, keeping any remainder as a final block."""
    chunks = [rpt_every] * (total_cycles // rpt_every)
    remainder = total_cycles % rpt_every
    if remainder:
        chunks.append(remainder)
    return chunks


def _rate_text(rates: Sequence[float]) -> str:
    parts = [f"{rate:.2f}".rstrip("0").rstrip(".") + "C" for rate in rates]
    return " · ".join(parts)


def build_cycle_rpt_campaign(
    *,
    total_cycles: int,
    rpt_every: int = DEFAULT_RPT_EVERY,
    charge_c_rate: float,
    discharge_c_rate: float,
    dcir_pulse_c_rates: Sequence[float] = (1.0, 1.5, 2.0),
    reference_c_rate: float = RPT_DISCHARGE_C_RATE,
    soc_fractions: Sequence[float] = RPT_DCIR_SOC_FRACTIONS,
    cycle_rest_s: float = 300.0,
    rpt_rest_s: float = 1800.0,
    dcir_pulse_s: float = 10.0,
    baseline_rpt: bool = True,
) -> CampaignPlan:
    """Plan a "run N cycles, measure, repeat" campaign.

    ``baseline_rpt`` puts one RPT before any cycling, because a capacity-fade
    number is meaningless without the value it faded from.
    """
    errors: list[str] = []
    if total_cycles < 1:
        errors.append("총 사이클 수는 1 이상이어야 합니다.")
    if rpt_every < 1:
        errors.append("RPT 주기는 1 이상이어야 합니다.")
    if charge_c_rate <= 0 or discharge_c_rate <= 0:
        errors.append("충전율과 방전율은 0보다 커야 합니다.")
    if not dcir_pulse_c_rates:
        errors.append("DC-IR 펄스 전류를 하나 이상 지정하세요.")
    elif any(rate <= 0 for rate in dcir_pulse_c_rates):
        errors.append("DC-IR 펄스 전류는 0보다 커야 합니다.")
    if errors:
        return CampaignPlan(errors=tuple(errors))

    rates = [float(rate) for rate in dcir_pulse_c_rates]
    rpt_params = {
        "reference_c_rate": reference_c_rate,
        "dcir_pulse_c_rates": rates,
        "dcir_pulse_s": dcir_pulse_s,
        "rest_s": rpt_rest_s,
        "soc_fractions": [float(value) for value in soc_fractions],
        "include_dcir_pulses": True,
    }
    rate_text = _rate_text(rates)

    blocks: list[CampaignBlock] = []
    if baseline_rpt:
        blocks.append(
            CampaignBlock("rpt", dict(rpt_params), f"RPT 기준값 (0 사이클) · DC-IR {rate_text}")
        )

    chunks = _cycle_chunks(total_cycles, rpt_every)
    done = 0
    for chunk in chunks:
        done += chunk
        blocks.append(
            CampaignBlock(
                "cycle_life",
                {
                    "charge_c_rate": charge_c_rate,
                    "discharge_c_rate": discharge_c_rate,
                    "rest_s": cycle_rest_s,
                    "loop_count": chunk,
                },
                f"사이클 {done - chunk + 1}–{done} ({chunk}회)",
            )
        )
        blocks.append(
            CampaignBlock("rpt", dict(rpt_params), f"RPT @ {done} 사이클 · DC-IR {rate_text}")
        )

    notes = [
        f"사이클 {total_cycles}회를 {len(chunks)}개 구간으로 나누고 구간마다 RPT 를 넣었습니다.",
        f"RPT {len([b for b in blocks if b.module_type == 'rpt'])}회 · "
        f"각 RPT 는 SOC {len(soc_fractions)}지점 × 전류 {len(rates)}종 펄스를 측정합니다.",
    ]
    if chunks and chunks[-1] != rpt_every:
        notes.append(
            f"마지막 구간은 {chunks[-1]}회입니다 (총 사이클이 주기의 배수가 아니라 나머지가 남았습니다)."
        )

    warnings = [
        "DC-IR 저항 계산 구간(1초–10초)은 장비 파일에 기록되지 않습니다. "
        "펄스는 정상적으로 실행되지만 저항은 CTSPro 에서 구간을 지정하거나 "
        "측정 데이터에서 직접 계산해야 합니다.",
        "RPT 모듈은 아직 prototype 입니다. CTSPro 재열기 확인 전에는 "
        "장비 실행용으로 내보낼 수 없습니다.",
    ]

    return CampaignPlan(
        blocks=tuple(blocks),
        notes=tuple(notes),
        warnings=tuple(warnings),
        total_cycles=total_cycles,
        rpt_count=sum(1 for block in blocks if block.module_type == "rpt"),
        cycle_block_count=len(chunks),
    )


__all__ = [
    "DEFAULT_RPT_EVERY",
    "CampaignBlock",
    "CampaignPlan",
    "build_cycle_rpt_campaign",
]
