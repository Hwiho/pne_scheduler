"""Generate a deterministic, reopen-only batch for pattern review in CTSPro."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..engine.c_rate import current_mA_from_c_rate
from ..io.lab_header_writer import build_pne02_reopen_candidate
from ..io.reader import read_sch
from ..io.validation_manifest import (
    VALIDATION_MANIFEST_SCHEMA,
    write_validation_manifest,
)
from ..ir.cell_profile import CellProfile
from ..ir.project import ModuleNode, ScheduleProject
from ..modules.catalog import get_module_spec
from ..schema import SCH_STEP_TYPE_END

PACK_SCHEMA = "pne_scheduler.pattern_review_pack/v1"
PACK_TIMESTAMP = "2026-09-09 00:00:00.000"
CANDIDATE_NAME = "candidate_REOPEN_ONLY_DO_NOT_RUN.sch"
REVIEW_COLUMNS = (
    "pattern_id", "candidate_sha256", "pne_unit", "ctspro_version", "opened",
    "step_count_ok", "values_ok", "loop_ok", "save_as_path", "save_as_sha256",
    "result", "reviewer", "reviewed_at", "notes",
)


@dataclass(frozen=True, slots=True)
class PatternRecipe:
    pattern_id: str
    title: str
    module_type: str
    params: dict[str, Any] = field(default_factory=dict)
    canonical_ref: str = "software module topology only"
    expected_step_counts: tuple[int, ...] = ()


PATTERN_RECIPES: tuple[PatternRecipe, ...] = (
    PatternRecipe("PV-FM", "Formation", "formation", {"cycle_count": 1}, "FM corpus family", (5,)),
    PatternRecipe("PV-CAPA", "Capacity check", "capacheck", {}, "PNE02 capacheck family; candidate topology needs review", (12,)),
    PatternRecipe("PV-CYCLE", "Cycle life", "cycle_life", {"loop_count": 3}, "Cycle corpus family", (7,)),
    PatternRecipe("PV-HPPC", "HPPC full range", "hppc", {"variant": "full"}, "Locked 62-step HPPC full-range golden", (62,)),
    PatternRecipe("PV-QPEED-F", "QPEED full", "qpeed", {"variant": "full"}, "PNE02 locked 167-step golden", (167,)),
    PatternRecipe("PV-QPEED-S", "QPEED SOC setting", "qpeed", {"variant": "soc_setting"}, "PNE02 locked 11-step golden", (11,)),
    PatternRecipe("PV-QC-CYCLE", "QC cycle", "qc", {"variant": "cycle"}, "Set2 17-step QC cycle family", (17, 18)),
    PatternRecipe("PV-QC-NQ", "QC 1N1Q", "qc", {"variant": "1n1q"}, "Set2 17-step QC 1N1Q family", (17, 18)),
    PatternRecipe("PV-QC-C", "QC 1 charge", "qc", {"variant": "1_charge"}, "QC 1-charge 24–26-step family", (24, 25, 26)),
    PatternRecipe("PV-RPT", "RPT prototype", "rpt", {}, "RPT corpus family; fEndC/DCR unresolved", (13,)),
)


@dataclass(frozen=True, slots=True)
class PatternPackResult:
    output_dir: Path
    pattern_count: int
    candidate_hashes: dict[str, str]


def build_pattern_review_pack(output_dir: Path) -> PatternPackResult:
    """Create source, SCH, expectations, and manifest for every review recipe."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cell = CellProfile(
        nominal_capacity_mAh=24.0,
        v_max=4.2,
        v_min=2.5,
        max_current_mA=500.0,
    )
    rows: list[dict[str, Any]] = []
    candidate_hashes: dict[str, str] = {}

    for recipe in PATTERN_RECIPES:
        pattern_dir = output_dir / recipe.pattern_id
        pattern_dir.mkdir(parents=True, exist_ok=True)
        project = ScheduleProject(
            name=f"REOPEN_ONLY_{recipe.pattern_id.replace('-', '_')}",
            cell_profile=cell,
            sch_version=0x00010003,
            modules=[ModuleNode("pattern", recipe.module_type, dict(recipe.params))],
        )
        source_path = pattern_dir / "source.schproj"
        project.save(source_path)
        steps = project.expand_steps()
        if recipe.expected_step_counts and len(steps) not in recipe.expected_step_counts:
            raise ValueError(
                f"{recipe.pattern_id} produced {len(steps)} steps; expected one of "
                f"{recipe.expected_step_counts}"
            )

        candidate = build_pne02_reopen_candidate(project, timestamp=PACK_TIMESTAMP)
        sch_path = pattern_dir / CANDIDATE_NAME
        sch_path.write_bytes(candidate.data)
        parsed = read_sch(sch_path)
        structural_checks = [
            {"name": "layout_v3_612", "passed": parsed.payload_offset == 1760 and parsed.step_size == 612},
            {"name": "step_count_matches", "passed": parsed.step_count == len(steps)},
            {
                "name": "final_end",
                "passed": bool(parsed.steps)
                and parsed.steps[-1]["step_type_code"] == int(SCH_STEP_TYPE_END),
            },
        ]
        if not all(check["passed"] for check in structural_checks):
            raise ValueError(f"Structural reread failed for {recipe.pattern_id}")

        digest = _sha256(sch_path)
        candidate_hashes[recipe.pattern_id] = digest
        spec = get_module_spec(recipe.module_type)
        trust_status = spec.trust_status if spec else "prototype"
        warnings = list(candidate.warnings)
        warnings.extend(spec.limitations if spec else ())
        warnings.extend(
            (
                "REOPEN ONLY. DO NOT START OR RUN THIS SCHEDULE ON EQUIPMENT.",
                "Only the 1760-byte header came from a CTSPro-authored PNE02 file; the step payload was software-generated.",
                "The exact output hash must pass CTSPro reopen/display/save-as review before promotion.",
            )
        )
        warnings = list(dict.fromkeys(warnings))

        _write_expected_steps(pattern_dir / "expected_steps.csv", steps, cell)
        _write_overview(
            pattern_dir / "expected_overview.md",
            recipe=recipe,
            step_count=len(steps),
            trust_status=trust_status,
            digest=digest,
            warnings=warnings,
        )
        (pattern_dir / "sha256.txt").write_text(
            f"{digest}  {CANDIDATE_NAME}\n", encoding="utf-8"
        )

        manifest = {
            "schema": VALIDATION_MANIFEST_SCHEMA,
            "writer": "pne02_lab_header_reopen_candidate",
            "status": "CTSPro-reopen-candidate",
            "equipment_executable": False,
            "source_project": {
                "path": f"{recipe.pattern_id}/source.schproj",
                "sha256": _sha256(source_path),
            },
            "template": {
                "path": str(candidate.template_path.relative_to(candidate.template_path.parents[3])),
                "sha256": candidate.template_sha256,
                "size": candidate.template_path.stat().st_size,
                "usage": "header bytes 0..1759 only",
            },
            "target_profile": {
                "status": "review_target",
                "equipment": "PNE02",
                "channel_profile": "max 500 mA; reopen only",
                "ctspro_version": "user to record",
                "sch_version": "0x00010003",
                "step_size": 612,
                "cell_profile": cell.to_dict(),
            },
            "output": {
                "path": f"{recipe.pattern_id}/{CANDIDATE_NAME}",
                "sha256": digest,
                "size": sch_path.stat().st_size,
            },
            "changed_fields": [
                {"scope": "header", "fields": ["timestamps", "name", "PNE02 safety blocks"]},
                {"scope": "payload", "range": [1760, sch_path.stat().st_size], "source": "compiled StepIntent list"},
            ],
            "evidence": [
                "planning/PATTERN_VALIDATION_PLAN.md",
                recipe.canonical_ref,
                "PNE02 v3/612 corpus and Gate D structural harness",
            ],
            "validation": {
                "all_passed": True,
                "checks": structural_checks,
                "structural_reread": "passed",
                "equipment_smoke_test": "not_run",
            },
            "warnings": warnings,
        }
        write_validation_manifest(
            pattern_dir / f"{CANDIDATE_NAME}.manifest.json",
            manifest,
        )
        rows.append(
            {
                "pattern_id": recipe.pattern_id,
                "title": recipe.title,
                "module": recipe.module_type,
                "trust": trust_status,
                "steps": len(steps),
                "sha256": digest,
                "candidate": f"{recipe.pattern_id}/{CANDIDATE_NAME}",
            }
        )

    _write_index(output_dir / "INDEX.md", rows)
    review_path = output_dir / "review_results.csv"
    if not review_path.exists() or _review_sheet_is_blank(review_path):
        _write_review_sheet(review_path, rows)
    pack_manifest = {
        "schema": PACK_SCHEMA,
        "created_for": "PNE02 CTSPro batch reopen review",
        "equipment_executable": False,
        "pattern_count": len(rows),
        "patterns": rows,
    }
    (output_dir / "pack_manifest.json").write_text(
        json.dumps(pack_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return PatternPackResult(output_dir, len(rows), candidate_hashes)


def _write_expected_steps(path: Path, steps: list[Any], cell: CellProfile) -> None:
    stream = io.StringIO(newline="")
    columns = (
        "step_no", "type", "mode", "label", "c_rate", "current_mA", "voltage_v",
        "end_voltage_v", "end_time_s", "cv_cutoff_c_rate", "dod_percent",
        "end_capacity_fraction", "loop_target", "loop_count", "cap_ref_step",
    )
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for index, step in enumerate(steps, start=1):
        current = ""
        if step.current_mA is not None:
            current = step.current_mA
        elif step.c_rate is not None:
            current = current_mA_from_c_rate(step.c_rate, cell)
        writer.writerow(
            {
                "step_no": index,
                "type": step.step_type,
                "mode": step.mode or "",
                "label": step.label,
                "c_rate": "" if step.c_rate is None else step.c_rate,
                "current_mA": current,
                "voltage_v": "" if step.voltage_v is None else step.voltage_v,
                "end_voltage_v": "" if step.end_voltage_v is None else step.end_voltage_v,
                "end_time_s": "" if step.end_time_s is None else step.end_time_s,
                "cv_cutoff_c_rate": "" if step.cv_cutoff_c_rate is None else step.cv_cutoff_c_rate,
                "dod_percent": "" if step.dod_percent is None else step.dod_percent,
                "end_capacity_fraction": "" if step.end_capacity_fraction is None else step.end_capacity_fraction,
                "loop_target": "" if step.loop_goto_step is None else step.loop_goto_step,
                "loop_count": "" if step.loop_count is None else step.loop_count,
                "cap_ref_step": step.extra.get("cap_ref_step", ""),
            }
        )
    path.write_text(stream.getvalue(), encoding="utf-8")


def _write_overview(
    path: Path,
    *,
    recipe: PatternRecipe,
    step_count: int,
    trust_status: str,
    digest: str,
    warnings: list[str],
) -> None:
    warning_lines = "\n".join(f"- {warning}" for warning in warnings)
    path.write_text(
        f"""# {recipe.pattern_id} — {recipe.title}

**REOPEN ONLY — DO NOT START OR RUN ON EQUIPMENT.**

- Module: `{recipe.module_type}`
- Parameters: `{json.dumps(recipe.params, ensure_ascii=False, sort_keys=True)}`
- Expected steps: **{step_count}**
- Software trust: `{trust_status}`
- Canonical reference: {recipe.canonical_ref}
- Candidate SHA-256: `{digest}`

## Review

Open `{CANDIDATE_NAME}` in CTSPro and compare every row with `expected_steps.csv`.
Record the CTSPro build, displayed values, Save-As behavior, and result in the pack-level
`review_results.csv`. A successful open is not permission to run.

## Warnings / unresolved evidence

{warning_lines}
""",
        encoding="utf-8",
    )


def _write_index(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# PNE02 Pattern Reopen Review Pack",
        "",
        "**All SCH files in this directory are REOPEN-ONLY and MUST NOT be started or run.**",
        "",
        "Review the simplest schedules first, compare each screen with `expected_steps.csv`,",
        "then Save As and record the result in `review_results.csv`. Approval is exact-hash- and",
        "CTSPro-build-specific.",
        "",
        "| ID | Pattern | Trust | Steps | Candidate |",
        "|---|---|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['pattern_id']} | {row['title']} | {row['trust']} | {row['steps']} | "
            f"[{CANDIDATE_NAME}]({row['candidate']}) |"
        )
    lines.extend(
        [
            "",
            "Required before any SOC-dependent promotion: separate DOD@384 and fEndC@36",
            "controlled pairs described in `planning/PATTERN_VALIDATION_PLAN.md`.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_review_sheet(path: Path, rows: list[dict[str, Any]]) -> None:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=REVIEW_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {"pattern_id": row["pattern_id"], "candidate_sha256": row["sha256"]}
        )
    path.write_text(stream.getvalue(), encoding="utf-8")


def _review_sheet_is_blank(path: Path) -> bool:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != REVIEW_COLUMNS:
            return False
        user_fields = REVIEW_COLUMNS[2:]
        return all(not any((row.get(field) or "").strip() for field in user_fields) for row in reader)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = [
    "CANDIDATE_NAME",
    "PATTERN_RECIPES",
    "PatternPackResult",
    "PatternRecipe",
    "build_pattern_review_pack",
]
