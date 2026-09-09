"""CLI entry: python -m pne_scheduler"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .ir.project import ScheduleProject


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pne_scheduler",
        description="Build PNE .sch schedule files from .schproj projects.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser(
        "build",
        help="Compile a .schproj with the experimental, non-equipment-ready writer",
    )
    build.add_argument("project", type=Path, help="Input .schproj path")
    build.add_argument("-o", "--output", type=Path, required=True, help="Output .sch path")
    build.add_argument(
        "--allow-experimental-output",
        action="store_true",
        help="Acknowledge that output is not validated for CTSPro or equipment execution",
    )
    build.add_argument(
        "--manifest",
        type=Path,
        help="Validation manifest path (default: <output>.manifest.json)",
    )

    workspace = sub.add_parser(
        "workspace",
        help="Open the unified workspace (setup, protocol, procedure, validate, export)",
    )
    workspace.add_argument("project", type=Path, nargs="?", help="Optional .schproj to open")

    summary = sub.add_parser(
        "summary", help="Print a plain-language Korean summary of a project"
    )
    summary.add_argument("project", type=Path, help="Input .schproj path")

    import_sch = sub.add_parser(
        "import-sch",
        help="Open an existing .sch and report what may be edited in place",
    )
    import_sch.add_argument("source", type=Path, help="Existing .sch file")
    import_sch.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="STEP:FIELD=VALUE",
        help="Stage an edit, e.g. --set 3:fVref=25.0 (repeatable)",
    )
    import_sch.add_argument(
        "--plan-out", type=Path, help="Write the resulting patch plan as JSON"
    )

    library = sub.add_parser("library", help="List or save methods in the library")
    library.add_argument("method_id", nargs="?", help="Show every version of one method")
    library.add_argument(
        "--save",
        type=Path,
        metavar="PROJECT",
        help="Save a .schproj's module list as a new method version",
    )
    library.add_argument("--name", help="Method name to save under (with --save)")
    library.add_argument("--description", default="", help="Optional description")

    info = sub.add_parser("info", help="Show project summary")
    info.add_argument("project", type=Path, help="Input .schproj path")

    view = sub.add_parser("view", help="Open schedule viewer GUI")
    view.add_argument("sch", type=Path, nargs="?", help="Optional .sch file to open")

    edit = sub.add_parser("edit", help="Open project editor GUI (bulk module edit)")
    edit.add_argument("project", type=Path, nargs="?", help="Optional .schproj to open")

    flow = sub.add_parser("flow", help="Open the module connection flow editor")
    flow.add_argument("project", type=Path, nargs="?", help="Optional .schproj to open")

    resume = sub.add_parser("resume", help="Resume interrupted experiment from .sch + data")
    resume.add_argument("sch", type=Path, help="Original .sch schedule")
    resume.add_argument("data", type=Path, help="StepEnd or raw CSV")
    resume.add_argument("-o", "--output", type=Path, required=True, help="Output resumed .sch")
    resume.add_argument("--step", type=int, help="Override resume SCH step")
    resume.add_argument("--loops", type=int, help="Override remaining loop count")
    resume.add_argument("--plan-only", action="store_true", help="Print plan without writing")
    resume.add_argument(
        "--manifest",
        type=Path,
        help="Validation manifest path (default: <output>.manifest.json)",
    )

    bulk = sub.add_parser("bulk-edit", help="Bulk-edit module params in a .schproj")
    bulk.add_argument("project", type=Path, help="Input .schproj path")
    bulk.add_argument(
        "--set",
        action="append",
        metavar="KEY=VALUE",
        required=True,
        help="Parameter to set (repeatable)",
    )
    sel = bulk.add_mutually_exclusive_group()
    sel.add_argument("--all", action="store_true", help="Apply to all modules")
    sel.add_argument("--ids", type=str, help="Comma-separated module ids")
    sel.add_argument("--type", dest="module_type", type=str, help="Filter by module type")
    bulk.add_argument("-o", "--output", type=Path, help="Save to path (default: overwrite input)")

    compare = sub.add_parser(
        "compare",
        help="Compare a controlled before/after SCH pair",
    )
    compare.add_argument("before", type=Path, help="Baseline .sch path")
    compare.add_argument("after", type=Path, help="Single-field-change .sch path")
    compare.add_argument("-o", "--output", type=Path, help="Optional JSON report path")

    patch = sub.add_parser(
        "patch-sch",
        help="Write a template-preserving SCH clone from an evidence-gated patch plan",
    )
    patch.add_argument("template", type=Path, help="CTSPro-authored template .sch")
    patch.add_argument("plan", type=Path, help="SCH patch-plan JSON")
    patch.add_argument("-o", "--output", type=Path, required=True, help="Output .sch path")
    patch.add_argument(
        "--manifest",
        "--report",
        dest="manifest",
        type=Path,
        help="Validation manifest path (default: <output>.manifest.json)",
    )
    patch.add_argument(
        "--allow-analysis-output",
        action="store_true",
        help="Acknowledge that the output is not approved for equipment execution",
    )
    patch.add_argument(
        "--allow-unverified-fields",
        action="store_true",
        help="Allow offline patching of fields that are not writer-ready",
    )

    review_pack = sub.add_parser(
        "pattern-review-pack",
        help="Generate deterministic PNE02 reopen-only pattern candidates",
    )
    review_pack.add_argument("output", type=Path, help="Output pack directory")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "workspace":
        from .ui import launch_workspace

        return launch_workspace(args.project)

    if args.command == "summary":
        from .ir.loader import ProjectLoadError, load_project_lenient
        from .release import evaluate_release
        from .report.summary import summarize_project

        try:
            load = load_project_lenient(args.project)
        except ProjectLoadError as exc:
            print(f"프로젝트를 열 수 없습니다: {exc}", file=sys.stderr)
            return 2
        for repair in load.repairs:
            print(f"수정됨: {repair}", file=sys.stderr)
        print(summarize_project(load.project).as_text())
        state = evaluate_release(load.project)
        print()
        if state.label is not None:
            print(f"릴리스 등급: {state.label.label} ({state.label.label_ko})")
            print(f"  {state.label.meaning_ko}")
            for reason in state.label.reasons:
                print(f"  · {reason}")
        print(f"진행 상태: {state.stage_label}")
        for option in state.options:
            mark = " ← 권장" if option.recommended else ""
            print(f"  [{option.status_text}] {option.title}{mark}")
            for blocker in option.blockers:
                print(f"        · {blocker}")
        return 0

    if args.command == "import-sch":
        from .import_session import ImportSession

        try:
            session = ImportSession.open(args.source)
        except (OSError, ValueError) as exc:
            print(f"열 수 없습니다: {exc}", file=sys.stderr)
            return 2
        version = session.sch_version
        print(f"원본: {session.path}")
        print(f"  SHA-256: {session.sha256}")
        print(
            "  버전: "
            + (f"0x{version:08X}" if version is not None else "알 수 없음")
            + f" · 스텝 {session.step_count}개"
        )
        editable = session.editable_fields()
        print()
        if editable:
            print("원본을 고쳐 쓸 수 있는 필드 (CTSPro 재열기 근거로 승격된 것만):")
            for item in editable:
                print(f"  {item.name:<16} @{item.offset:<5} {item.dtype:<8} {item.evidence}")
        else:
            print("이 버전에는 근거로 승격된 필드가 없어 원본을 고칠 수 없습니다.")
        for raw in args.set:
            try:
                location, value = raw.split("=", 1)
                step_text, field_name = location.split(":", 1)
                session.stage(int(step_text), field_name, float(value))
            except ValueError:
                print(
                    f"편집 형식이 잘못되었습니다: {raw} (예: 3:fVref=25.0)",
                    file=sys.stderr,
                )
                return 2

        if args.set:
            proposal = session.propose_patch()
            print()
            for note in proposal.notes:
                print(f"  {note}")
            for item in proposal.rejected:
                print(f"  거부 스텝 {item.step_no} {item.field}: {item.reason}")
            for warning in proposal.warnings:
                print(f"  경고: {warning}")
            if not proposal.ok:
                print("적용할 수 있는 편집이 없습니다.", file=sys.stderr)
                return 2
            if args.plan_out:
                proposal.plan.save(args.plan_out)
                print()
                print(f"패치 계획을 저장했습니다: {args.plan_out}")
                print(
                    "적용: pne_scheduler patch-sch "
                    f'"{session.path}" "{args.plan_out}" -o <출력.sch> '
                    "--allow-analysis-output"
                )
            else:
                print()
                print("--plan-out 으로 계획을 저장한 뒤 patch-sch 로 적용하십시오.")
            return 0

        clone = session.propose_clone()
        print()
        print("초안으로 복제하면 버려지는 것:")
        for item in clone.dropped:
            print(f"  · {item}")
        return 0

    if args.command == "library":
        from .library import MethodLibrary

        store = MethodLibrary()
        if args.save:
            if not args.name:
                print("--save 에는 --name 이 필요합니다.", file=sys.stderr)
                return 2
            from .ir.loader import ProjectLoadError, load_project_lenient

            try:
                load = load_project_lenient(args.save)
            except ProjectLoadError as exc:
                print(f"프로젝트를 열 수 없습니다: {exc}", file=sys.stderr)
                return 2
            for repair in load.repairs:
                print(f"수정됨: {repair}", file=sys.stderr)
            from .library import save_project_as_method

            try:
                entry = save_project_as_method(
                    store,
                    load.project,
                    name=args.name,
                    description=args.description,
                )
            except ValueError as exc:
                print(f"저장할 수 없습니다: {exc}", file=sys.stderr)
                return 2
            print(f"저장했습니다: {entry.label} · 구간 {entry.module_count}개")
            print(f"  {entry.path}")
            return 0
        if args.method_id:
            versions = store.versions(args.method_id)
            if not versions:
                print(f"저장된 방법이 없습니다: {args.method_id}", file=sys.stderr)
                return 2
            for entry in versions:
                print(
                    f"v{entry.version:<4} 구간 {entry.module_count:<3} "
                    f"{entry.equipment_unit or '장비 미지정':<8} {entry.saved_at}"
                )
            return 0
        methods = store.methods()
        if not methods:
            print(f"저장된 방법이 없습니다. ({store.root})")
            return 0
        for entry in methods:
            print(
                f"{entry.method_id:<28} {entry.name:<24} v{entry.version:<4} "
                f"구간 {entry.module_count:<3} {entry.equipment_unit or '-':<8} {entry.saved_at}"
            )
        return 0

    if args.command == "info":
        project = ScheduleProject.load(args.project)
        print(f"Name: {project.name}")
        print(f"SCH version: 0x{project.sch_version:08X}")
        print(f"Cell: {project.cell_profile.nominal_capacity_mAh:.1f} mAh")
        print(f"Modules: {len(project.modules)}")
        return 0

    if args.command == "build":
        from .io.writer import write_sch
        from .io.validation_manifest import (
            default_manifest_path,
            experimental_build_manifest,
            write_validation_manifest,
        )

        if not args.allow_experimental_output:
            print(
                "Refusing to write an SCH file: from-scratch builds are not yet "
                "equipment-ready (step compiler / smoke test incomplete). Pass "
                "--allow-experimental-output only for offline development.",
                file=sys.stderr,
            )
            return 2
        from .validate.preflight import validate_project

        project = ScheduleProject.load(args.project)
        manifest_path = args.manifest or default_manifest_path(args.output)
        output_existed = args.output.exists()
        manifest_existed = manifest_path.exists()
        try:
            preflight = validate_project(project, purpose="experimental_build")
            if preflight.errors:
                details = "; ".join(
                    f"{issue.code}: {issue.message}" for issue in preflight.errors
                )
                raise ValueError(f"Preflight failed: {details}")
            preflight_warnings = [
                f"{issue.code}: {issue.message}" for issue in preflight.warnings
            ]
            compile_warnings = list(
                dict.fromkeys([*preflight_warnings, *write_sch(project, args.output)])
            )
            manifest = experimental_build_manifest(
                args.project,
                args.output,
                sch_version=project.sch_version,
                cell_profile=project.cell_profile.to_dict(),
                extra_warnings=compile_warnings,
            )
            write_validation_manifest(manifest_path, manifest)
        except (OSError, TypeError, ValueError) as exc:
            if not output_existed:
                args.output.unlink(missing_ok=True)
            if not manifest_existed:
                manifest_path.unlink(missing_ok=True)
            print(f"Experimental SCH build failed: {exc}", file=sys.stderr)
            return 2
        print(f"Wrote experimental output to {args.output}")
        print(f"Wrote validation manifest to {manifest_path}")
        for warning in compile_warnings:
            print(f"  WARN: {warning}")
        print("WARNING: Do not load or execute this file on PNE equipment.")
        return 0

    if args.command == "view":
        from .ui.schedule_viewer import launch_schedule_viewer

        launch_schedule_viewer(args.sch)
        return 0

    if args.command == "edit":
        from .ui.project_editor import launch_project_editor

        launch_project_editor(args.project)
        return 0

    if args.command == "flow":
        from .ui.flow_editor import launch_flow_editor

        launch_flow_editor(args.project)
        return 0

    if args.command == "resume":
        from .resume import build_resume_plan, splice_resume_schedule

        if args.plan_only:
            plan = build_resume_plan(
                args.sch,
                args.data,
                resume_sch_step=args.step,
                remaining_loop_count=args.loops,
            )
            cp = plan.checkpoint
            print(f"Resume SCH step: {plan.resume_sch_step}")
            print(f"Last completed: SCH {cp.last_completed_sch_step} (CTS {cp.last_completed_cts_step})")
            print(f"Detail: {cp.detail}")
            print(f"Remaining loops: {plan.remaining_loop_count}")
            for w in plan.warnings:
                print(f"  WARN: {w}")
            return 0

        result = splice_resume_schedule(
            args.sch,
            args.data,
            args.output,
            resume_sch_step=args.step,
            remaining_loop_count=args.loops,
            validation_manifest_path=args.manifest,
        )
        print(f"Wrote {result.output_path}")
        print(f"Wrote validation manifest to {result.manifest_path}")
        print(result.plan.splice_summary)
        return 0

    if args.command == "bulk-edit":
        from .edit import apply_bulk_edit, parse_set_args

        project = ScheduleProject.load(args.project)
        patch = parse_set_args(args.set)
        module_ids = [s.strip() for s in args.ids.split(",")] if args.ids else None
        module_types = [args.module_type] if args.module_type else None
        result = apply_bulk_edit(
            project,
            patch,
            module_ids=module_ids,
            module_types=module_types,
            all_modules=args.all or (module_ids is None and module_types is None),
        )
        out = args.output or args.project
        project.save(out)
        print(f"Updated {result.updated_count} module(s) → {out}")
        for change in result.changes:
            print(
                f"  {change.module_id}.{change.key}: "
                f"{change.old_value!r} → {change.new_value!r}"
            )
        for err in result.errors:
            print(f"  ERROR: {err}")
        return 0 if not result.errors else 1

    if args.command == "compare":
        import json

        from .tools.compare_sch import compare_sch_files

        report = compare_sch_files(args.before, args.after)
        rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
            print(f"Wrote {args.output}")
        else:
            print(rendered, end="")
        return 0 if report["compatible"] else 2

    if args.command == "patch-sch":
        import json

        from .io.template_writer import SchPatchPlan, apply_sch_patch
        from .io.validation_manifest import (
            default_manifest_path,
            write_validation_manifest,
        )

        manifest_path = args.manifest or default_manifest_path(args.output)
        output_existed = args.output.exists()
        manifest_existed = manifest_path.exists()
        try:
            plan = SchPatchPlan.load(args.plan)
            result = apply_sch_patch(
                args.template,
                plan,
                args.output,
                allow_analysis_output=args.allow_analysis_output,
                allow_unverified_fields=args.allow_unverified_fields,
            )
            write_validation_manifest(manifest_path, result.report)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            if not output_existed:
                args.output.unlink(missing_ok=True)
            if not manifest_existed:
                manifest_path.unlink(missing_ok=True)
            print(f"SCH patch failed: {exc}", file=sys.stderr)
            return 2

        print(f"Wrote analysis-only SCH clone to {result.output_path}")
        print(f"Wrote validation manifest to {manifest_path}")
        print("WARNING: Do not execute this file on PNE equipment.")
        return 0

    if args.command == "pattern-review-pack":
        from .tools.pattern_review_pack import build_pattern_review_pack

        try:
            result = build_pattern_review_pack(args.output)
        except (OSError, TypeError, ValueError) as exc:
            print(f"Pattern review pack failed: {exc}", file=sys.stderr)
            return 2
        print(f"Wrote {result.pattern_count} reopen-only candidates to {result.output_dir}")
        print("WARNING: Open for display review only. Do not start or run these schedules.")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
