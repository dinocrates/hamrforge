from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from hamrforge.grading import GradeError, grade_submission
from hamrforge.runner import CompileRequest, CompileResult


class AlwaysFailRunner:
    def compile_cpp(self, request: CompileRequest, workspace: Path) -> CompileResult:
        return CompileResult(returncode=1, stdout="", stderr="fake compiler failure")

    def run_executable(self, request, workspace: Path):
        raise AssertionError("run_executable should not be called when compilation fails")


def zip_folder(source_dir: Path, zip_path: Path) -> Path:
    with ZipFile(zip_path, "w") as archive:
        for path in source_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir))
    return zip_path


def test_grade_perfect_submission_awards_file_check_points(tmp_path: Path) -> None:
    submission = zip_folder(Path("fixtures/perfect"), tmp_path / "perfect.zip")

    result = grade_submission(Path("assignments/byte-class"), submission, tmp_path / "reports")

    assert result.score == 40
    assert result.max_score == 40
    assert result.checks[0].passed
    assert result.checks[1].passed
    assert result.checks[2].passed
    assert result.checks[3].passed
    assert result.checks[4].passed
    assert result.checks[5].passed
    assert result.checks[6].passed
    assert result.report_json_path.exists()
    assert result.report_md_path.exists()

    report = json.loads(result.report_json_path.read_text(encoding="utf-8"))
    assert report["score"] == 40
    assert report["checks"][0]["feedback"] == "All required files were found."
    assert report["checks"][1]["type"] == "compile"
    assert report["checks"][2]["type"] == "expression_test"


