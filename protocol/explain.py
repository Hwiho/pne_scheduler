"""Explain what a parsed PNE schedule does, with explicit evidence limits.

SOC percentages are not stored in the current corpus (`fEndC` and `fSocRate`
are unused). This module narrates filename hints, voltage setpoints, rest
durations, and repeating blocks, and labels each claim as inferred.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from ..classify import QpeedVariant, ScheduleCategory

if TYPE_CHECKING:
    from ..io.sch_parser import ScheduleDocument, SchStepView

ACTIVE_TYPES = frozenset({"CCCV", "CC_CHG", "CC_DCHG", "CHARGE", "DISCHARGE"})
CONTROL_TYPES = frozenset({"LOOP", "CYCLE", "END"})
RESIDUAL_CURRENT_MA = 100.0
TYPICAL_VMIN_V = 2.5
TYPICAL_VMAX_V = 4.2
PARTIAL_V_LO = 2.55
PARTIAL_V_HI = 4.15


class EvidenceKind(StrEnum):
    FILENAME = "filename"
    STEP_TOPOLOGY = "step_topology"
    VOLTAGE_SETPOINT = "voltage_setpoint"
    REST_DURATION = "rest_duration_heuristic"
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class SocCheckpoint:
    label: str
    percent: int | None
    voltage_v: float | None
    source: EvidenceKind
    detail: str
    count: int = 1
    step_nos: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class SchedulePhase:
    title: str
    summary: str
    step_first: int
    step_last: int
    c_rate_labels: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScheduleExplanation:
    path: str
    family: str
    variant: str | None
    title: str
    summary: str
    confidence: float
    soc_checkpoints: tuple[SocCheckpoint, ...]
    phases: tuple[SchedulePhase, ...]
    caveats: tuple[str, ...]
    evidence_notes: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["soc_checkpoints"] = [
            {**item, "source": item["source"]} for item in payload["soc_checkpoints"]
        ]
        return payload


def explain_schedule(document: ScheduleDocument) -> ScheduleExplanation:
    """Build a human-readable, evidence-labeled explanation of a schedule."""
    family, variant, confidence = _family(document)
    checkpoints = _soc_checkpoints(document)
    phases = _phases(document)
    summary = _summary(document, family, variant, checkpoints, phases)
    caveats = _caveats(document, family)
    notes = _evidence_notes(document)
    title = _title(document, family, variant)
    return ScheduleExplanation(
        path=str(document.path),
        family=family,
        variant=variant,
        title=title,
        summary=summary,
        confidence=confidence,
        soc_checkpoints=checkpoints,
        phases=phases,
        caveats=caveats,
        evidence_notes=notes,
    )


def format_explanation(explanation: ScheduleExplanation) -> str:
    """Render a CLI / viewer narrative."""
    lines = [
        explanation.title,
        f"Family: {explanation.family}"
        + (f" / {explanation.variant}" if explanation.variant else "")
        + f"   confidence {explanation.confidence:.0%}",
        "",
        explanation.summary,
        "",
        "SOC checkpoints",
    ]
    if explanation.soc_checkpoints:
        for item in explanation.soc_checkpoints:
            extra = []
            if item.percent is not None:
                extra.append(f"{item.percent}%")
            if item.voltage_v is not None:
                extra.append(f"{item.voltage_v:.3f} V")
            if item.count > 1:
                extra.append(f"×{item.count}")
            extra.append(f"[{item.source.value}]")
            lines.append(f"  - {item.label}: {item.detail} ({', '.join(extra)})")
    else:
        lines.append("  - none readable from the binary (fEndC / fSocRate are unused)")

    if explanation.phases:
        lines.append("")
        lines.append("Blocks")
        grouped = _group_identical_phases(explanation.phases)
        index = 1
        for phase, repeat in grouped:
            rates = f"  C={', '.join(phase.c_rate_labels)}" if phase.c_rate_labels else ""
            if repeat == 1:
                label = f"steps {phase.step_first}–{phase.step_last}"
            else:
                label = (
                    f"steps {phase.step_first}–{phase.step_last} "
                    f"then ×{repeat - 1} more identical blocks"
                )
            lines.append(f"  {index}. {label}: {phase.title}{rates}")
            lines.append(f"     {phase.summary}")
            index += 1

    if explanation.caveats:
        lines.append("")
        lines.append("Caveats")
        for caveat in explanation.caveats:
            lines.append(f"  - {caveat}")

    if explanation.evidence_notes:
        lines.append("")
        lines.append("How this was inferred")
        for note in explanation.evidence_notes:
            lines.append(f"  - {note}")

    return "\n".join(lines).rstrip() + "\n"


def rest_duration_s(step: SchStepView) -> float | None:
    """REST duration. The corpus stores time in fIref because fEndTime is 0."""
    if step.step_type != "REST":
        return None
    if step.f_end_time > 0:
        return float(step.f_end_time)
    if step.f_iref > 0:
        return float(step.f_iref)
    return None


def voltage_v_from_raw(raw: float) -> float | None:
    """Map a raw end/mode value to volts. Corpus end voltages are millivolts."""
    if raw <= 0:
        return None
    if raw >= 20.0:
        return raw / 1000.0
    if 1.0 <= raw <= 6.5:
        return raw
    return None


def step_end_voltage_v(step: SchStepView) -> float | None:
    return voltage_v_from_raw(step.f_end_v)


def step_mode_voltage_v(step: SchStepView) -> float | None:
    return voltage_v_from_raw(step.mode_value)


def format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "0 s"
    if seconds >= 3600 and abs(seconds % 3600) < 1e-6:
        hours = int(round(seconds / 3600))
        return f"{hours} h"
    if seconds >= 60 and abs(seconds % 60) < 1e-6:
        minutes = int(round(seconds / 60))
        return f"{minutes} min"
    if abs(seconds - round(seconds)) < 1e-6:
        return f"{int(round(seconds))} s"
    return f"{seconds:g} s"


def _family(document: ScheduleDocument) -> tuple[str, str | None, float]:
    category = document.classification.category
    proto = document.protocol.protocol.value if document.protocol is not None else "unknown"
    if category == ScheduleCategory.HPPC or proto == "hppc":
        return "hppc", None, 0.9
    if category == ScheduleCategory.QPEED or proto == "qpeed":
        variant = (
            document.classification.qpeed_variant.value
            if document.classification.qpeed_variant is not None
            else "full"
        )
        return "qpeed", variant, 0.9
    if category == ScheduleCategory.RPT or proto == "rpt":
        return "rpt", None, 0.9 if category == ScheduleCategory.RPT else 0.75
    if category == ScheduleCategory.FORMATION or proto == "formation":
        return "formation", None, 0.9
    if category == ScheduleCategory.CAPACHECK or proto in {"capacheck", "derating"}:
        variant = document.classification.protocol_variant.value
        return "capacheck", variant if variant != "none" else None, 0.85
    if category == ScheduleCategory.INSITU_CYCLE or proto == "insitu_cycle":
        return "insitu_cycle", None, 0.8
    if category == ScheduleCategory.CYCLE_LIFE or proto == "cycle_life":
        return "cycle_life", None, 0.8
    return proto if proto != "unknown" else "unknown", None, document.protocol.confidence if document.protocol else 0.2


def _title(document: ScheduleDocument, family: str, variant: str | None) -> str:
    label = family.replace("_", " ").upper() if family != "unknown" else "Unclassified schedule"
    if variant:
        label = f"{label} ({variant})"
    return f"{document.path.name} — {label}"


def _soc_checkpoints(document: ScheduleDocument) -> tuple[SocCheckpoint, ...]:
    items: list[SocCheckpoint] = []
    percents = document.classification.filename_soc_percents
    for percent in percents:
        items.append(
            SocCheckpoint(
                label=f"filename SOC {percent}%",
                percent=percent,
                voltage_v=None,
                source=EvidenceKind.FILENAME,
                detail="Named in the filename; not confirmed by a stored capacity field",
            )
        )

    voltage_steps: dict[float, list[int]] = {}
    for step in document.steps:
        if step.step_type not in ACTIVE_TYPES:
            continue
        volts = step_end_voltage_v(step)
        if volts is None:
            continue
        key = round(volts, 3)
        voltage_steps.setdefault(key, []).append(step.step_no)

    for volts, step_nos in sorted(voltage_steps.items()):
        if _is_typical_limit(volts):
            kind = "empty" if abs(volts - TYPICAL_VMIN_V) < 0.05 else "full"
            items.append(
                SocCheckpoint(
                    label=f"{kind} voltage {volts:.3f} V",
                    percent=0 if kind == "empty" else 100,
                    voltage_v=volts,
                    source=EvidenceKind.STEP_TOPOLOGY,
                    detail="Voltage-terminated charge/discharge at a typical cell limit",
                    count=len(step_nos),
                    step_nos=tuple(step_nos),
                )
            )
        elif PARTIAL_V_LO < volts < PARTIAL_V_HI:
            items.append(
                SocCheckpoint(
                    label=f"partial voltage {volts:.3f} V",
                    percent=None,
                    voltage_v=volts,
                    source=EvidenceKind.VOLTAGE_SETPOINT,
                    detail=(
                        "Mid-window voltage setpoint used as an SOC stand-in; "
                        "percent is unknown without an OCV table"
                    ),
                    count=len(step_nos),
                    step_nos=tuple(step_nos),
                )
            )

    return tuple(items)


def _is_typical_limit(volts: float) -> bool:
    return abs(volts - TYPICAL_VMIN_V) < 0.05 or abs(volts - TYPICAL_VMAX_V) < 0.05


def _group_identical_phases(
    phases: tuple[SchedulePhase, ...],
) -> list[tuple[SchedulePhase, int]]:
    if not phases:
        return []
    grouped: list[tuple[SchedulePhase, int]] = []
    current = phases[0]
    count = 1
    for phase in phases[1:]:
        same = (
            phase.title == current.title
            and phase.summary == current.summary
            and phase.c_rate_labels == current.c_rate_labels
        )
        if same:
            count += 1
        else:
            grouped.append((current, count))
            current = phase
            count = 1
    grouped.append((current, count))
    return grouped


def _phases(document: ScheduleDocument) -> tuple[SchedulePhase, ...]:
    steps = document.steps
    if not steps:
        return ()

    blocks: list[list[SchStepView]] = []
    current: list[SchStepView] = []
    for step in steps:
        if step.step_type == "CYCLE" and current:
            blocks.append(current)
            current = [step]
        else:
            current.append(step)
    if current:
        blocks.append(current)

    phases: list[SchedulePhase] = []
    for block in blocks:
        useful = [s for s in block if s.step_type not in CONTROL_TYPES]
        if not useful and not any(s.step_type == "LOOP" for s in block):
            continue
        first = block[0].step_no
        last = block[-1].step_no
        rates = _unique_c_rate_labels(useful)
        title, summary = _describe_block(block, useful)
        phases.append(
            SchedulePhase(
                title=title,
                summary=summary,
                step_first=first,
                step_last=last,
                c_rate_labels=rates,
            )
        )
    return tuple(phases)


def _unique_c_rate_labels(steps: list[SchStepView]) -> tuple[str, ...]:
    labels: list[str] = []
    seen: set[str] = set()
    for step in steps:
        if step.step_type == "REST":
            continue
        if step.f_iref <= RESIDUAL_CURRENT_MA:
            continue
        label = step.c_rate_label or (f"~{step.c_rate:.2f}C" if step.c_rate else "")
        if label and label not in seen:
            seen.add(label)
            labels.append(label)
    return tuple(labels)


def _describe_block(
    block: list[SchStepView],
    useful: list[SchStepView],
) -> tuple[str, str]:
    loops = [s for s in block if s.step_type == "LOOP"]
    loop_note = ""
    if loops:
        counts = [s.loop_count for s in loops if s.loop_count]
        if counts:
            loop_note = f"; LOOP count {counts[-1]}"
            if loops[-1].loop_target:
                loop_note += f", goto step {loops[-1].loop_target}"

    active = [s for s in useful if s.step_type in ACTIVE_TYPES]
    rests = [s for s in useful if s.step_type == "REST"]
    rest_times = [rest_duration_s(s) for s in rests]
    rest_times_ok = [t for t in rest_times if t is not None]
    rest_text = ""
    if rest_times_ok:
        common = Counter(round(t) for t in rest_times_ok).most_common(2)
        rest_text = ", rest " + ", ".join(
            f"{format_duration(float(t))}×{n}" if n > 1 else format_duration(float(t))
            for t, n in common
        )

    if not active:
        title = "Rest / control"
        summary = f"{len(rests)} rest step(s){rest_text}{loop_note}".strip("; ")
        return title, summary or "Control steps only"

    kinds = []
    residual = 0
    for step in active:
        volts = step_end_voltage_v(step)
        if step.f_iref <= RESIDUAL_CURRENT_MA:
            residual += 1
            kinds.append(
                f"residual {step.f_iref:.0f} mA {step.step_type}"
                + (f" to {volts:.3f} V" if volts else "")
            )
            continue
        rate = step.c_rate_label or ""
        verb = {
            "CCCV": "CCCV charge",
            "CC_CHG": "CC charge",
            "CC_DCHG": "CC discharge",
        }.get(step.step_type, step.step_type)
        end = f" to {volts:.3f} V" if volts else ""
        if step.step_type == "CCCV" and step.f_end_i:
            end = end or " (current cutoff)"
        kinds.append(f"{rate} {verb}{end}".strip())

    compacted = _compact_repeats(kinds)
    title = compacted[0] if len(compacted) == 1 else "Mixed charge/discharge"
    if residual and "residual" not in title:
        title = f"{title}; residual current" if title != "Mixed charge/discharge" else title
    summary = "; ".join(compacted) + rest_text + loop_note
    return title, summary


def _compact_repeats(items: list[str]) -> list[str]:
    if not items:
        return []
    out: list[str] = []
    current = items[0]
    count = 1
    for item in items[1:]:
        if item == current:
            count += 1
        else:
            out.append(current if count == 1 else f"{current} ×{count}")
            current = item
            count = 1
    out.append(current if count == 1 else f"{current} ×{count}")
    return out


def _summary(
    document: ScheduleDocument,
    family: str,
    variant: str | None,
    checkpoints: tuple[SocCheckpoint, ...],
    phases: tuple[SchedulePhase, ...],
) -> str:
    n = len(document.steps)
    if family == "hppc":
        return _hppc_summary(document, checkpoints, n)
    if family == "qpeed":
        return _qpeed_summary(document, variant, checkpoints, n)
    if family == "rpt":
        return _rpt_summary(document, checkpoints, n)
    if family == "formation":
        return (
            f"Formation schedule with {n} steps. Filename/protocol inference treats this "
            "as FM (default 0.1C). The binary uses voltage-terminated CCCV charge and "
            "CC discharge; SOC percentages are not stored."
        )
    if family == "capacheck":
        return (
            f"Capacity-check schedule with {n} steps: typically a rest, then charge/"
            "discharge capacity measurement blocks. Filename protocol is capacheck "
            "(0.1C then C/3 in the lab default). SOC is not a stored field."
        )
    if family in {"cycle_life", "insitu_cycle"}:
        loops = [s.loop_count for s in document.steps if s.step_type == "LOOP" and s.loop_count]
        loop_text = f" A LOOP count of {max(loops)} repeats the aging body." if loops else ""
        kind = "in-situ cycle (no RPT block in the filename)" if family == "insitu_cycle" else "cycle-life"
        return (
            f"{kind.capitalize()} schedule with {n} steps.{loop_text} "
            "Charge/discharge run to voltage limits; SOC staircases are not stored."
        )
    if phases:
        return (
            f"Unclassified or mixed schedule with {n} steps and {len(phases)} "
            "CYCLE-separated block(s). See blocks below; SOC% is not stored in fEndC."
        )
    return f"Schedule with {n} steps. Not enough structure to name a lab protocol."


def _hppc_summary(
    document: ScheduleDocument,
    checkpoints: tuple[SocCheckpoint, ...],
    n: int,
) -> str:
    residual = [
        s
        for s in document.steps
        if s.step_type in ACTIVE_TYPES and 0 < s.f_iref <= RESIDUAL_CURRENT_MA
    ]
    high = [
        s
        for s in document.steps
        if s.step_type in ACTIVE_TYPES and s.f_iref > RESIDUAL_CURRENT_MA
    ]
    limits = sorted({round(v, 3) for v in (step_end_voltage_v(s) for s in high) if v})
    limit_text = (
        " and ".join(f"{v:.3f} V" for v in limits)
        if limits
        else "the charge/discharge voltage limits"
    )
    residual_text = (
        f" {len(residual)} residual-current CC step(s) at ~{residual[0].f_iref:.0f} mA "
        "approach the same voltage limits (not a 10 s pulse train)."
        if residual
        else ""
    )
    mid = [c for c in checkpoints if c.percent not in (0, 100) and c.voltage_v]
    if mid:
        soc_text = (
            " Mid-window voltage setpoints are "
            + ", ".join(f"{c.voltage_v:.3f} V" for c in mid)
            + "; SOC% still cannot be read from fEndC."
        )
    else:
        soc_text = (
            " No discrete SOC% list is stored (fEndC is 0). This fixture is a full "
            "voltage-range protocol, not an SOC 90/50/10 pulse staircase."
        )
    return (
        f"HPPC-named schedule with {n} steps. High-current CCCV/CC steps run between "
        f"{limit_text}.{residual_text}{soc_text}"
    )


def _qpeed_summary(
    document: ScheduleDocument,
    variant: str | None,
    checkpoints: tuple[SocCheckpoint, ...],
    n: int,
) -> str:
    partial = [c for c in checkpoints if c.source == EvidenceKind.VOLTAGE_SETPOINT]
    high = [
        s
        for s in document.steps
        if s.step_type in {"CC_CHG", "CCCV"} and s.f_iref > RESIDUAL_CURRENT_MA
    ]
    high_rates = _unique_c_rate_labels(high)
    rate_text = f" High-C labels: {', '.join(high_rates)}." if high_rates else ""

    if variant == QpeedVariant.SOC_SETTING.value:
        return (
            f"QPEED SOC-setting block with {n} steps. This is the conditioning "
            "sub-protocol that precedes a QPEED pulse/fast-charge file, not a full "
            "pulse train. The binary does not store SOC%; the filename does not "
            "encode a percentage either. Sequence is 1C discharge to 2.5 V, 1C CCCV, "
            "1C discharge, then 1C charge (end voltage unused on that last charge)."
        )

    if partial:
        bits = ", ".join(
            f"{c.voltage_v:.3f} V ×{c.count}" for c in partial if c.voltage_v is not None
        )
        return (
            f"QPEED full schedule with {n} steps. Each repeating block empties to "
            f"2.5 V, capacity-checks at 1C, then charges to a mid-window voltage "
            f"({bits}) as the SOC stand-in, then applies a higher-current charge to "
            f"4.2 V.{rate_text} That voltage is not a stored SOC percentage, and "
            "the high-C step is voltage-terminated (not a proven 10 s pulse)."
        )

    return (
        f"QPEED schedule with {n} steps.{rate_text} SOC% is not stored in fEndC; "
        "use voltage setpoints and filename hints below."
    )


def _rpt_summary(
    document: ScheduleDocument,
    checkpoints: tuple[SocCheckpoint, ...],
    n: int,
) -> str:
    named = [c for c in checkpoints if c.source == EvidenceKind.FILENAME]
    residual = [
        s
        for s in document.steps
        if s.step_type in ACTIVE_TYPES and 0 < s.f_iref <= RESIDUAL_CURRENT_MA
    ]
    named_text = (
        " Filename names " + ", ".join(f"SOC {c.percent}%" for c in named) + "."
        if named
        else " Filename does not list SOC 80/50/20."
    )
    residual_text = (
        f" {len(residual)} residual ~{residual[0].f_iref:.0f} mA discharge step(s) "
        "follow a C-rate discharge (common RPT leftover-current pattern)."
        if residual
        else ""
    )
    return (
        f"RPT schedule with {n} steps.{named_text} The binary does not contain an "
        "fEndC SOC staircase, so the module default 80/50/20 cannot be confirmed "
        f"from this file.{residual_text}"
    )


def _caveats(document: ScheduleDocument, family: str) -> tuple[str, ...]:
    notes = [
        "Inferred for analysis only; not writer-verified and not equipment-ready.",
        "fEndC is 0 on every step in the current corpus, so SOC% cannot be read as a capacity end condition.",
        "REST duration is taken from fIref when fEndTime is 0 (corpus heuristic; semantic-unverified).",
        "C-rates depend on inferred Q_nom; the viewer and writer still do not share one capacity contract.",
    ]
    if family == "hppc":
        notes.append(
            "The HPPC module generator defaults to SOC 90/50/10 and 10 s pulses; "
            "this file does not match that template."
        )
    if family == "qpeed":
        notes.append(
            "The QPEED module generator defaults to SOC 50% via end_capacity_fraction; "
            "this file uses voltage setpoints instead."
        )
    if family == "rpt":
        notes.append(
            "RPT module default DC-IR pulses at SOC 80/50/20 are a generator template, "
            "not a claim about this binary."
        )
    end_times = [s.f_end_time for s in document.steps if s.f_end_time]
    if not end_times:
        notes.append(
            "No nonzero fEndTime values, so short current pulses cannot be distinguished "
            "from voltage-terminated full steps using the time field."
        )
    return tuple(notes)


def _evidence_notes(document: ScheduleDocument) -> tuple[str, ...]:
    cls = document.classification
    proto = document.protocol
    notes = [
        f"Filename rule: {cls.matched_rule} → {cls.category.value}",
    ]
    if proto is not None:
        notes.append(f"Protocol fingerprint: {proto.protocol.value} ({proto.detail})")
    if cls.filename_soc_percents:
        notes.append(
            "Filename SOC: " + ", ".join(f"{p}%" for p in cls.filename_soc_percents)
        )
    else:
        notes.append("Filename does not encode an SOC percentage")
    return tuple(notes)
