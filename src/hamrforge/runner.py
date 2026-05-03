from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol


@dataclass(frozen=True)
class CompileRequest:
    compiler: str
    standard: str
    source_files: list[Path]
    output_path: Path
    timeout_seconds: int = 20
    max_output_bytes: int = 65536


@dataclass(frozen=True)
class CompileResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    compiler_missing: bool = False
    output_limited: bool = False

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0 and not self.timed_out and not self.compiler_missing

    @property
    def combined_output(self) -> str:
        pieces = [self.stdout.strip(), self.stderr.strip()]
        return "\n".join(piece for piece in pieces if piece)


@dataclass(frozen=True)
class RunRequest:
    executable_path: Path
    stdin: str = ""
    timeout_seconds: int = 5
    max_output_bytes: int = 65536


@dataclass(frozen=True)
class RunResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    output_limited: bool = False

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    @property
    def combined_output(self) -> str:
        pieces = [self.stdout.strip(), self.stderr.strip()]
        return "\n".join(piece for piece in pieces if piece)


class SandboxRunner(Protocol):
    def compile_cpp(self, request: CompileRequest, workspace: Path) -> CompileResult:
        """Compile C++ source files inside the runner's execution environment."""

    def run_executable(self, request: RunRequest, workspace: Path) -> RunResult:
        """Run an executable inside the runner's execution environment."""


