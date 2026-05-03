from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class AssignmentLoadError(Exception):
    """Raised when an assignment file cannot be read or parsed."""


@dataclass(frozen=True)
class ValidationResult:
    assignment_path: Path
    errors: list[str]

    @property
    def is_valid(self) -> bool:
        return not self.errors


REQUIRED_TOP_LEVEL_FIELDS = (
    "title",
    "slug",
    "language",
    "standard",
    "compiler",
    "max_score",
    "submission",
    "checks",
)


def load_assignment(assignment_dir: Path) -> dict[str, Any]:
    assignment_path = assignment_dir / "assignment.yml"
    if not assignment_path.exists():
        raise AssignmentLoadError(f"Missing assignment file: {assignment_path}")

    try:
        loaded = yaml.safe_load(assignment_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise AssignmentLoadError(f"Could not parse {assignment_path}: {exc}") from exc
    except OSError as exc:
        raise AssignmentLoadError(f"Could not read {assignment_path}: {exc}") from exc

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise AssignmentLoadError("assignment.yml must contain a YAML mapping at the top level.")
    return loaded


def validate_assignment(assignment_dir: Path) -> ValidationResult:
    assignment_dir = assignment_dir.resolve()
    assignment_path = assignment_dir / "assignment.yml"
    errors: list[str] = []

    try:
        assignment = load_assignment(assignment_dir)
    except AssignmentLoadError as exc:
        return ValidationResult(assignment_path=assignment_path, errors=[str(exc)])

    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in assignment:
            errors.append(f"Missing required field: {field}")

    _validate_non_empty_string(assignment, "title", errors)
    _validate_non_empty_string(assignment, "slug", errors)
    _validate_non_empty_string(assignment, "language", errors)
    _validate_non_empty_string(assignment, "standard", errors)
    _validate_non_empty_string(assignment, "compiler", errors)
    _validate_positive_number(assignment, "max_score", errors)
    _validate_submission(assignment.get("submission"), errors)
    _validate_checks(assignment.get("checks"), errors)

    return ValidationResult(assignment_path=assignment_path, errors=errors)


def _validate_non_empty_string(config: dict[str, Any], field: str, errors: list[str]) -> None:
    value = config.get(field)
    if field in config and (not isinstance(value, str) or not value.strip()):
        errors.append(f"{field} must be a non-empty string.")


def _validate_positive_number(config: dict[str, Any], field: str, errors: list[str]) -> None:
    value = config.get(field)
    if field in config and (isinstance(value, bool) or not isinstance(value, int | float) or value <= 0):
        errors.append(f"{field} must be a positive number.")


def _validate_submission(submission: Any, errors: list[str]) -> None:
    if submission is None:
        return
    if not isinstance(submission, dict):
        errors.append("submission must be a mapping.")
        return

    required_files = submission.get("required_files")
    if "required_files" not in submission:
        errors.append("Missing required field: submission.required_files")
        return
    if not isinstance(required_files, list) or not required_files:
        errors.append("submission.required_files must be a non-empty list.")
        return

    for index, filename in enumerate(required_files):
        if not isinstance(filename, str) or not filename.strip():
            errors.append(f"submission.required_files[{index}] must be a non-empty string.")


def _validate_checks(checks: Any, errors: list[str]) -> None:
    if checks is None:
        return
    if not isinstance(checks, list) or not checks:
        errors.append("checks must be a non-empty list.")
        return

    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            errors.append(f"checks[{index}] must be a mapping.")
            continue
        if not check.get("name"):
            errors.append(f"checks[{index}].name must be a non-empty string.")
        if not check.get("type"):
            errors.append(f"checks[{index}].type must be a non-empty string.")
        points = check.get("points")
        if points is not None and (isinstance(points, bool) or not isinstance(points, int | float) or points < 0):
            errors.append(f"checks[{index}].points must be a non-negative number.")
