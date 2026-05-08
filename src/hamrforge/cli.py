from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from hamrforge.assignment import validate_assignment
from hamrforge.batch import batch_grade
from hamrforge.catalog import CatalogError
from hamrforge.demo import reset_demo_data
from hamrforge.grading import GradeError, grade_submission
from hamrforge.runner import create_runner
from hamrforge.workspace import WorkspaceError, create_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hamrforge",
        description="HamrForge local C++ autograding tools.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate-assignment",
        help="Validate an assignment folder containing assignment.yml.",
    )
    validate_parser.add_argument("assignment", type=Path, help="Path to the assignment folder.")
    validate_parser.set_defaults(func=_validate_assignment_command)

    grade_parser = subparsers.add_parser(
        "grade",
        help="Grade one ZIP submission against an assignment. Currently supports required-file checks only.",
    )
    grade_parser.add_argument("assignment", type=Path, help="Path to the assignment folder.")
    grade_parser.add_argument("submission", type=Path, help="Path to the student ZIP submission.")
    grade_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Directory where report.json and report.md should be written.",
    )
    grade_parser.add_argument(
        "--runner",
        choices=["local_unsafe", "podman"],
        default=None,
        help="Override the assignment runner for this grading run.",
    )
    grade_parser.add_argument(
        "--runner-image",
        default=None,
        help="Container image to use with --runner podman.",
    )
    grade_parser.set_defaults(func=_grade_command)

    batch_parser = subparsers.add_parser(
        "batch-grade",
        help="Grade many ZIP submissions and write CSV, summary JSON, and feedback reports.",
    )
    batch_parser.add_argument("assignment", type=Path, help="Path to the assignment folder.")
    batch_parser.add_argument(
        "submissions",
        nargs="+",
        help="ZIP files or glob patterns. Quote globs if you want HamrForge to expand them.",
    )
    batch_parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Directory where batch reports should be written.",
    )
    batch_parser.set_defaults(func=_batch_grade_command)

    workspace_parser = subparsers.add_parser(
        "create-workspace",
        help="Create a server-side workspace from an assignment starter folder.",
    )
    workspace_parser.add_argument("assignment", type=Path, help="Path to the assignment folder.")
    workspace_parser.add_argument("--owner", default="demo-student", help="Workspace owner key.")
    workspace_parser.add_argument("--overwrite", action="store_true", help="Replace an existing workspace.")
    workspace_parser.set_defaults(func=_create_workspace_command)

    reset_demo_parser = subparsers.add_parser(
        "reset-demo-data",
        help="Reset demo student workspaces from starter files.",
    )
    reset_demo_parser.add_argument("--owner", default="demo-student", help="Demo owner key to reset.")
    reset_demo_parser.set_defaults(func=_reset_demo_data_command)

    web_parser = subparsers.add_parser(
        "web",
        help="Run the private instructor web UI.",
    )
    web_parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    web_parser.add_argument("--port", type=int, default=8000, help="Port to bind.")
    web_parser.set_defaults(func=_web_command)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def _validate_assignment_command(args: argparse.Namespace) -> int:
    result = validate_assignment(args.assignment)
    if result.is_valid:
        print(f"Assignment is valid: {result.assignment_path}")
        return 0

    print(f"Assignment is invalid: {result.assignment_path}")
    for error in result.errors:
        print(f"- {error}")
    return 1


def _grade_command(args: argparse.Namespace) -> int:
    out_dir = args.out or Path("reports") / args.submission.stem
    try:
        runner = create_runner(args.runner, image=args.runner_image) if args.runner else None
        result = grade_submission(args.assignment, args.submission, out_dir, runner=runner)
    except GradeError as exc:
        print(f"Could not grade submission: {exc}")
        return 1
    except ValueError as exc:
        print(f"Could not grade submission: {exc}")
        return 1

    print(f"Score: {result.score:g} / {result.max_score:g}")
    for check in result.checks:
        status = "passed" if check.passed else "failed"
        print(f"{check.name}: {status} ({check.score:g} / {check.max_score:g})")
        if check.missing_files:
            print("Missing files:")
            for filename in check.missing_files:
                print(f"- {filename}")
        if check.detail and not check.passed:
            print("Details:")
            print(check.detail)
    print("Reports saved:")
    print(f"- {result.report_json_path}")
    print(f"- {result.report_md_path}")
    return 0


def _batch_grade_command(args: argparse.Namespace) -> int:
    result = batch_grade(args.assignment, args.submissions, args.out)
    print(f"Graded: {result.graded_count}")
    print(f"Failed: {result.failed_count}")
    print(f"Reports saved:")
    print(f"- {result.grades_csv_path}")
    print(f"- {result.summary_json_path}")
    print(f"- {result.feedback_dir}")
    return 0 if result.failed_count == 0 else 1


def _create_workspace_command(args: argparse.Namespace) -> int:
    try:
        workspace = create_workspace(args.assignment, args.owner, overwrite=args.overwrite)
    except WorkspaceError as exc:
        print(f"Could not create workspace: {exc}")
        return 1

    print(f"Workspace ready: {workspace.path}")
    return 0


def _reset_demo_data_command(args: argparse.Namespace) -> int:
    try:
        result = reset_demo_data(owner_key=args.owner)
    except (WorkspaceError, CatalogError) as exc:
        print(f"Could not reset demo data: {exc}")
        return 1

    print(f"Demo data reset for: {result.owner_key}")
    print(f"Workspaces recreated: {result.reset_count}")
    for path in result.workspace_paths:
        print(f"- {path}")
    return 0


def _web_command(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("hamrforge.web:app", host=args.host, port=args.port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
