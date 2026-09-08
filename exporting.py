"""Concrete output writers behind the gated export paths.

Each function here corresponds to one ``release.OutputOption`` and refuses to
run when that option is locked, so the gate cannot be bypassed by calling the
writer directly.
"""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .engine.c_rate import current_mA_from_c_rate
from .io.validation_manifest import (
    VALIDATION_MANIFEST_SCHEMA,
    write_validation_manifest,
)
from .ir.procedure import build_procedure
from .ir.project import ScheduleProject
from .release import evaluate_release
from .report.summary import summarize_project
from .spec import units

REVIEW_CANDIDATE_NAME = "candidate_REOPEN_ONLY_DO_NOT_RUN.sch"

STEP_COLUMNS_KO = (
    ("step_no", "스텝"),
    ("phase", "구간"),
    ("type", "종류"),
    ("mode", "모드"),
    ("label", "설명"),
    ("c_rate", "C-rate"),
    ("current_mA", "전류(mA)"),
    ("voltage_v", "전압 한계(V)"),
    ("end_voltage_v", "종료 전압(V)"),
    ("end_time_s", "시간 종료(s)"),
    ("end_time_ko", "시간 종료"),
    ("cv_cutoff_c_rate", "CV 종료 전류"),
    ("dod_percent", "DOD(%)"),
    ("loop_target", "LOOP 대상"),
    ("loop_count", "LOOP 횟수"),
)


class ExportBlocked(RuntimeError):
    """The requested output path is locked; the message lists why."""


@dataclass(frozen=True, slots=True)
class ExportResult:
    kind: str
    paths: tuple[Path, ...]
    note: str = ""


def _require(project: ScheduleProject, kind: str) -> None:
    state = evaluate_release(project)
    option = state.option(kind)
    if option is None:
        raise ExportBlocked(f"알 수 없는 내보내기 경로입니다: {kind}")
    if not option.allowed:
        blockers = "\n".join(f"· {item}" for item in option.blockers) or "· 사유 미상"
        raise ExportBlocked(f"{option.title} 은(는) 아직 잠겨 있습니다:\n{blockers}")


