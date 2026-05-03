from __future__ import annotations

import csv
import glob
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from hamrforge.grading import GradeError, grade_submission
from hamrforge.runner import SandboxRunner


@dataclass(frozen=True)
class BatchRow:
    filename: str
    status: str
    score: float
    max_score: float
    percent: float
    flags: list[str]
    feedback_path: str
    error: str = ""


@dataclass(frozen=True)
class BatchResult:
    graded_count: int
    failed_count: int
    grades_csv_path: Path
    summary_json_path: Path
    feedback_dir: Path
    rows: list[BatchRow]


def batch_grade(
    assignment_dir: Path,
    submission_inputs: list[str],
    out_dir: Path,
    runner: SandboxRunner | None = None,
) -> BatchResult:
    submissions = _resolve_submissions(submission_inputs)
    out_dir.mkdir(parents=True, exist_ok=True)
    feedback_dir = out_dir / "feedback"
    run_dir = out_dir / "runs"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    rows: list[BatchRow] = []
    for submission in submissions:
        row = _grade_one_for_batch(assignment_dir, submission, feedback_dir, run_dir, runner)
        rows.append(row)

    grades_csv_path = out_dir / "grades.csv"
    summary_json_path = out_dir / "summary.json"
    _write_grades_csv(grades_csv_path, rows)
    _write_summary_json(summary_json_path, rows)

    return BatchResult(
        graded_count=sum(1 for row in rows if row.status == "graded"),
        failed_count=sum(1 for row in rows if row.status == "failed"),
        grades_csv_path=grades_csv_path,
        summary_json_path=summary_json_path,
        feedback_dir=feedback_dir,
        rows=rows,
    )


def _grade_one_for_batch(
    assignment_dir: Path,
    submission: Path,
    feedback_dir: Path,
    run_dir: Path,
    runner: SandboxRunner | None,
) -> BatchRow:
    run_out_dir = run_dir / submission.stem
    feedback_path = feedback_dir / f"{submission.stem}.md"

    try:
        result = grade_submission(assignment_dir, submission, run_out_dir, runner=runner)
    except GradeError as exc:
        error = str(exc)
        feedback_path.write_text(
            "\n".join(
                [
                    "# HamrForge Feedback Report",
                    "",
                    f"Submission: {submission.name}",
                    "Status: failed",
                    "",
                    "HamrForge could not grade this submission.",
                    "",
                    error,
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return BatchRow(
            filename=submission.name,
            status="failed",
            score=0.0,
            max_score=0.0,
            percent=0.0,
            flags=["manual_review_recommended"],
            feedback_path=str(feedback_path),
            error=error,
        )

    shutil.copyfile(result.report_md_path, feedback_path)
    percent = (result.score / result.max_score * 100) if result.max_score else 0.0
    return BatchRow(
        filename=submission.name,
        status="graded",
        score=result.score,
        max_score=result.max_score,
        percent=percent,
        flags=result.flags,
        feedback_path=str(feedback_path),
    )


def _resolve_submissions(submission_inputs: list[str]) -> list[Path]:
    submissions: list[Path] = []
    seen: set[Path] = set()
    for submission_input in submission_inputs:
        matches = [Path(match) for match in glob.glob(submission_input)]
        candidates = matches or [Path(submission_input)]
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            submissions.append(candidate)
    return sorted(submissions, key=lambda path: path.name)


def _write_grades_csv(path: Path, rows: list[BatchRow]) -> None:
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=["filename", "status", "score", "max_score", "percent", "flags", "feedback_path", "error"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "filename": row.filename,
                    "status": row.status,
                    "score": f"{row.score:g}",
                    "max_score": f"{row.max_score:g}",
                    "percent": f"{row.percent:.2f}",
                    "flags": ";".join(row.flags),
                    "feedback_path": row.feedback_path,
                    "error": row.error,
                }
            )


def _write_summary_json(path: Path, rows: list[BatchRow]) -> None:
    graded = [row for row in rows if row.status == "graded"]
    failed = [row for row in rows if row.status == "failed"]
    summary = {
        "total": len(rows),
        "graded": len(graded),
        "failed": len(failed),
        "average_percent": _average(row.percent for row in graded),
        "submissions": [
            {
                "filename": row.filename,
                "status": row.status,
                "score": row.score,
                "max_score": row.max_score,
                "percent": row.percent,
                "flags": row.flags,
                "feedback_path": row.feedback_path,
                "error": row.error,
            }
            for row in rows
        ],
    }
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def _average(values: Iterable[float]) -> float:
    collected = list(values)
    if not collected:
        return 0.0
    return sum(collected) / len(collected)
