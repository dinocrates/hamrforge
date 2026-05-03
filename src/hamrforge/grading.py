from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from hamrforge.assignment import load_assignment, validate_assignment
from hamrforge.reports import write_reports
from hamrforge.runner import CompileRequest, LocalUnsafeRunner, RunRequest, SandboxRunner
from hamrforge.submission import SubmissionError, extract_submission


class GradeError(Exception):
    """Raised when a submission cannot be graded."""


@dataclass(frozen=True)
class CheckResult:
    name: str
    type: str
    score: float
    max_score: float
    passed: bool
    feedback: str
    missing_files: list[str]
    detail: str = ""


@dataclass(frozen=True)
class GradeResult:
    assignment: str
    score: float
    max_score: float
    checks: list[CheckResult]
    flags: list[str]
    report_json_path: Path
    report_md_path: Path


def grade_submission(
    assignment_dir: Path,
    submission_zip: Path,
    out_dir: Path,
    runner: SandboxRunner | None = None,
) -> GradeResult:
    validation = validate_assignment(assignment_dir)
    if not validation.is_valid:
        joined_errors = "; ".join(validation.errors)
        raise GradeError(f"assignment is invalid: {joined_errors}")

    assignment = load_assignment(assignment_dir.resolve())
    submission_zip = submission_zip.resolve()
    if not submission_zip.exists():
        raise GradeError(f"submission file does not exist: {submission_zip}")
    if submission_zip.suffix.lower() != ".zip":
        raise GradeError("submission must be a .zip file for this MVP checkpoint.")

    ignored_paths = _ignored_paths(assignment)

    runner = runner or LocalUnsafeRunner()

    try:
        with TemporaryDirectory(prefix="hamrforge-") as tmp:
            extracted_dir = Path(tmp) / "submission"
            extract_submission(submission_zip, extracted_dir, ignored_paths)
            result = _grade_checks(assignment, extracted_dir, out_dir, runner)
    except SubmissionError as exc:
        raise GradeError(str(exc)) from exc

    return result


def _grade_checks(
    assignment: dict[str, Any],
    extracted_dir: Path,
    out_dir: Path,
    runner: SandboxRunner,
) -> GradeResult:
    check_results: list[CheckResult] = []
    flags: list[str] = []
    required_files = list(assignment["submission"]["required_files"])

    for check in assignment["checks"]:
        check_type = check.get("type")
        if check_type == "file_check":
            result = _run_file_check(check, extracted_dir, required_files)
            if not result.passed:
                flags.append("missing_required_files")
            check_results.append(result)
        elif check_type == "compile":
            result = _run_compile_check(check, assignment, extracted_dir, runner)
            if not result.passed:
                flags.append("compile_failed")
            check_results.append(result)
        elif check_type == "expression_test":
            result = _run_expression_test(check, assignment, extracted_dir, runner)
            if not result.passed:
                flags.append("expression_test_failed")
            check_results.append(result)
        elif check_type == "console_io":
            result = _run_console_io_check(check, assignment, extracted_dir, runner)
            if not result.passed:
                flags.append("console_io_failed")
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


def _run_compile_check(
    check: dict[str, Any],
    assignment: dict[str, Any],
    extracted_dir: Path,
    runner: SandboxRunner,
) -> CheckResult:
    max_score = float(check.get("points", 0))
    cpp_files = sorted(path for path in extracted_dir.rglob("*.cpp") if path.is_file())
    if not cpp_files:
        return CheckResult(
            name=check["name"],
            type="compile",
            score=0.0,
            max_score=max_score,
            passed=False,
            feedback="No .cpp files were found to compile.",
            missing_files=[],
        )

    output_path = extracted_dir / "hamrforge_program"
    compile_result = runner.compile_cpp(
        CompileRequest(
            compiler=str(assignment["compiler"]),
            standard=str(assignment["standard"]),
            source_files=cpp_files,
            output_path=output_path,
        ),
        workspace=extracted_dir,
    )
    if compile_result.compiler_missing:
        return CheckResult(
            name=check["name"],
            type="compile",
            score=0.0,
            max_score=max_score,
            passed=False,
            feedback=f"Compiler not found: {assignment['compiler']}",
            missing_files=[],
        )
    if compile_result.timed_out:
        return CheckResult(
            name=check["name"],
            type="compile",
            score=0.0,
            max_score=max_score,
            passed=False,
            feedback="Compilation timed out.",
            missing_files=[],
            detail=compile_result.combined_output,
        )

    passed = compile_result.succeeded
    return CheckResult(
        name=check["name"],
        type="compile",
        score=max_score if passed else 0.0,
        max_score=max_score,
        passed=passed,
        feedback="Your code compiled successfully." if passed else "Your code did not compile.",
        missing_files=[],
        detail=compile_result.combined_output,
    )


