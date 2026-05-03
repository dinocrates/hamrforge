from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
