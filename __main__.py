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

    info = sub.add_parser("info", help="Show project summary")
    info.add_argument("project", type=Path, help="Input .schproj path")

    overview = sub.add_parser(
        "overview",
        help="Summarize the composed module recipes in a .schproj",
    )
    overview.add_argument("project", type=Path, help="Input .schproj path")

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

    explain = sub.add_parser(
        "explain",
        help="Narrate what a .sch schedule does (SOC hints, voltage setpoints, blocks)",
    )
    explain.add_argument("sch", type=Path, help="Input .sch path")
    explain.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print a structured JSON explanation",
    )
    explain.add_argument("-o", "--output", type=Path, help="Optional output path")

    patch = sub.add_parser(
        "patch-sch",
        help="Write a template-preserving SCH clone from an evidence-gated patch plan",
    )
    patch.add_argument("template", type=Path, help="CTSPro-authored template .sch")
    patch.add_argument("plan", type=Path, help="SCH patch-plan JSON")
    patch.add_argument("-o", "--output", type=Path, required=True, help="Output .sch path")
    patch.add_argument("--report", type=Path, help="Patch report JSON path")
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

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "info":
        project = ScheduleProject.load(args.project)
        print(f"Name: {project.name}")
        print(f"SCH version: 0x{project.sch_version:08X}")
        print(f"Cell: {project.cell_profile.nominal_capacity_mAh:.1f} mAh")
        print(f"Modules: {len(project.modules)}")
        return 0

    if args.command == "overview":
        from .protocol.overview import compose_overview, format_overview

        project = ScheduleProject.load(args.project)
        print(format_overview(compose_overview(project)), end="")
        return 0

    if args.command == "build":
        from .io.writer import write_sch_reloadable

        if not args.allow_experimental_output:
            print(
                "Refusing to write an SCH file: the writer still uses a placeholder "
                "header and is not equipment-ready. Pass --allow-experimental-output "
                "only for offline development.",
                file=sys.stderr,
            )
            return 2
        project = ScheduleProject.load(args.project)
        try:
            document = write_sch_reloadable(project, args.output)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"Wrote experimental output to {args.output}")
        print(f"Viewer reload OK: {len(document.steps)} steps at offset {document.payload_offset}.")
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
        )
        print(f"Wrote {result.output_path}")
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

    if args.command == "explain":
        import json

        from .io.sch_parser import parse_schedule_file
        from .protocol import explain_schedule, format_explanation

        try:
            document = parse_schedule_file(args.sch)
        except (OSError, ValueError) as exc:
            print(f"Could not read schedule: {exc}", file=sys.stderr)
            return 2

        explanation = explain_schedule(document)
        if args.as_json:
            rendered = json.dumps(explanation.to_dict(), indent=2, ensure_ascii=False) + "\n"
        else:
            rendered = format_explanation(explanation)
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
            print(f"Wrote {args.output}")
        else:
            print(rendered, end="")
        return 0

    if args.command == "patch-sch":
        import json

        from .io.template_writer import SchPatchPlan, apply_sch_patch

        try:
            plan = SchPatchPlan.load(args.plan)
            result = apply_sch_patch(
                args.template,
                plan,
                args.output,
                allow_analysis_output=args.allow_analysis_output,
                allow_unverified_fields=args.allow_unverified_fields,
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            print(f"SCH patch failed: {exc}", file=sys.stderr)
            return 2

        report_path = args.report or args.output.with_suffix(
            args.output.suffix + ".report.json"
        )
        report_path.write_text(
            json.dumps(result.report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote analysis-only SCH clone to {result.output_path}")
        print(f"Wrote patch report to {report_path}")
        print("WARNING: Do not execute this file on PNE equipment.")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