def test_grade_directory_submission_matches_zip_behavior(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for source in Path("fixtures/perfect").iterdir():
        if source.is_file():
            (workspace / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    result = grade_submission(Path("assignments/byte-class"), workspace, tmp_path / "reports")

    assert result.score == 40
    assert result.max_score == 40
    assert all(check.passed for check in result.checks)


def test_grade_missing_files_submission_loses_file_check_points(tmp_path: Path) -> None:
    submission = zip_folder(Path("fixtures/missing-files"), tmp_path / "missing-files.zip")

    result = grade_submission(Path("assignments/byte-class"), submission, tmp_path / "reports")

    assert result.score == 0
    assert result.max_score == 40
    assert not result.checks[0].passed
    assert result.checks[0].missing_files == ["Byte.cpp"]
    assert result.flags == ["compile_failed", "console_io_failed", "expression_test_failed", "missing_required_files"]


def test_hpp_file_satisfies_required_h_header(tmp_path: Path) -> None:
    submission = tmp_path / "xcode-style.zip"
    with ZipFile(submission, "w") as archive:
        archive.writestr(
            "Byte.hpp",
            """
#pragma once
#include <string>
class Byte {
public:
    Byte() : bits{0, 0, 0, 0, 0, 0, 0, 0} {}
    void setValue(int value) {
        for (int i = 0; i < 8; ++i) bits[i] = (value >> i) & 1;
    }
    int at(int index) { return index >= 0 && index < 8 ? bits[index] : 0; }
    std::string toString() {
        std::string result;
        for (int i = 7; i >= 0; --i) result += bits[i] ? '1' : '0';
        return result;
    }
    int toInt() const { return bitsToInt(); }
private:
    int bits[8];
    int bitsToInt() const {
        int value = 0;
        for (int i = 0; i < 8; ++i) value += bits[i] << i;
        return value;
    }
};
""",
        )
        archive.writestr("Byte.cpp", '#include "Byte.hpp"\n')
        archive.writestr("main.cpp", '#include "Byte.hpp"\nint main() { Byte b; b.setValue(99); return 0; }\n')

    result = grade_submission(Path("assignments/byte-class"), submission, tmp_path / "reports")

    assert result.score == 40
    assert result.checks[0].passed
    assert result.checks[1].passed
    assert result.checks[2].passed


def test_compile_error_submission_loses_compile_points(tmp_path: Path) -> None:
    submission = zip_folder(Path("fixtures/compile-error"), tmp_path / "compile-error.zip")

    result = grade_submission(Path("assignments/byte-class"), submission, tmp_path / "reports")

    assert result.score == 12
    assert result.max_score == 40
    assert result.checks[0].passed
    assert not result.checks[1].passed
    assert result.checks[1].type == "compile"
    assert result.checks[1].detail
    assert result.flags == ["compile_failed", "console_io_failed", "expression_test_failed"]

    report_md = result.report_md_path.read_text(encoding="utf-8")
    assert "Your code did not compile." in report_md
    assert "```text" in report_md


def test_infinite_loop_submission_times_out_console_io_check(tmp_path: Path) -> None:
    submission = zip_folder(Path("fixtures/infinite-loop"), tmp_path / "infinite-loop.zip")

    result = grade_submission(Path("assignments/byte-class"), submission, tmp_path / "reports")

    assert result.score == 28
    assert result.max_score == 40
    assert result.checks[1].passed
    assert not result.checks[6].passed
    assert result.checks[6].type == "console_io"
    assert result.checks[6].feedback == "Console I/O test timed out."
    assert "timed out" in result.checks[6].detail
    assert result.flags == ["console_io_failed"]


def test_huge_output_submission_has_captured_output_limited(tmp_path: Path) -> None:
    submission = zip_folder(Path("fixtures/huge-output"), tmp_path / "huge-output.zip")

    result = grade_submission(Path("assignments/byte-class"), submission, tmp_path / "reports")

    assert result.score == 40
    assert result.max_score == 40
    assert result.checks[6].passed
    assert "HamrForge output truncated after 65536 bytes" in result.checks[6].detail
    assert len(result.checks[6].detail) < 70000


def test_grade_uses_injected_runner_for_compile_checks(tmp_path: Path) -> None:
    submission = zip_folder(Path("fixtures/perfect"), tmp_path / "perfect.zip")

    result = grade_submission(
        Path("assignments/byte-class"),
        submission,
        tmp_path / "reports",
        runner=AlwaysFailRunner(),
    )

    assert result.score == 12
    assert not result.checks[1].passed
    assert result.checks[1].detail == "fake compiler failure"


def test_grade_rejects_unsupported_configured_runner(tmp_path: Path) -> None:
    assignment_dir = tmp_path / "assignment"
    assignment_dir.mkdir()
    assignment_source = Path("assignments/byte-class/assignment.yml").read_text(encoding="utf-8")
    assignment_text = assignment_source.replace("runner: local_unsafe", "runner: unknown_runner")
    (assignment_dir / "assignment.yml").write_text(assignment_text, encoding="utf-8")
    submission = zip_folder(Path("fixtures/perfect"), tmp_path / "perfect.zip")

    with pytest.raises(GradeError, match="Unsupported sandbox runner: unknown_runner"):
        grade_submission(assignment_dir, submission, tmp_path / "reports")


def test_expression_test_reports_expected_and_actual(tmp_path: Path) -> None:
    submission = zip_folder(Path("fixtures/bad-bit-order"), tmp_path / "bad-bit-order.zip")

    result = grade_submission(Path("assignments/byte-class"), submission, tmp_path / "reports")

    assert result.score == 32
    assert result.max_score == 40
    assert not result.checks[2].passed
    assert not result.checks[3].passed
    assert not result.checks[4].passed
    assert result.checks[5].passed
    assert "Expected: 99" in result.checks[2].detail
    assert "Actual: 198" in result.checks[2].detail
    assert result.flags == ["expression_test_failed"]


def test_console_io_check_accepts_any_output_when_only_run_completion_is_required(tmp_path: Path) -> None:
    submission = tmp_path / "run-completion.zip"
    with ZipFile(submission, "w") as archive:
        archive.write(Path("fixtures/perfect/Byte.h"), "Byte.h")
        archive.write(Path("fixtures/perfect/Byte.cpp"), "Byte.cpp")
        archive.writestr("main.cpp", '#include <iostream>\nint main() { std::cout << "wrong\\n"; return 0; }\n')

    result = grade_submission(Path("assignments/byte-class"), submission, tmp_path / "reports")

    assert result.checks[6].type == "console_io"
    assert result.checks[6].passed


def test_grade_rejects_zip_slip_paths(tmp_path: Path) -> None:
    submission = tmp_path / "unsafe.zip"
    with ZipFile(submission, "w") as archive:
        archive.writestr("../Byte.cpp", "not okay")

    with pytest.raises(GradeError, match="unsafe parent path"):
        grade_submission(Path("assignments/byte-class"), submission, tmp_path / "reports")


def test_grade_reports_unsupported_assignment_language(tmp_path: Path) -> None:
    assignment_dir = tmp_path / "java-assignment"
    assignment_dir.mkdir()
    (assignment_dir / "assignment.yml").write_text(
        """
title: Java Placeholder
slug: java-placeholder
language: java
standard: "21"
compiler: javac
max_score: 10
submission:
  required_files:
    - Main.java
checks:
  - name: Required files
    type: file_check
    points: 10
""",
        encoding="utf-8",
    )
    submission = tmp_path / "java.zip"
    with ZipFile(submission, "w") as archive:
        archive.writestr("Main.java", "class Main {}\n")

    with pytest.raises(GradeError, match="Unsupported assignment language: java"):
        grade_submission(assignment_dir, submission, tmp_path / "reports")


def test_grade_ignores_junk_folders(tmp_path: Path) -> None:
    submission = tmp_path / "junk.zip"
    with ZipFile(submission, "w") as archive:
        archive.writestr("Debug/Byte.cpp", "ignored")
        archive.writestr("main.cpp", "int main() { return 0; }")
        archive.writestr("Byte.h", "#pragma once")

    result = grade_submission(Path("assignments/byte-class"), submission, tmp_path / "reports")

    assert result.score == 18
    assert result.checks[0].missing_files == ["Byte.cpp"]
