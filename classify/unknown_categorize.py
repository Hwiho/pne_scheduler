"""Categorize unknown SCH filenames using filename hints and binary signatures."""

from __future__ import annotations

import csv
import json
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .schedule_classifier import classify_schedule
from .schedule_filename import ScheduleCategory
from .sch_binary_profile import binary_profile

TRAINING_ROW_SCHEMA = "pne_scheduler.unknown_sch_training_row/v1"
REPORT_SCHEMA = "pne_scheduler.unknown_sch_categorization/v1"

# Filename keyword probes (label, pattern, suggested_category)
FILENAME_PROBE_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("soc_only", re.compile(r"SOC\s*\d+", re.I), "soc_setting"),
    ("soc_setting_loose", re.compile(r"soc[_\s-]*\d+", re.I), "soc_setting"),
    ("c_rate_token", re.compile(r"[\d.]+'?\s*C\b", re.I), "rate_test"),
    ("initial_check", re.compile(r"initial[_\s-]*check|init[_\s-]*check", re.I), "capacheck"),
    ("capa_check", re.compile(r"capa[_\s-]*check|capcheck|capacity[_\s-]*check", re.I), "capacheck"),
    ("aging", re.compile(r"\baging\b|ageing", re.I), "storage"),
    ("swelling", re.compile(r"swell|breathing", re.I), "cycle_life"),
    ("pulse", re.compile(r"\bpulse\b|pluse", re.I), "hppc"),
    ("preheat", re.compile(r"preheat|pre.?heat|preheating", re.I), "rest"),
    ("xrd", re.compile(r"\bxrd\b", re.I), "soc_setting"),
    ("xrm", re.compile(r"\bxrm\b", re.I), "discharge"),
    ("lt_profile", re.compile(r"LT\d+C", re.I), "cycle_life"),
    ("std_ref", re.compile(r"\bstd\b|standardiz", re.I), "rpt"),
    ("stack_mono", re.compile(r"\bstack\b|\bmono\b|\d+stack", re.I), "cycle_life"),
    ("wip", re.compile(r"\bwip\b", re.I), "unknown"),
    ("cip", re.compile(r"\bcip\d*\b", re.I), "formation"),
    ("cont_cycle", re.compile(r"\bcont\b", re.I), "cycle_life"),
    ("sop", re.compile(r"\bsop\b", re.I), "formation"),
    ("cross_pct", re.compile(r"cross\d+%", re.I), "doe"),
    ("ch_dch_token", re.compile(r"\bCH\b|\bDCH\b|_CH_|_DCH_", re.I), "charge"),
    ("plating", re.compile(r"plating|electrodep", re.I), "charge"),
    ("gitt_token", re.compile(r"gitt|pitt", re.I), "gitt"),
    ("dcir_token", re.compile(r"dcir|dcr", re.I), "dcir"),
    ("form_token", re.compile(r"(?:^|[_\s-])form(?:\.sch|_|$|\s)", re.I), "formation"),
)

_TOKEN_SPLIT = re.compile(r"[^a-zA-Z0-9가-힣]+")


@dataclass(frozen=True, slots=True)
class SignatureVote:
    category: str
    count: int
    total: int

    @property
    def confidence(self) -> float:
        return round(self.count / self.total, 4) if self.total else 0.0


@dataclass(frozen=True, slots=True)
class UnknownSchRecord:
    unit: str
    zip_path: str
    archive_path: str
    stem: str
    step_signature: str | None
    step_count: int | None
    loop_steps: int | None
    current_mA_max: float | None
    filename_probes: tuple[str, ...]
    filename_tokens: tuple[str, ...]
    suggested_category: str
    confidence: float
    method: str
    matched_rule: str
    signature_votes: tuple[SignatureVote, ...]


def tokenize_filename(stem: str) -> list[str]:
    raw = _TOKEN_SPLIT.split(stem.lower())
    return [t for t in raw if len(t) >= 2][:24]


def probe_filename(stem: str) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    for label, pattern, category in FILENAME_PROBE_RULES:
        if pattern.search(stem):
            hits.append((label, category))
    return hits