def _run_expression_test(
    check: dict[str, Any],
    assignment: dict[str, Any],
    extracted_dir: Path,
    runner: SandboxRunner,
) -> CheckResult:
    max_score = float(check.get("points", 0))
    test_name = _safe_test_name(check["name"])
    harness_path = extracted_dir / f"hamrforge_{test_name}.cpp"
    output_path = extracted_dir / f"hamrforge_{test_name}"
    harness_path.write_text(_render_expression_harness(check, extracted_dir), encoding="utf-8")

    source_files = _student_support_cpp_files(extracted_dir) + [harness_path]
    compile_result = runner.compile_cpp(
        CompileRequest(
            compiler=str(assignment["compiler"]),
            standard=str(assignment["standard"]),
            source_files=source_files,
            output_path=output_path,
        ),
        workspace=extracted_dir,
    )
    if not compile_result.succeeded:
        if compile_result.compiler_missing:
            feedback = f"Compiler not found: {assignment['compiler']}"
        elif compile_result.timed_out:
            feedback = "Expression test compilation timed out."
        else:
            feedback = "Expression test did not compile."
        return CheckResult(
            name=check["name"],
            type="expression_test",
            score=0.0,
            max_score=max_score,
            passed=False,
            feedback=feedback,
            missing_files=[],
            detail=compile_result.combined_output,
        )

    run_result = runner.run_executable(RunRequest(executable_path=output_path), workspace=extracted_dir)
    if run_result.timed_out:
        return CheckResult(
            name=check["name"],
            type="expression_test",
            score=0.0,
            max_score=max_score,
            passed=False,
            feedback="Expression test timed out.",
            missing_files=[],
            detail=run_result.combined_output,
        )

    passed = run_result.succeeded
    return CheckResult(
        name=check["name"],
        type="expression_test",
        score=max_score if passed else 0.0,
        max_score=max_score,
        passed=passed,
        feedback="Expression test passed." if passed else "Expression test failed.",
        missing_files=[],
        detail=run_result.combined_output,
    )