def write_step_table(project: ScheduleProject, path: Path) -> Path:
    """Korean step table for review — the expanded schedule as a spreadsheet."""
    view = build_procedure(project)
    cell = project.cell_profile
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=[key for key, _ in STEP_COLUMNS_KO], lineterminator="\n"
    )
    writer.writerow({key: label for key, label in STEP_COLUMNS_KO})
    for number, step in enumerate(view.steps, start=1):
        phase = view.phase_for_step(number)
        current = ""
        if step.current_mA is not None:
            current = round(float(step.current_mA), 4)
        elif step.c_rate is not None:
            current = round(current_mA_from_c_rate(step.c_rate, cell), 4)
        writer.writerow(
            {
                "step_no": number,
                "phase": phase.title if phase else "",
                "type": step.step_type,
                "mode": step.mode or "",
                "label": step.label,
                "c_rate": "" if step.c_rate is None else units.format_c_rate(step.c_rate),
                "current_mA": current,
                "voltage_v": "" if step.voltage_v is None else step.voltage_v,
                "end_voltage_v": "" if step.end_voltage_v is None else step.end_voltage_v,
                "end_time_s": "" if step.end_time_s is None else step.end_time_s,
                "end_time_ko": (
                    "" if step.end_time_s is None else units.format_duration_ko(step.end_time_s)
                ),
                "cv_cutoff_c_rate": (
                    "" if step.cv_cutoff_c_rate is None
                    else units.format_c_rate(step.cv_cutoff_c_rate)
                ),
                "dod_percent": "" if step.dod_percent is None else step.dod_percent,
                "loop_target": "" if step.loop_goto_step is None else step.loop_goto_step,
                "loop_count": "" if step.loop_count is None else step.loop_count,
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stream.getvalue(), encoding="utf-8-sig")
    return path


def export_preview(project: ScheduleProject, out_dir: Path) -> ExportResult:
    """Step table, Korean summary, and a project copy — nothing equipment-facing."""
    _require(project, "preview")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    steps_path = write_step_table(project, out_dir / "steps.csv")
    summary_path = out_dir / "summary.txt"
    summary_path.write_text(summarize_project(project).as_text() + "\n", encoding="utf-8")
    project_path = out_dir / "project.schproj"
    project.save(project_path)
    return ExportResult(
        "preview",
        (steps_path, summary_path, project_path),
        "소프트웨어 검토용입니다. 장비로 보내지 마세요.",
    )


def export_review_candidate(
    project: ScheduleProject,
    out_dir: Path,
    *,
    timestamp: str | None = None,
) -> ExportResult:
    """A reopen-only SCH for CTSEditorPro display review, with its manifest."""
    _require(project, "review_candidate")
    from .io.lab_header_writer import build_pne02_reopen_candidate
    from .io.reader import read_sch

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S.000")

    candidate = build_pne02_reopen_candidate(project, timestamp=stamp)
    sch_path = out_dir / REVIEW_CANDIDATE_NAME
    sch_path.write_bytes(candidate.data)
    parsed = read_sch(sch_path)
    steps = list(project.expand_steps())
    checks = [
        {
            "name": "layout_v3_612",
            "passed": parsed.payload_offset == 1760 and parsed.step_size == 612,
        },
        {"name": "step_count_matches", "passed": parsed.step_count == len(steps)},
    ]
    if not all(check["passed"] for check in checks):
        sch_path.unlink(missing_ok=True)
        raise ExportBlocked("생성한 파일을 다시 읽었을 때 구조가 맞지 않아 삭제했습니다.")

    digest = hashlib.sha256(sch_path.read_bytes()).hexdigest()
    project_path = out_dir / "source.schproj"
    project.save(project_path)
    steps_path = write_step_table(project, out_dir / "expected_steps.csv")
    checklist_path = out_dir / "REVIEW_CHECKLIST.md"
    checklist_path.write_text(
        _review_checklist(project, digest, len(steps)), encoding="utf-8"
    )

    warnings = list(candidate.warnings)
    warnings.extend(
        (
            "REOPEN ONLY. DO NOT START OR RUN THIS SCHEDULE ON EQUIPMENT.",
            "Only the 1760-byte header came from a CTSPro-authored PNE02 file; the step payload was software-generated.",
            "The exact output hash must pass CTSPro reopen/display/save-as review before promotion.",
        )
    )
    equipment = project.equipment
    write_validation_manifest(
        out_dir / f"{REVIEW_CANDIDATE_NAME}.manifest.json",
        {
            "schema": VALIDATION_MANIFEST_SCHEMA,
            "writer": "pne02_lab_header_reopen_candidate",
            "status": "CTSPro-reopen-candidate",
            "equipment_executable": False,
            "source_project": {
                "path": "source.schproj",
                "sha256": hashlib.sha256(project_path.read_bytes()).hexdigest(),
            },
            "template": {
                "path": str(candidate.template_path.name),
                "sha256": candidate.template_sha256,
                "size": candidate.template_path.stat().st_size,
                "usage": "header bytes 0..1759 only",
            },
            "target_profile": {
                "status": "review_target",
                "equipment": equipment.unit if equipment else "PNE02",
                "channel_profile": (
                    f"max {equipment.max_current_mA:g} mA; reopen only"
                    if equipment and equipment.max_current_mA
                    else "reopen only"
                ),
                "ctspro_version": (equipment.ctspro_build if equipment else None) or "user to record",
                "sch_version": "0x00010003",
                "step_size": 612,
                "cell_profile": project.cell_profile.to_dict(),
            },
            "output": {
                "path": REVIEW_CANDIDATE_NAME,
                "sha256": digest,
                "size": sch_path.stat().st_size,
            },
            "changed_fields": [
                {"scope": "header", "fields": ["timestamps", "name", "PNE02 safety blocks"]},
                {
                    "scope": "payload",
                    "range": [1760, sch_path.stat().st_size],
                    "source": "compiled StepIntent list",
                },
            ],
            "evidence": [
                "planning/PATTERN_VALIDATION_PLAN.md",
                "PNE02 v3/612 corpus and Gate D structural harness",
            ],
            "validation": {
                "all_passed": True,
                "checks": checks,
                "equipment_smoke_test": "not_run",
            },
            "warnings": list(dict.fromkeys(warnings)),
        },
    )
    return ExportResult(
        "review_candidate",
        (sch_path, project_path, steps_path, checklist_path),
        f"SHA-256 {digest[:16]}… · CTSPro 에서 열어보기 전용입니다. 절대 실행하지 마세요.",
    )


def _review_checklist(project: ScheduleProject, digest: str, step_count: int) -> str:
    summary = summarize_project(project)
    equipment = project.equipment
    lines = [
        f"# CTSPro 검토 체크리스트 — {project.name}",
        "",
        "> 이 파일은 **열어서 확인만** 하기 위한 후보입니다. 장비에서 실행하지 마세요.",
        "",
        f"- 대상 장비: {equipment.describe() if equipment else '미지정'}",
        f"- 후보 SHA-256: `{digest}`",
        f"- 스텝 수: {step_count}",
        f"- 예상 소요: {summary.duration_text}",
        "",
        "## 확인 항목",
        "",
        "- [ ] CTSEditorPro 에서 파일이 열린다",
        f"- [ ] 스텝 수가 {step_count} 개로 표시된다",
        "- [ ] 각 스텝의 전류/전압/시간 값이 expected_steps.csv 와 일치한다",
        "- [ ] LOOP 대상과 반복 횟수가 일치한다",
        "- [ ] Save As 로 다시 저장했을 때 값이 유지된다",
        "- [ ] 저장본의 SHA-256 을 아래에 기록했다",
        "",
        "| 항목 | 값 |",
        "| --- | --- |",
        "| 검토자 | |",
        "| 검토일 | |",
        "| CTSPro 버전 | |",
        "| Save As 경로 | |",
        "| Save As SHA-256 | |",
        "| 결과 (통과/실패) | |",
        "",
        "## 스케줄 요약",
        "",
        "```",
        summary.as_text(),
        "```",
        "",
    ]
    return "\n".join(lines)


__all__ = [
    "ExportBlocked",
    "ExportResult",
    "REVIEW_CANDIDATE_NAME",
    "export_preview",
    "export_review_candidate",
    "write_step_table",
]