def build_signature_model(
    labeled: list[tuple[str, str | None]],
    *,
    min_votes: int = 2,
) -> dict[str, Counter[str]]:
    """Map step_signature → category counts from already-classified files."""
    model: dict[str, Counter[str]] = defaultdict(Counter)
    for category, signature in labeled:
        if not signature or category == ScheduleCategory.UNKNOWN.value:
            continue
        model[signature][category] += 1
    return {sig: ctr for sig, ctr in model.items() if sum(ctr.values()) >= min_votes}


def suggest_from_signature(
    signature: str | None,
    model: dict[str, Counter[str]],
) -> tuple[str, float, str, tuple[SignatureVote, ...]]:
    if not signature or signature not in model:
        return ScheduleCategory.UNKNOWN.value, 0.0, "none", ()
    ctr = model[signature]
    total = sum(ctr.values())
    category, count = ctr.most_common(1)[0]
    votes = tuple(
        SignatureVote(category=cat, count=cnt, total=total)
        for cat, cnt in ctr.most_common(3)
    )
    return category, round(count / total, 4), "binary_signature", votes


def suggest_from_filename_probes(
    probes: list[tuple[str, str]],
) -> tuple[str, float, str]:
    if not probes:
        return ScheduleCategory.UNKNOWN.value, 0.0, "none"
    # Prefer specific experiment families over generic charge/discharge.
    priority = {
        "gitt_token": 10,
        "dcir_token": 10,
        "pulse": 9,
        "initial_check": 9,
        "capa_check": 9,
        "soc_setting_loose": 8,
        "soc_only": 8,
        "xrd": 8,
        "aging": 7,
        "swelling": 7,
        "lt_profile": 7,
        "cont_cycle": 7,
        "stack_mono": 6,
        "c_rate_token": 5,
        "form_token": 5,
        "cip": 5,
        "sop": 5,
        "preheat": 4,
        "xrm": 4,
        "ch_dch_token": 2,
        "plating": 2,
        "wip": 1,
    }
    best = max(probes, key=lambda p: priority.get(p[0], 3))
    return best[1], 0.55, f"filename_probe:{best[0]}"


def merge_suggestions(
    sig_cat: str,
    sig_conf: float,
    sig_method: str,
    probe_cat: str,
    probe_conf: float,
    probe_method: str,
) -> tuple[str, float, str]:
    if sig_conf >= 0.7:
        return sig_cat, sig_conf, sig_method
    if probe_conf > sig_conf and probe_cat != ScheduleCategory.UNKNOWN.value:
        return probe_cat, probe_conf, probe_method
    if sig_conf >= 0.5:
        return sig_cat, sig_conf, sig_method
    if probe_cat != ScheduleCategory.UNKNOWN.value:
        return probe_cat, probe_conf, probe_method
    return ScheduleCategory.UNKNOWN.value, max(sig_conf, probe_conf), sig_method if sig_conf else probe_method


