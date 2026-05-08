from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from hamrforge.assignment import load_assignment, validate_assignment
from hamrforge.grading import GradeError, grade_submission
from hamrforge.models import CheckResult, GradeResult
from hamrforge.runner import CompileRequest, RunRequest, SandboxRunner


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
    runner: str = "assignment default"


@dataclass(frozen=True)
class GradingJob:
    job_id: str
    path: Path
    status: str
    owner_key: str
    assignment_slug: str
    runner: str
    created_at: str
    updated_at: str
    attempt_id: str | None = None
    score: float | None = None
    max_score: float | None = None
    report_json_path: Path | None = None
    report_md_path: Path | None = None
    error: str = ""


@dataclass(frozen=True)
class ProgramRun:
    runner: str
    compile_returncode: int
    compile_stdout: str
    compile_stderr: str
    run_returncode: int | None = None
    program_stdout: str = ""
    program_stderr: str = ""
    compile_timed_out: bool = False
    run_timed_out: bool = False
    output_limited: bool = False
    compiler_missing: bool = False

    @property
    def compiled(self) -> bool:
        return self.compile_returncode == 0 and not self.compile_timed_out and not self.compiler_missing

    @property
    def succeeded(self) -> bool:
        return self.compiled and self.run_returncode == 0 and not self.run_timed_out


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
    _ensure_student_file(workspace, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _touch_metadata(workspace)


def create_workspace_file(workspace: Workspace, relative_path: str, content: str = "") -> None:
    path = _resolve_inside(workspace.path, relative_path)
    _ensure_student_file(workspace, path)
    if path.exists():
        raise WorkspaceError(f"workspace file already exists: {relative_path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _touch_metadata(workspace)


def rename_workspace_file(workspace: Workspace, old_relative_path: str, new_relative_path: str) -> None:
    old_path = _resolve_inside(workspace.path, old_relative_path)
    new_path = _resolve_inside(workspace.path, new_relative_path)
    _ensure_student_file(workspace, old_path)
    _ensure_student_file(workspace, new_path)
    if not old_path.exists() or not old_path.is_file():
        raise WorkspaceError(f"workspace file does not exist: {old_relative_path}")
    if new_path.exists():
        raise WorkspaceError(f"workspace file already exists: {new_relative_path}")
    new_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.rename(new_path)
    _touch_metadata(workspace)


def delete_workspace_file(workspace: Workspace, relative_path: str) -> None:
    path = _resolve_inside(workspace.path, relative_path)
    _ensure_student_file(workspace, path)
    if not path.exists() or not path.is_file():
        raise WorkspaceError(f"workspace file does not exist: {relative_path}")
    path.unlink()
    _touch_metadata(workspace)


def reset_demo_workspace(workspace: Workspace, confirmation: str) -> Workspace:
    expected = f"reset {workspace.assignment_slug}"
    if confirmation.strip() != expected:
        raise WorkspaceError(f'type "{expected}" to reset this demo workspace')
    if not workspace.owner_key.startswith("demo"):
        raise WorkspaceError("workspace reset is only available for demo owner keys")
    return create_workspace(workspace.assignment_path, workspace.owner_key, overwrite=True)


def grade_workspace(workspace: Workspace, runner: SandboxRunner | None = None, runner_name: str = "assignment default") -> Attempt:
    attempt_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    attempts_dir = workspace.path / ".hamrforge" / "attempts"
    attempt_dir = attempts_dir / attempt_id
    report_dir = attempt_dir / "reports"
    snapshot_dir = attempt_dir / "snapshot"
    attempt_dir.mkdir(parents=True, exist_ok=False)

    _copy_snapshot(workspace.path, snapshot_dir)
    try:
        result = grade_submission(workspace.assignment_path, snapshot_dir, report_dir, runner=runner)
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
        "runner": runner_name,
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
        runner=runner_name,
    )


def grade_workspace_job(
    workspace: Workspace,
    runner: SandboxRunner | None = None,
    runner_name: str = "assignment default",
) -> GradingJob:
    job = create_grading_job(workspace, runner_name=runner_name)
    _write_job(job, status="running")
    try:
        attempt = grade_workspace(workspace, runner=runner, runner_name=runner_name)
    except Exception as exc:
        _write_job(job, status="failed", error=str(exc))
        raise
    _write_job(
        job,
        status="completed",
        attempt_id=attempt.attempt_id,
        score=attempt.result.score,
        max_score=attempt.result.max_score,
        report_json_path=attempt.report_json_path,
        report_md_path=attempt.report_md_path,
    )
    loaded = _job_from_dir(job.path)
    if loaded is None:
        raise WorkspaceError(f"grading job record could not be loaded: {job.job_id}")
    return loaded


def create_grading_job(workspace: Workspace, runner_name: str = "assignment default") -> GradingJob:
    job_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    jobs_dir = workspace.path / ".hamrforge" / "jobs"
    job_dir = jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=False)
    now = _now()
    job = GradingJob(
        job_id=job_id,
        path=job_dir,
        status="queued",
        owner_key=workspace.owner_key,
        assignment_slug=workspace.assignment_slug,
        runner=runner_name,
        created_at=now,
        updated_at=now,
    )
    _write_job(job, status="queued")
    return job


