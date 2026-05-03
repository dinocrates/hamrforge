from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from hamrforge.models import CheckResult
from hamrforge.runner import CompileRequest, RunRequest, SandboxRunner


class UnsupportedLanguageError(Exception):
    """Raised when an assignment requests a language HamrForge cannot grade yet."""


class LanguageAdapter(Protocol):
    language: str

    def run_check(
        self,
        check: dict[str, Any],
        assignment: dict[str, Any],
        extracted_dir: Path,
        runner: SandboxRunner,
    ) -> CheckResult | None:
        """Run an adapter-specific check, or return None for unsupported check types."""


class CppAdapter:
    language = "cpp"

    def run_check(
        self,
        check: dict[str, Any],
        assignment: dict[str, Any],
        extracted_dir: Path,
        runner: SandboxRunner,
    ) -> CheckResult | None:
        check_type = check.get("type")
        if check_type == "compile":
            return self._run_compile_check(check, assignment, extracted_dir, runner)
        if check_type == "expression_test":
            return self._run_expression_test(check, assignment, extracted_dir, runner)
        if check_type == "console_io":
            return self._run_console_io_check(check, assignment, extracted_dir, runner)
        return None

    def _run_compile_check(
        self,
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
        self,
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
        self,
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


def get_language_adapter(language: str) -> LanguageAdapter:
    normalized = language.strip().lower()
    if normalized in {"cpp", "c++"}:
        return CppAdapter()
    raise UnsupportedLanguageError(f"Unsupported assignment language: {language}. Rev 1 supports: cpp.")


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
