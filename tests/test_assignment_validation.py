from __future__ import annotations

from pathlib import Path

from hamrforge.assignment import validate_assignment


def write_assignment(path: Path, content: str) -> Path:
    assignment_dir = path / "assignment"
    assignment_dir.mkdir()
    (assignment_dir / "assignment.yml").write_text(content, encoding="utf-8")
    return assignment_dir


def test_sample_assignment_is_valid() -> None:
    result = validate_assignment(Path("assignments/byte-class"))

    assert result.is_valid
    assert result.errors == []


def test_missing_required_fields_are_reported(tmp_path: Path) -> None:
    assignment_dir = write_assignment(
        tmp_path,
        """
title: Broken Assignment
submission:
  required_files:
    - main.cpp
""",
    )

    result = validate_assignment(assignment_dir)

    assert not result.is_valid
    assert "Missing required field: slug" in result.errors
    assert "Missing required field: checks" in result.errors


def test_submission_required_files_must_be_non_empty_list(tmp_path: Path) -> None:
    assignment_dir = write_assignment(
        tmp_path,
        """
title: Broken Assignment
slug: broken
language: cpp
standard: c++17
compiler: g++
max_score: 100
submission:
  required_files: []
checks:
  - name: Required files
    type: file_check
    points: 10
""",
    )

    result = validate_assignment(assignment_dir)

    assert not result.is_valid
    assert "submission.required_files must be a non-empty list." in result.errors


def test_runner_setting_must_be_string_or_mapping(tmp_path: Path) -> None:
    assignment_dir = write_assignment(
        tmp_path,
        """
title: Broken Assignment
slug: broken
language: cpp
standard: c++17
compiler: g++
max_score: 100
runner: []
submission:
  required_files:
    - main.cpp
checks:
  - name: Required files
    type: file_check
    points: 10
""",
    )

    result = validate_assignment(assignment_dir)

    assert not result.is_valid
    assert "runner must be a non-empty string or mapping." in result.errors


def test_runner_image_must_be_non_empty_string(tmp_path: Path) -> None:
    assignment_dir = write_assignment(
        tmp_path,
        """
title: Broken Assignment
slug: broken
language: cpp
standard: c++17
compiler: g++
max_score: 100
runner:
  type: podman
  image: ""
submission:
  required_files:
    - main.cpp
checks:
  - name: Required files
    type: file_check
    points: 10
""",
    )

    result = validate_assignment(assignment_dir)

    assert not result.is_valid
    assert "runner.image must be a non-empty string." in result.errors


def test_missing_assignment_file_is_reported(tmp_path: Path) -> None:
    result = validate_assignment(tmp_path)

    assert not result.is_valid
    assert result.errors[0].startswith("Missing assignment file:")
