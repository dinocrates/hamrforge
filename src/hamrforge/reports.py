from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol


class ReportableCheck(Protocol):
    name: str
    type: str
    score: float
    max_score: float
    passed: bool
    feedback: str
    detail: str


def write_reports(
    out_dir: Path,
    assignment_title: str,
    score: float,
    max_score: float,
    checks: list[ReportableCheck],
    flags: list[str],
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    report_json_path = out_dir / "report.json"
    report_md_path = out_dir / "report.md"

    report = {
        "assignment": assignment_title,
        "score": score,
        "max_score": max_score,
        "checks": [
            {
                "name": check.name,
                "type": check.type,
                "score": check.score,
                "max_score": check.max_score,
                "passed": check.passed,
                "feedback": check.feedback,
                "detail": check.detail,
            }
            for check in checks
        ],
        "flags": flags,
    }
    report_json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report_md_path.write_text(_render_markdown(assignment_title, score, max_score, checks, flags), encoding="utf-8")
    return report_json_path, report_md_path


def _render_markdown(
    assignment_title: str,
    score: float,
    max_score: float,
    checks: list[ReportableCheck],
    flags: list[str],
) -> str:
    lines = [
        "# HamrForge Feedback Report",
        "",
        f"Assignment: {assignment_title}",
        f"Score: {score:g} / {max_score:g}",
        "",
        "## Results",
        "",
    ]
    for check in checks:
        lines.extend(
            [
                f"### {check.name} - {check.score:g} / {check.max_score:g}",
                "",
                check.feedback,
                "",
            ]
        )
        if check.detail:
            lines.extend(["```text", check.detail, "```", ""])
    if flags:
        lines.extend(["## Flags", ""])
        lines.extend(f"- {flag}" for flag in flags)
        lines.append("")
    return "\n".join(lines)