def scan_zip_corpus(
    zip_map: dict[str, Path],
) -> tuple[list[UnknownSchRecord], dict[str, Counter[str]]]:
    labeled_signatures: list[tuple[str, str | None]] = []
    unknown_stubs: list[dict[str, Any]] = []

    for unit, zip_path in sorted(zip_map.items()):
        if not zip_path.is_file():
            continue
        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                if not name.lower().endswith(".sch"):
                    continue
                stem = PurePosixPath(name).name
                try:
                    data = zf.read(name)
                    match = classify_schedule(stem, data)
                    profile = binary_profile(data)
                except Exception:
                    match = None
                    profile = None
                signature = profile["step_signature"] if profile else None
                if match is None:
                    continue
                labeled_signatures.append((match.category.value, signature))
                if match.category != ScheduleCategory.UNKNOWN:
                    continue
                unknown_stubs.append(
                    {
                        "unit": unit,
                        "zip_path": str(zip_path),
                        "archive_path": name,
                        "stem": stem,
                        "profile": profile,
                        "signature": signature,
                        "probes": probe_filename(stem),
                        "tokens": tokenize_filename(stem),
                        "matched_rule": match.matched_rule,
                    }
                )

    signature_model = build_signature_model(labeled_signatures)
    records: list[UnknownSchRecord] = []
    for stub in unknown_stubs:
        profile = stub["profile"]
        probes: list[tuple[str, str]] = stub["probes"]
        probe_labels = tuple(p[0] for p in probes)
        sig_cat, sig_conf, sig_method, votes = suggest_from_signature(
            stub["signature"], signature_model
        )
        probe_cat, probe_conf, probe_method = suggest_from_filename_probes(probes)
        category, confidence, method = merge_suggestions(
            sig_cat, sig_conf, sig_method, probe_cat, probe_conf, probe_method
        )
        records.append(
            UnknownSchRecord(
                unit=stub["unit"],
                zip_path=stub["zip_path"],
                archive_path=stub["archive_path"],
                stem=stub["stem"],
                step_signature=stub["signature"],
                step_count=profile["step_count"] if profile else None,
                loop_steps=profile["loop_steps"] if profile else None,
                current_mA_max=profile["current_mA_max"] if profile else None,
                filename_probes=probe_labels,
                filename_tokens=tuple(stub["tokens"]),
                suggested_category=category,
                confidence=confidence,
                method=method,
                matched_rule=stub.get("matched_rule", "none"),
                signature_votes=votes,
            )
        )

    return records, signature_model


def build_unit_review_priority(
    unit: str,
    records: list[UnknownSchRecord],
    *,
    top_clusters: int = 40,
    top_tokens: int = 30,
) -> dict[str, Any]:
    """Rank unknown clusters and tokens for human review (e.g. PNE04)."""
    unit_recs = [r for r in records if r.unit == unit]
    clusters = [c for c in build_clusters(unit_recs) if c["unit"] == unit]

    def priority_score(cluster: dict[str, Any]) -> float:
        members = [
            r
            for r in unit_recs
            if (r.step_signature or "parse_fail") == (cluster.get("step_signature") or "parse_fail")
        ]
        if not members:
            return float(cluster["count"])
        avg_conf = sum(m.confidence for m in members) / len(members)
        unresolved = sum(1 for m in members if m.suggested_category == ScheduleCategory.UNKNOWN.value)
        return cluster["count"] * (0.5 + avg_conf) + unresolved * 0.25

    ranked_clusters = sorted(clusters, key=priority_score, reverse=True)[:top_clusters]
    for cluster in ranked_clusters:
        cluster["priority_score"] = round(priority_score(cluster), 2)

    token_ctr: Counter[str] = Counter()
    for rec in unit_recs:
        if rec.suggested_category != ScheduleCategory.UNKNOWN.value:
            continue
        for tok in rec.filename_tokens:
            if len(tok) >= 3 and tok not in ("sch", "set", "copy"):
                token_ctr[tok] += 1

    high_value = [
        r
        for r in unit_recs
        if r.confidence >= 0.55 and r.suggested_category != ScheduleCategory.UNKNOWN.value
    ]
    high_value.sort(key=lambda r: (-r.confidence, r.stem))

    return {
        "schema": "pne_scheduler.unit_unknown_review/v1",
        "unit": unit,
        "unknown_count": len(unit_recs),
        "still_unresolved": sum(
            1 for r in unit_recs if r.suggested_category == ScheduleCategory.UNKNOWN.value
        ),
        "review_clusters": ranked_clusters,
        "unresolved_tokens": [
            {"token": tok, "count": cnt} for tok, cnt in token_ctr.most_common(top_tokens)
        ],
        "promote_candidates": [
            {
                "stem": r.stem,
                "suggested_category": r.suggested_category,
                "confidence": r.confidence,
                "method": r.method,
                "step_signature": r.step_signature,
            }
            for r in high_value[:60]
        ],
    }