class LocalUnsafeRunner:
    """Development-only runner that executes student code directly on the host.

    This runner is intentionally unsafe. It is useful for local MVP development,
    but real student submissions must eventually run through an isolated OCI
    sandbox such as Docker or Podman with resource and network limits.
    """

    def compile_cpp(self, request: CompileRequest, workspace: Path) -> CompileResult:
        command = [
            request.compiler,
            f"-std={request.standard}",
            *[str(path) for path in request.source_files],
            "-o",
            str(request.output_path),
        ]

        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
                check=False,
            )
        except FileNotFoundError:
            return CompileResult(returncode=127, stdout="", stderr="", compiler_missing=True)
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, output_limited = _limit_outputs(
                _normalize_output(exc.stdout),
                _normalize_output(exc.stderr),
                request.max_output_bytes,
            )
            return CompileResult(
                returncode=124,
                stdout=stdout,
                stderr=_append_message(
                    stderr,
                    f"Local unsafe compile command timed out after {request.timeout_seconds} seconds.",
                ),
                timed_out=True,
                output_limited=output_limited,
            )

        stdout, stderr, output_limited = _limit_outputs(completed.stdout, completed.stderr, request.max_output_bytes)
        return CompileResult(
            returncode=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            output_limited=output_limited,
        )

    def run_executable(self, request: RunRequest, workspace: Path) -> RunResult:
        try:
            completed = subprocess.run(
                [str(request.executable_path)],
                cwd=workspace,
                input=request.stdin,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, output_limited = _limit_outputs(
                _normalize_output(exc.stdout),
                _normalize_output(exc.stderr),
                request.max_output_bytes,
            )
            return RunResult(
                returncode=124,
                stdout=stdout,
                stderr=_append_message(
                    stderr,
                    f"Local unsafe run command timed out after {request.timeout_seconds} seconds.",
                ),
                timed_out=True,
                output_limited=output_limited,
            )

        stdout, stderr, output_limited = _limit_outputs(completed.stdout, completed.stderr, request.max_output_bytes)
        return RunResult(
            returncode=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            output_limited=output_limited,
        )


class DockerCliRunner:
    """Placeholder for a future Docker-backed sandbox runner."""

    def compile_cpp(self, request: CompileRequest, workspace: Path) -> CompileResult:
        raise NotImplementedError("DockerCliRunner is not implemented yet.")

    def run_executable(self, request: RunRequest, workspace: Path) -> RunResult:
        raise NotImplementedError("DockerCliRunner is not implemented yet.")


class PodmanCliRunner:
    """Runs compile and execution commands inside a Podman container."""

    def __init__(
        self,
        image: str = "hamrforge-cpp-runner",
        run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self.image = image
        self._run_command = run_command

    def compile_cpp(self, request: CompileRequest, workspace: Path) -> CompileResult:
        command = [
            request.compiler,
            f"-std={request.standard}",
            *[self._container_path(path, workspace) for path in request.source_files],
            "-o",
            self._container_path(request.output_path, workspace),
        ]
        result = self._run_in_container(
            command,
            workspace,
            stdin="",
            timeout_seconds=request.timeout_seconds,
            max_output_bytes=request.max_output_bytes,
        )
        return CompileResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            timed_out=result.timed_out,
            output_limited=result.output_limited,
        )

    def run_executable(self, request: RunRequest, workspace: Path) -> RunResult:
        result = self._run_in_container(
            [self._container_path(request.executable_path, workspace)],
            workspace,
            stdin=request.stdin,
            timeout_seconds=request.timeout_seconds,
            max_output_bytes=request.max_output_bytes,
        )
        return RunResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            timed_out=result.timed_out,
            output_limited=result.output_limited,
        )

    def _run_in_container(
        self,
        command: list[str],
        workspace: Path,
        stdin: str,
        timeout_seconds: int,
        max_output_bytes: int,
    ) -> RunResult:
        podman_command = self._podman_command(workspace, command)
        try:
            completed = self._run_command(
                podman_command,
                cwd=workspace,
                input=stdin,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except FileNotFoundError:
            return RunResult(
                returncode=127,
                stdout="",
                stderr="Podman CLI not found. Install podman or use runner: local_unsafe for development.",
            )
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, output_limited = _limit_outputs(
                _normalize_output(exc.stdout),
                _normalize_output(exc.stderr),
                max_output_bytes,
            )
            return RunResult(
                returncode=124,
                stdout=stdout,
                stderr=_append_message(
                    stderr,
                    f"Podman container timed out after {timeout_seconds} seconds.",
                ),
                timed_out=True,
                output_limited=output_limited,
            )

        stdout, stderr, output_limited = _limit_outputs(completed.stdout, completed.stderr, max_output_bytes)
        if completed.returncode != 0:
            stderr = _append_message(stderr, f"Podman container exited with status {completed.returncode}.")
        return RunResult(
            returncode=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            output_limited=output_limited,
        )

    def _podman_command(self, workspace: Path, command: list[str]) -> list[str]:
        return [
            "podman",
            "run",
            "--rm",
            "--network",
            "none",
            "--memory",
            "256m",
            "--cpus",
            "1",
            "--pids-limit",
            "64",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,size=64m",
            "--security-opt",
            "no-new-privileges",
            "--cap-drop",
            "ALL",
            "--userns",
            "keep-id",
            "--user",
            "1000:1000",
            "--volume",
            f"{workspace.resolve()}:/workspace:rw",
            "--workdir",
            "/workspace",
            self.image,
            *command,
        ]

    def _container_path(self, path: Path, workspace: Path) -> str:
        resolved_workspace = workspace.resolve()
        resolved_path = path.resolve()
        if resolved_path == resolved_workspace:
            return "/workspace"
        if resolved_workspace not in resolved_path.parents:
            raise ValueError(f"path is outside the mounted workspace: {path}")
        return "/workspace/" + resolved_path.relative_to(resolved_workspace).as_posix()


def _normalize_output(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode(errors="replace")
    return output


def _append_message(output: str, message: str) -> str:
    if output.strip():
        return output.rstrip() + "\n" + message
    return message


def _limit_outputs(stdout: str, stderr: str, max_output_bytes: int) -> tuple[str, str, bool]:
    limited_stdout, stdout_limited = _limit_output(stdout, max_output_bytes)
    limited_stderr, stderr_limited = _limit_output(stderr, max_output_bytes)
    return limited_stdout, limited_stderr, stdout_limited or stderr_limited


def _limit_output(output: str, max_output_bytes: int) -> tuple[str, bool]:
    encoded = output.encode(errors="replace")
    if len(encoded) <= max_output_bytes:
        return output, False
    truncated = encoded[:max_output_bytes].decode(errors="replace")
    return (
        truncated
        + f"\n[HamrForge output truncated after {max_output_bytes} bytes. Additional output was discarded.]",
        True,
    )


def runner_name_from_assignment(assignment: dict[str, Any]) -> str:
    configured = assignment.get("runner", "local_unsafe")
    if isinstance(configured, str):
        return configured
    if isinstance(configured, dict):
        return str(configured.get("type", "local_unsafe"))
    return "local_unsafe"


def runner_image_from_assignment(assignment: dict[str, Any]) -> str | None:
    configured = assignment.get("runner")
    if isinstance(configured, dict) and configured.get("image") is not None:
        return str(configured["image"])
    return None


def create_runner(name: str, image: str | None = None) -> SandboxRunner:
    normalized = name.strip().lower().replace("-", "_")
    if normalized == "local_unsafe":
        return LocalUnsafeRunner()
    if normalized == "podman":
        return PodmanCliRunner(image=image or "hamrforge-cpp-runner")
    raise ValueError(f"Unsupported sandbox runner: {name}. Rev 1 supports: local_unsafe, podman.")
