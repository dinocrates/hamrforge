from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hamrforge.assignment import load_assignment, validate_assignment
from hamrforge.grading import GradeError, grade_submission
from hamrforge.models import CheckResult, GradeResult


class WorkspaceError(Exception):
    """Raised when a workspace operation cannot be completed."""


DATA_DIR = Path("data")
WORKSPACES_DIR = DATA_DIR / "workspaces"

EDITABLE_EXTENSIONS = {".cpp", ".h", ".hpp", ".txt", ".md", ".yml", ".yaml"}


@dataclass(frozen=True)
class Workspace:
    owner_key: str
    assignment_slug: str
    assignment_path: Path
    path: Path
    metadata_path: Path


@dataclass(frozen=True)
class WorkspaceFile:
    path: str
    size: int
    editable: bool


@dataclass(frozen=True)
class Attempt:
    attempt_id: str
    path: Path
    report_json_path: Path
    report_md_path: Path
    snapshot_path: Path
    result: GradeResult


def create_workspace(assignment_dir: Path, owner_key: str, overwrite: bool = False) -> Workspace:
    assignment_dir = assignment_dir.resolve()
    validation = validate_assignment(assignment_dir)
    if not validation.is_valid:
        raise WorkspaceError("assignment is invalid: " + "; ".join(validation.errors))

    assignment = load_assignment(assignment_dir)
    slug = str(assignment["slug"])
    workspace_root = WORKSPACES_DIR / _safe_segment(owner_key) / _safe_segment(slug)
    starter_dir = assignment_dir / "starter"
    if not starter_dir.exists() or not starter_dir.is_dir():
        raise WorkspaceError(f"assignment starter folder does not exist: {starter_dir}")

    if workspace_root.exists() and overwrite:
        shutil.rmtree(workspace_root)
    workspace_root.mkdir(parents=True, exist_ok=True)

    for source in starter_dir.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(starter_dir)
        target = _resolve_inside(workspace_root, relative.as_posix())
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or overwrite:
            shutil.copy2(source, target)

    now = _now()
    metadata = {
        "owner_key": owner_key,
        "assignment_slug": slug,
        "assignment_path": str(assignment_dir),
        "created_at": now,
        "updated_at": now,
    }
    hamrforge_dir = workspace_root / ".hamrforge"
    hamrforge_dir.mkdir(exist_ok=True)
    metadata_path = hamrforge_dir / "workspace.json"
    if metadata_path.exists() and not overwrite:
        existing = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["created_at"] = existing.get("created_at", now)
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return load_workspace(owner_key, slug)


def load_workspace(owner_key: str, assignment_slug: str) -> Workspace:
    workspace_root = (WORKSPACES_DIR / _safe_segment(owner_key) / _safe_segment(assignment_slug)).resolve()
    metadata_path = workspace_root / ".hamrforge" / "workspace.json"
    if not metadata_path.exists():
        raise WorkspaceError(f"workspace does not exist: {workspace_root}")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return Workspace(
        owner_key=str(metadata["owner_key"]),
        assignment_slug=str(metadata["assignment_slug"]),
        assignment_path=Path(metadata["assignment_path"]),
        path=workspace_root,
        metadata_path=metadata_path,
    )


def list_workspace_files(workspace: Workspace) -> list[WorkspaceFile]:
    files: list[WorkspaceFile] = []
    for path in sorted(workspace.path.rglob("*")):
        if not path.is_file() or ".hamrforge" in path.parts:
            continue
        relative = path.relative_to(workspace.path).as_posix()
        files.append(WorkspaceFile(path=relative, size=path.stat().st_size, editable=_is_editable(path)))
    return files


def read_workspace_file(workspace: Workspace, relative_path: str) -> str:
    path = _resolve_inside(workspace.path, relative_path)
    if not path.exists() or not path.is_file():
        raise WorkspaceError(f"workspace file does not exist: {relative_path}")
    if not _is_editable(path):
        raise WorkspaceError(f"workspace file is not editable text: {relative_path}")
    return path.read_text(encoding="utf-8")


