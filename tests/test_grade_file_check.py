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

    assert result.score == 100
    assert result.max_score == 100
    assert result.checks[0].passed
    assert result.checks[1].passed
    assert result.checks[2].passed
    assert result.checks[3].passed
    assert result.checks[4].passed
    assert result.checks[5].passed
    assert result.report_json_path.exists()
    assert result.report_md_path.exists()

    report = json.loads(result.report_json_path.read_text(encoding="utf-8"))
    assert report["score"] == 100
    assert report["checks"][0]["feedback"] == "All required files were found."
    assert report["checks"][1]["type"] == "compile"
    assert report["checks"][2]["type"] == "expression_test"


def test_grade_missing_files_submission_loses_file_check_points(tmp_path: Path) -> None:
    submission = zip_folder(Path("fixtures/missing-files"), tmp_path / "missing-files.zip")

    result = grade_submission(Path("assignments/byte-class"), submission, tmp_path / "reports")

    assert result.score == 20
    assert result.max_score == 100
    assert not result.checks[0].passed
    assert result.checks[0].missing_files == ["Byte.cpp"]
    assert result.flags == ["console_io_failed", "expression_test_failed", "missing_required_files"]


def test_hpp_file_satisfies_required_h_header(tmp_path: Path) -> None:
    submission = tmp_path / "xcode-style.zip"
    with ZipFile(submission, "w") as archive:
        archive.writestr("main.cpp", "int main() { return 0; }")
        archive.writestr("Byte.hpp", "#pragma once")
        archive.writestr("Byte.cpp", '#include "Byte.hpp"\n')

    result = grade_submission(Path("assignments/byte-class"), submission, tmp_path / "reports")

    assert result.score == 30
    assert result.checks[0].passed
    assert result.checks[1].passed
    assert not result.checks[2].passed


def test_compile_error_submission_loses_compile_points(tmp_path: Path) -> None:
    submission = zip_folder(Path("fixtures/compile-error"), tmp_path / "compile-error.zip")

    result = grade_submission(Path("assignments/byte-class"), submission, tmp_path / "reports")

    assert result.score == 10
    assert result.max_score == 100
    assert result.checks[0].passed
    assert not result.checks[1].passed
    assert result.checks[1].type == "compile"
    assert result.checks[1].detail
    assert result.flags == ["compile_failed", "console_io_failed", "expression_test_failed"]

    report_md = result.report_md_path.read_text(encoding="utf-8")
    assert "Your code did not compile." in report_md
    assert "```text" in report_md


def test_grade_uses_injected_runner_for_compile_checks(tmp_path: Path) -> None:
    submission = zip_folder(Path("fixtures/perfect"), tmp_path / "perfect.zip")

    result = grade_submission(
        Path("assignments/byte-class"),
        submission,
        tmp_path / "reports",
        runner=AlwaysFailRunner(),
    )

    assert result.score == 10
    assert not result.checks[1].passed
    assert result.checks[1].detail == "fake compiler failure"


def test_expression_test_reports_expected_and_actual(tmp_path: Path) -> None:
    submission = zip_folder(Path("fixtures/bad-addition"), tmp_path / "bad-addition.zip")

    result = grade_submission(Path("assignments/byte-class"), submission, tmp_path / "reports")

    assert result.score == 60
    assert result.max_score == 100
    assert result.checks[2].passed
    assert result.checks[3].passed
    assert not result.checks[4].passed
    assert "Expected: 129" in result.checks[4].detail
    assert "Actual: 1" in result.checks[4].detail
    assert result.flags == ["console_io_failed", "expression_test_failed"]


def test_console_io_reports_missing_expected_output(tmp_path: Path) -> None:
    submission = zip_folder(Path("fixtures/bad-addition"), tmp_path / "bad-addition.zip")

    result = grade_submission(Path("assignments/byte-class"), submission, tmp_path / "reports")

    assert result.checks[5].type == "console_io"
    assert not result.checks[5].passed
    assert "Missing expected output:" in result.checks[5].detail
    assert "- 12" in result.checks[5].detail


def test_grade_rejects_zip_slip_paths(tmp_path: Path) -> None:
    submission = tmp_path / "unsafe.zip"
    with ZipFile(submission, "w") as archive:
        archive.writestr("../Byte.cpp", "not okay")

    with pytest.raises(GradeError, match="unsafe parent path"):
        grade_submission(Path("assignments/byte-class"), submission, tmp_path / "reports")


def test_grade_ignores_junk_folders(tmp_path: Path) -> None:
    submission = tmp_path / "junk.zip"
    with ZipFile(submission, "w") as archive:
        archive.writestr("Debug/Byte.cpp", "ignored")
        archive.writestr("main.cpp", "int main() { return 0; }")
        archive.writestr("Byte.h", "#pragma once")

    result = grade_submission(Path("assignments/byte-class"), submission, tmp_path / "reports")

    assert result.score == 20
    assert result.checks[0].missing_files == ["Byte.cpp"]