def _run_console_io_check(
    check: dict[str, Any],
    assignment: dict[str, Any],
    extracted_dir: Path,
    runner: SandboxRunner,
) -> CheckResult:
    max_score = float(check.get("points", 0))
    cpp_files = _student_program_cpp_files(extracted_dir)
    if not cpp_files:
        return CheckResult(
            name=check["name"],
            type="console_io",
            score=0.0,
            max_score=max_score,
            passed=False,
            feedback="No .cpp files were found to compile for console I/O.",
            missing_files=[],
        )

    output_path = extracted_dir / f"hamrforge_console_{_safe_test_name(check['name'])}"
    compile_result = runner.compile_cpp(
        CompileRequest(
            compiler=str(assignment["compiler"]),
            standard=str(assignment["standard"]),
            source_files=cpp_files,
            output_path=output_path,
        ),
        workspace=extracted_dir,
    )
    if not compile_result.succeeded:
        if compile_result.compiler_missing:
            feedback = f"Compiler not found: {assignment['compiler']}"
        elif compile_result.timed_out:
            feedback = "Console I/O compilation timed out."
        else:
            feedback = "Console I/O program did not compile."
        return CheckResult(
            name=check["name"],
            type="console_io",
            score=0.0,
            max_score=max_score,
            passed=False,
            feedback=feedback,
            missing_files=[],
            detail=compile_result.combined_output,
        )

    run_result = runner.run_executable(
        RunRequest(executable_path=output_path, stdin=str(check.get("input", ""))),
        workspace=extracted_dir,
    )
    if run_result.timed_out:
        return CheckResult(
            name=check["name"],
            type="console_io",
            score=0.0,
            max_score=max_score,
            passed=False,
            feedback="Console I/O test timed out.",
            missing_files=[],
            detail=run_result.combined_output,
        )

    output = _normalize_output_for_comparison(run_result.stdout)
    missing_expected = [
        expected
        for expected in check.get("expected_contains", [])
        if _normalize_output_for_comparison(str(expected)) not in output
    ]
    passed = run_result.succeeded and not missing_expected
    detail = _console_io_detail(run_result.stdout, run_result.stderr, missing_expected)
    return CheckResult(
        name=check["name"],
        type="console_io",
        score=max_score if passed else 0.0,
        max_score=max_score,
        passed=passed,
        feedback="Console output matched expectations." if passed else "Console output did not match expectations.",
        missing_files=[],
        detail=detail,
    )


def _render_expression_harness(check: dict[str, Any], extracted_dir: Path) -> str:
    includes = "\n".join(f'#include "{_resolve_include(include, extracted_dir)}"' for include in check.get("include", []))
    setup = check.get("setup", "")
    expect = check["expect"]
    expression = expect["expression"]
    expected = _cpp_literal(expect["equals"])
    return f"""#include <iostream>
#include <string>
{includes}

int main() {{
{_indent_cpp(setup)}
    auto hamrforge_actual = ({expression});
    auto hamrforge_expected = ({expected});
    if (hamrforge_actual == hamrforge_expected) {{
        return 0;
    }}
    std::cout << "Expected: " << hamrforge_expected << "\\n";
    std::cout << "Actual: " << hamrforge_actual << "\\n";
    return 1;
}}
"""


def _student_support_cpp_files(extracted_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in extracted_dir.rglob("*.cpp")
        if path.is_file() and path.name != "main.cpp" and not path.name.startswith("hamrforge_")
    )


def _student_program_cpp_files(extracted_dir: Path) -> list[Path]:
    return sorted(path for path in extracted_dir.rglob("*.cpp") if path.is_file() and not path.name.startswith("hamrforge_"))


def _normalize_output_for_comparison(output: str) -> str:
    return output.replace("\r\n", "\n").replace("\r", "\n")


def _console_io_detail(stdout: str, stderr: str, missing_expected: list[Any]) -> str:
    lines: list[str] = []
    if missing_expected:
        lines.append("Missing expected output:")
        lines.extend(f"- {expected}" for expected in missing_expected)
    lines.append("Program stdout:")
    lines.append(stdout.rstrip() if stdout else "<empty>")
    if stderr:
        lines.append("Program stderr:")
        lines.append(stderr.rstrip())
    return "\n".join(lines)


def _resolve_include(include: str, extracted_dir: Path) -> str:
    include_path = Path(include)
    if (extracted_dir / include_path).exists():
        return include
    if include_path.suffix.lower() in {".h", ".hpp"}:
        for suffix in (".h", ".hpp"):
            alternative = include_path.with_suffix(suffix)
            if (extracted_dir / alternative).exists():
                return alternative.as_posix()
    return include


def _cpp_literal(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'std::string("{escaped}")'
    return str(value)


def _indent_cpp(code: str) -> str:
    if not code.strip():
        return ""
    return "\n".join(f"    {line}" if line.strip() else "" for line in code.rstrip().splitlines())


def _safe_test_name(name: str) -> str:
    safe = "".join(character.lower() if character.isalnum() else "_" for character in name)
    return "_".join(part for part in safe.split("_") if part)


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