def latest_grading_job(workspace: Workspace) -> GradingJob | None:
    jobs = list_grading_jobs(workspace)
    return jobs[0] if jobs else None


def load_grading_job(workspace: Workspace, job_id: str) -> GradingJob:
    job_dir = _resolve_inside(workspace.path / ".hamrforge" / "jobs", _safe_segment(job_id))
    job = _job_from_dir(job_dir)
    if job is None:
        raise WorkspaceError(f"grading job does not exist: {job_id}")
    return job


def list_grading_jobs(workspace: Workspace) -> list[GradingJob]:
    jobs_dir = workspace.path / ".hamrforge" / "jobs"
    if not jobs_dir.exists():
        return []
    return [
        job
        for job_dir in sorted((path for path in jobs_dir.iterdir() if path.is_dir()), reverse=True)
        if (job := _job_from_dir(job_dir)) is not None
    ]


def run_workspace_program(
    workspace: Workspace,
    runner: SandboxRunner,
    runner_name: str = "assignment default",
    stdin: str = "",
) -> ProgramRun:
    assignment = load_assignment(workspace.assignment_path)
    if str(assignment["language"]).strip().lower() not in {"cpp", "c++"}:
        raise WorkspaceError(f"workspace run supports cpp assignments only in Rev 1: {assignment['language']}")

    with TemporaryDirectory(prefix="hamrforge-run-") as tmp:
        snapshot_dir = Path(tmp) / "snapshot"
        _copy_snapshot(workspace.path, snapshot_dir)
        cpp_files = _student_program_cpp_files(snapshot_dir)
        if not cpp_files:
            return ProgramRun(
                runner=runner_name,
                compile_returncode=1,
                compile_stdout="",
                compile_stderr="No .cpp files were found to compile.",
            )

        output_path = snapshot_dir / "hamrforge_program"
        compile_result = runner.compile_cpp(
            CompileRequest(
                compiler=str(assignment["compiler"]),
                standard=str(assignment["standard"]),
                source_files=cpp_files,
                output_path=output_path,
            ),
            workspace=snapshot_dir,
        )
        if not compile_result.succeeded:
            return ProgramRun(
                runner=runner_name,
                compile_returncode=compile_result.returncode,
                compile_stdout=compile_result.stdout,
                compile_stderr=compile_result.stderr,
                compile_timed_out=compile_result.timed_out,
                output_limited=compile_result.output_limited,
                compiler_missing=compile_result.compiler_missing,
            )

        run_result = runner.run_executable(
            RunRequest(executable_path=output_path, stdin=stdin),
            workspace=snapshot_dir,
        )
        return ProgramRun(
            runner=runner_name,
            compile_returncode=compile_result.returncode,
            compile_stdout=compile_result.stdout,
            compile_stderr=compile_result.stderr,
            run_returncode=run_result.returncode,
            program_stdout=run_result.stdout,
            program_stderr=run_result.stderr,
            compile_timed_out=compile_result.timed_out,
            run_timed_out=run_result.timed_out,
            output_limited=compile_result.output_limited or run_result.output_limited,
            compiler_missing=compile_result.compiler_missing,
        )