def render_unit_review_markdown(review: dict[str, Any]) -> str:
    unit = review["unit"]
    lines = [
        f"# {unit} unknown SCH review priority",
        "",
        f"- Unknown after full classifier: **{review['unknown_count']}**",
        f"- Still unresolved (no suggestion): **{review['still_unresolved']}**",
        "",
        "## Top clusters (review first)",
        "",
        "| Priority | Count | Suggested | Signature (truncated) | Examples |",
        "|---------:|------:|-----------|----------------------|----------|",
    ]
    for cluster in review.get("review_clusters", [])[:25]:
        sig = cluster.get("step_signature") or "parse_fail"
        if len(sig) > 48:
            sig = sig[:45] + "..."
        examples = "; ".join(cluster.get("examples", [])[:2])
        if len(examples) > 60:
            examples = examples[:57] + "..."
        lines.append(
            f"| {cluster.get('priority_score', '')} | {cluster['count']} | "
            f"{cluster.get('suggested_category', '')} | `{sig}` | {examples} |"
        )
    lines.extend(["", "## Unresolved filename tokens", ""])
    for item in review.get("unresolved_tokens", [])[:20]:
        lines.append(f"- `{item['token']}`: {item['count']}")
    lines.extend(["", "## High-value promote candidates (confidence ≥0.55)", ""])
    for item in review.get("promote_candidates", [])[:15]:
        lines.append(
            f"- `{item['stem']}` → **{item['suggested_category']}** "
            f"({item['confidence']}, {item['method']})"
        )
    return "\n".join(lines) + "\n"


def _cluster_key(rec: UnknownSchRecord) -> str:
    probes = ",".join(rec.filename_probes[:3]) or "none"
    return f"{rec.unit}|{rec.step_signature or 'parse_fail'}|{probes}"


def build_clusters(records: list[UnknownSchRecord]) -> list[dict[str, Any]]:
    buckets: dict[str, list[UnknownSchRecord]] = defaultdict(list)
    for rec in records:
        buckets[_cluster_key(rec)].append(rec)

    clusters: list[dict[str, Any]] = []
    for key, members in buckets.items():
        unit, signature, probes = key.split("|", 2)
        cat_votes = Counter(m.suggested_category for m in members)
        top_cat, top_n = cat_votes.most_common(1)[0]
        clusters.append(
            {
                "cluster_id": key,
                "unit": unit,
                "step_signature": signature if signature != "parse_fail" else None,
                "filename_probes": probes.split(",") if probes != "none" else [],
                "count": len(members),
                "suggested_category": top_cat,
                "category_votes": dict(cat_votes.most_common()),
                "examples": [m.stem for m in members[:5]],
            }
        )
    clusters.sort(key=lambda c: (-c["count"], c["unit"], c["cluster_id"]))
    return clusters


def build_rule_candidates(records: list[UnknownSchRecord], *, min_count: int = 8) -> list[dict]:
    """Token patterns frequent among high-confidence suggestions (for rule promotion)."""
    token_by_cat: dict[str, Counter[str]] = defaultdict(Counter)
    for rec in records:
        if rec.confidence < 0.55 or rec.suggested_category == ScheduleCategory.UNKNOWN.value:
            continue
        for tok in rec.filename_tokens:
            if tok.isdigit() or len(tok) < 3:
                continue
            token_by_cat[rec.suggested_category][tok] += 1

    candidates: list[dict] = []
    for category, ctr in token_by_cat.items():
        for token, count in ctr.most_common(20):
            if count < min_count:
                continue
            candidates.append(
                {
                    "category": category,
                    "token": token,
                    "count": count,
                    "suggested_pattern": rf"(?i)\b{re.escape(token)}\b",
                    "rule_name": f"{category}_{token}_token",
                }
            )
    candidates.sort(key=lambda c: (-c["count"], c["category"]))
    return candidates


def record_to_training_row(rec: UnknownSchRecord) -> dict[str, Any]:
    return {
        "schema": TRAINING_ROW_SCHEMA,
        "unit": rec.unit,
        "stem": rec.stem,
        "archive_path": rec.archive_path,
        "current_label": ScheduleCategory.UNKNOWN.value,
        "suggested_category": rec.suggested_category,
        "confidence": rec.confidence,
        "method": rec.method,
        "step_signature": rec.step_signature,
        "step_count": rec.step_count,
        "loop_steps": rec.loop_steps,
        "current_mA_max": rec.current_mA_max,
        "filename_probes": list(rec.filename_probes),
        "filename_tokens": list(rec.filename_tokens),
        "signature_votes": [
            {"category": v.category, "count": v.count, "total": v.total}
            for v in rec.signature_votes
        ],
        "review_status": "auto",
        "verified_label": None,
    }


