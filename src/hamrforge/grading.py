from __future__ import annotations

import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from hamrforge.adapters import UnsupportedLanguageError, get_language_adapter
from hamrforge.assignment import load_assignment, validate_assignment
from hamrforge.models import CheckResult, GradeResult
from hamrforge.reports import write_reports
from hamrforge.runner import SandboxRunner, create_runner, runner_image_from_assignment, runner_name_from_assignment
from hamrforge.submission import SubmissionError, extract_submission


class GradeError(Exception):
    """Raised when a submission cannot be graded."""


def grade_submission(
    assignment_dir: Path,
    submission_path: Path,
    out_dir: Path,
    runner: SandboxRunner | None = None,
) -> GradeResult:
    validation = validate_assignment(assignment_dir)
    if not validation.is_valid:
        joined_errors = "; ".join(validation.errors)
        raise GradeError(f"assignment is invalid: {joined_errors}")

    assignment = load_assignment(assignment_dir.resolve())
    submission_path = submission_path.resolve()
    if not submission_path.exists():
        raise GradeError(f"submission path does not exist: {submission_path}")

    ignored_paths = _ignored_paths(assignment)
    if runner is None:
        try:
            runner = create_runner(
                runner_name_from_assignment(assignment),
                image=runner_image_from_assignment(assignment),
            )
        except ValueError as exc:
            raise GradeError(str(exc)) from exc

    try:
        with TemporaryDirectory(prefix="hamrforge-") as tmp:
            extracted_dir = Path(tmp) / "submission"
            if submission_path.is_dir():
                _copy_workspace_submission(submission_path, extracted_dir, ignored_paths)
            elif submission_path.suffix.lower() == ".zip":
                extract_submission(submission_path, extracted_dir, ignored_paths)
            else:
                raise GradeError("submission must be a .zip file or a directory.")
            result = _grade_checks(assignment, extracted_dir, out_dir, runner)
    except SubmissionError as exc:
        raise GradeError(str(exc)) from exc

    return result


def _copy_workspace_submission(source_dir: Path, destination: Path, ignored_paths: set[str]) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored_lower = {path.lower() for path in ignored_paths} | {".hamrforge"}
        return {name for name in names if name.lower() in ignored_lower}

    shutil.copytree(source_dir, destination, ignore=ignore)


def _grade_checks(
    assignment: dict[str, Any],
    extracted_dir: Path,
    out_dir: Path,
    runner: SandboxRunner,
) -> GradeResult:
    check_results: list[CheckResult] = []
    flags: list[str] = []
    required_files = list(assignment["submission"]["required_files"])
    try:
        language_adapter = get_language_adapter(str(assignment["language"]))
    except UnsupportedLanguageError as exc:
        raise GradeError(str(exc)) from exc

    for check in assignment["checks"]:
        check_type = check.get("type")
        if check_type == "file_check":
            result = _run_file_check(check, extracted_dir, required_files)
            if not result.passed:
                flags.append("missing_required_files")
            check_results.append(result)
            continue

        result = language_adapter.run_check(check, assignment, extracted_dir, runner)
        if result is None:
            continue
        if not result.passed:
            flags.append(_flag_for_check_type(result.type))
        check_results.append(result)

    if not check_results:
        raise GradeError("assignment does not define any supported checks.")

    score = sum(check.score for check in check_results)
    max_score = sum(check.max_score for check in check_results)
    report_json_path, report_md_path = write_reports(
        out_dir=out_dir,
        assignment_title=assignment["title"],
        score=score,
        max_score=max_score,
        checks=check_results,
        flags=sorted(set(flags)),
    )

    return GradeResult(
        assignment=assignment["title"],
        score=score,
        max_score=max_score,
        checks=check_results,
        flags=sorted(set(flags)),
        report_json_path=report_json_path,
        report_md_path=report_md_path,
    )


def _run_file_check(check: dict[str, Any], extracted_dir: Path, required_files: list[str]) -> CheckResult:
    max_score = float(check.get("points", 0))
    missing_files = _find_missing_required_files(extracted_dir, required_files)
    passed = not missing_files
    score = max_score if passed else 0.0
    feedback = "All required files were found." if passed else "Missing required files: " + ", ".join(missing_files)
    return CheckResult(
        name=check["name"],
        type="file_check",
        score=score,
        max_score=max_score,
        passed=passed,
        feedback=feedback,
        missing_files=missing_files,
    )


def _flag_for_check_type(check_type: str) -> str:
    return {
        "compile": "compile_failed",
        "expression_test": "expression_test_failed",
        "console_io": "console_io_failed",
    }.get(check_type, f"{check_type}_failed")


def _find_missing_required_files(extracted_dir: Path, required_files: list[str]) -> list[str]:
    discovered = {path.name for path in extracted_dir.rglob("*") if path.is_file()}
    return [filename for filename in required_files if not _required_file_is_present(filename, discovered)]


def _required_file_is_present(required_file: str, discovered_files: set[str]) -> bool:
    if required_file in discovered_files:
        return True

    required_path = Path(required_file)
    if required_path.suffix.lower() not in {".h", ".hpp"}:
        return False

    header_alternatives = {
        required_path.with_suffix(".h").name,
        required_path.with_suffix(".hpp").name,
    }
    return bool(header_alternatives & discovered_files)


def _ignored_paths(assignment: dict[str, Any]) -> set[str]:
    configured = assignment.get("submission", {}).get("ignored_paths", [])
    common = {".vs", "Debug", "Release", "x64", "__MACOSX"}
    return {str(path) for path in configured} | common