def latest_attempt(workspace: Workspace) -> Attempt | None:
    attempts = list_attempts(workspace)
    return attempts[0] if attempts else None


def list_attempts(workspace: Workspace) -> list[Attempt]:
    attempts_dir = workspace.path / ".hamrforge" / "attempts"
    if not attempts_dir.exists():
        return []
    attempts = [
        attempt
        for attempt_dir in sorted((path for path in attempts_dir.iterdir() if path.is_dir()), reverse=True)
        if (attempt := _attempt_from_dir(attempt_dir)) is not None
    ]
    return attempts


def _attempt_from_dir(attempt_dir: Path) -> Attempt | None:
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
        runner=str(metadata.get("runner", "assignment default")),
    )


def _job_from_dir(job_dir: Path) -> GradingJob | None:
    metadata_path = job_dir / "job.json"
    if not metadata_path.exists():
        return None
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return GradingJob(
        job_id=str(metadata["job_id"]),
        path=job_dir,
        status=str(metadata["status"]),
        owner_key=str(metadata["owner_key"]),
        assignment_slug=str(metadata["assignment_slug"]),
        runner=str(metadata["runner"]),
        created_at=str(metadata["created_at"]),
        updated_at=str(metadata["updated_at"]),
        attempt_id=metadata.get("attempt_id"),
        score=_optional_float(metadata.get("score")),
        max_score=_optional_float(metadata.get("max_score")),
        report_json_path=Path(metadata["report_json_path"]) if metadata.get("report_json_path") else None,
        report_md_path=Path(metadata["report_md_path"]) if metadata.get("report_md_path") else None,
        error=str(metadata.get("error", "")),
    )


def _write_job(
    job: GradingJob,
    status: str,
    attempt_id: str | None = None,
    score: float | None = None,
    max_score: float | None = None,
    report_json_path: Path | None = None,
    report_md_path: Path | None = None,
    error: str = "",
) -> None:
    existing = _job_from_dir(job.path)
    metadata = {
        "job_id": job.job_id,
        "owner_key": job.owner_key,
        "assignment_slug": job.assignment_slug,
        "runner": job.runner,
        "status": status,
        "created_at": existing.created_at if existing else job.created_at,
        "updated_at": _now(),
        "attempt_id": attempt_id if attempt_id is not None else (existing.attempt_id if existing else None),
        "score": score if score is not None else (existing.score if existing else None),
        "max_score": max_score if max_score is not None else (existing.max_score if existing else None),
        "report_json_path": str(report_json_path)
        if report_json_path is not None
        else (str(existing.report_json_path) if existing and existing.report_json_path else None),
        "report_md_path": str(report_md_path)
        if report_md_path is not None
        else (str(existing.report_md_path) if existing and existing.report_md_path else None),
        "error": error if error else (existing.error if existing else ""),
    }
    (job.path / "job.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def _copy_snapshot(workspace_root: Path, snapshot_dir: Path) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        return {".hamrforge"} & set(names)

    shutil.copytree(workspace_root, snapshot_dir, ignore=ignore)


def _student_program_cpp_files(workspace_root: Path) -> list[Path]:
    return sorted(path for path in workspace_root.rglob("*.cpp") if path.is_file() and not path.name.startswith("hamrforge_"))


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


def _ensure_student_file(workspace: Workspace, path: Path) -> None:
    relative = path.relative_to(workspace.path)
    if ".hamrforge" in relative.parts:
        raise WorkspaceError("cannot modify HamrForge metadata files")
    if not path.name:
        raise WorkspaceError("workspace file path cannot be empty")
    if not _is_editable(path):
        raise WorkspaceError(f"workspace file is not an editable text type: {relative.as_posix()}")


def _safe_segment(value: str) -> str:
    safe = "".join(character if character.isalnum() or character in {"-", "_"} else "-" for character in value)
    safe = safe.strip("-_")
    if not safe:
        raise WorkspaceError("workspace path segment cannot be empty")
    return safe


def _is_editable(path: Path) -> bool:
    return path.suffix.lower() in EDITABLE_EXTENSIONS


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _now() -> str:
    return datetime.now(UTC).isoformat()