def signature_model_to_json(model: dict[str, Counter[str]]) -> dict[str, dict[str, int]]:
    return {sig: dict(ctr) for sig, ctr in sorted(model.items(), key=lambda x: -sum(x[1].values()))}


def build_report(
    zip_map: dict[str, Path],
    *,
    records: list[UnknownSchRecord] | None = None,
    signature_model: dict[str, Counter[str]] | None = None,
) -> dict[str, Any]:
    if records is None or signature_model is None:
        records, signature_model = scan_zip_corpus(zip_map)
    clusters = build_clusters(records)
    rule_candidates = build_rule_candidates(records)

    suggested_counts = Counter(rec.suggested_category for rec in records)
    resolved = sum(1 for r in records if r.suggested_category != ScheduleCategory.UNKNOWN.value)
    high_conf = sum(1 for r in records if r.confidence >= 0.7)

    per_unit_detail: dict[str, Any] = {}
    for unit in sorted({r.unit for r in records}):
        unit_recs = [r for r in records if r.unit == unit]
        per_unit_detail[unit] = {
            "unknown_count": len(unit_recs),
            "resolved_suggestions": sum(
                1 for r in unit_recs if r.suggested_category != ScheduleCategory.UNKNOWN.value
            ),
            "high_confidence": sum(1 for r in unit_recs if r.confidence >= 0.7),
            "suggested_categories": dict(
                Counter(r.suggested_category for r in unit_recs).most_common()
            ),
        }

    return {
        "schema": REPORT_SCHEMA,
        "total_unknown": len(records),
        "resolved_suggestions": resolved,
        "resolved_pct": round(100 * resolved / len(records), 1) if records else 0,
        "high_confidence": high_conf,
        "high_confidence_pct": round(100 * high_conf / len(records), 1) if records else 0,
        "suggested_categories_all": dict(suggested_counts.most_common()),
        "per_unit": per_unit_detail,
        "signature_model_entries": len(signature_model),
        "cluster_count": len(clusters),
        "top_clusters": clusters[:40],
        "rule_promotion_candidates": rule_candidates[:60],
        "signature_model": signature_model_to_json(signature_model),
    }


def export_training_jsonl(records: list[UnknownSchRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(record_to_training_row(rec), ensure_ascii=False) + "\n")


def export_training_csv(records: list[UnknownSchRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "unit",
        "stem",
        "current_label",
        "suggested_category",
        "confidence",
        "method",
        "step_signature",
        "filename_probes",
        "review_status",
        "verified_label",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for rec in records:
            writer.writerow(
                {
                    "unit": rec.unit,
                    "stem": rec.stem,
                    "current_label": ScheduleCategory.UNKNOWN.value,
                    "suggested_category": rec.suggested_category,
                    "confidence": rec.confidence,
                    "method": rec.method,
                    "step_signature": rec.step_signature or "",
                    "filename_probes": "|".join(rec.filename_probes),
                    "review_status": "auto",
                    "verified_label": "",
                }
            )


def apply_verified_labels(
    records: list[UnknownSchRecord],
    verified: dict[str, str],
) -> list[UnknownSchRecord]:
    updated: list[UnknownSchRecord] = []
    for rec in records:
        if rec.stem not in verified:
            updated.append(rec)
            continue
        updated.append(
            UnknownSchRecord(
                unit=rec.unit,
                zip_path=rec.zip_path,
                archive_path=rec.archive_path,
                stem=rec.stem,
                step_signature=rec.step_signature,
                step_count=rec.step_count,
                loop_steps=rec.loop_steps,
                current_mA_max=rec.current_mA_max,
                filename_probes=rec.filename_probes,
                filename_tokens=rec.filename_tokens,
                suggested_category=verified[rec.stem],
                confidence=1.0,
                method="verified_label",
                matched_rule="verified_label",
                signature_votes=rec.signature_votes,
            )
        )
    return updated
