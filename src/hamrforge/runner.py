from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class CompileRequest:
    compiler: str
    standard: str
    source_files: list[Path]
    output_path: Path
    timeout_seconds: int = 20


@dataclass(frozen=True)
class CompileResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    compiler_missing: bool = False

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


@dataclass(frozen=True)
class RunResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

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
    """Runs compile commands directly on the host. Unsafe for untrusted submissions."""

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
            return CompileResult(
                returncode=124,
                stdout=_normalize_output(exc.stdout),
                stderr=_normalize_output(exc.stderr),
                timed_out=True,
            )

        return CompileResult(returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)

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
            return RunResult(
                returncode=124,
                stdout=_normalize_output(exc.stdout),
                stderr=_normalize_output(exc.stderr),
                timed_out=True,
            )

        return RunResult(returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)


class DockerCliRunner:
    """Placeholder for a future Docker-backed sandbox runner."""

    def compile_cpp(self, request: CompileRequest, workspace: Path) -> CompileResult:
        raise NotImplementedError("DockerCliRunner is not implemented yet.")

    def run_executable(self, request: RunRequest, workspace: Path) -> RunResult:
        raise NotImplementedError("DockerCliRunner is not implemented yet.")


def _normalize_output(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode(errors="replace")
    return output