def write_workspace_file(workspace: Workspace, relative_path: str, content: str) -> None:
    path = _resolve_inside(workspace.path, relative_path)
    if ".hamrforge" in path.relative_to(workspace.path).parts:
        raise WorkspaceError("cannot edit HamrForge metadata files")
    if not _is_editable(path):
        raise WorkspaceError(f"workspace file is not editable text: {relative_path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _touch_metadata(workspace)


def grade_workspace(workspace: Workspace) -> Attempt:
    attempt_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    attempts_dir = workspace.path / ".hamrforge" / "attempts"
    attempt_dir = attempts_dir / attempt_id
    report_dir = attempt_dir / "reports"
    snapshot_dir = attempt_dir / "snapshot"
    attempt_dir.mkdir(parents=True, exist_ok=False)

    _copy_snapshot(workspace.path, snapshot_dir)
    try:
        result = grade_submission(workspace.assignment_path, workspace.path, report_dir)
    except GradeError:
        shutil.rmtree(attempt_dir, ignore_errors=True)
        raise

    metadata = {
        "attempt_id": attempt_id,
        "owner_key": workspace.owner_key,
        "assignment_slug": workspace.assignment_slug,
        "created_at": _now(),
        "score": result.score,
        "max_score": result.max_score,
        "flags": result.flags,
        "report_json_path": str(result.report_json_path),
        "report_md_path": str(result.report_md_path),
        "snapshot_path": str(snapshot_dir),
    }
    (attempt_dir / "attempt.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return Attempt(
        attempt_id=attempt_id,
        path=attempt_dir,
        report_json_path=result.report_json_path,
        report_md_path=result.report_md_path,
        snapshot_path=snapshot_dir,
        result=result,
    )


def latest_attempt(workspace: Workspace) -> Attempt | None:
    attempts_dir = workspace.path / ".hamrforge" / "attempts"
    if not attempts_dir.exists():
        return None
    attempts = sorted(path for path in attempts_dir.iterdir() if path.is_dir())
    if not attempts:
        return None
    attempt_dir = attempts[-1]
    metadata_path = attempt_dir / "attempt.json"
    if not metadata_path.exists():
        return None
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    result = _result_from_report(Path(metadata["report_json_path"]), Path(metadata["report_md_path"]))
    return Attempt(
        attempt_id=str(metadata["attempt_id"]),
        path=attempt_dir,
        report_json_path=Path(metadata["report_json_path"]),
        report_md_path=Path(metadata["report_md_path"]),
        snapshot_path=Path(metadata["snapshot_path"]),
        result=result,
    )


def _copy_snapshot(workspace_root: Path, snapshot_dir: Path) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        return {".hamrforge"} & set(names)

    shutil.copytree(workspace_root, snapshot_dir, ignore=ignore)


def _result_from_report(report_json_path: Path, report_md_path: Path) -> GradeResult:
    report = json.loads(report_json_path.read_text(encoding="utf-8"))
    checks = [
        CheckResult(
            name=check["name"],
            type=check["type"],
            score=float(check["score"]),
            max_score=float(check["max_score"]),
            passed=bool(check["passed"]),
            feedback=check["feedback"],
            missing_files=[],
            detail=check.get("detail", ""),
        )
        for check in report["checks"]
    ]
    return GradeResult(
        assignment=report["assignment"],
        score=float(report["score"]),
        max_score=float(report["max_score"]),
        checks=checks,
        flags=list(report.get("flags", [])),
        report_json_path=report_json_path,
        report_md_path=report_md_path,
    )


def _touch_metadata(workspace: Workspace) -> None:
    metadata = json.loads(workspace.metadata_path.read_text(encoding="utf-8"))
    metadata["updated_at"] = _now()
    workspace.metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def _resolve_inside(root: Path, relative_path: str) -> Path:
    if Path(relative_path).is_absolute():
        raise WorkspaceError(f"absolute paths are not allowed: {relative_path}")
    resolved_root = root.resolve()
    resolved_path = (resolved_root / relative_path).resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise WorkspaceError(f"path escapes workspace: {relative_path}")
    return resolved_path


def _safe_segment(value: str) -> str:
    safe = "".join(character if character.isalnum() or character in {"-", "_"} else "-" for character in value)
    safe = safe.strip("-_")
    if not safe:
        raise WorkspaceError("workspace path segment cannot be empty")
    return safe


def _is_editable(path: Path) -> bool:
    return path.suffix.lower() in EDITABLE_EXTENSIONS


def _now() -> str:
    return datetime.now(UTC).isoformat()
