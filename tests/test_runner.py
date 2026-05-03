from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from hamrforge.runner import (
    CompileRequest,
    LocalUnsafeRunner,
    PodmanCliRunner,
    RunRequest,
    create_runner,
    runner_image_from_assignment,
    runner_name_from_assignment,
)


def test_runner_name_defaults_to_local_unsafe() -> None:
    assert runner_name_from_assignment({}) == "local_unsafe"


def test_runner_name_can_be_configured_as_string() -> None:
    assert runner_name_from_assignment({"runner": "local_unsafe"}) == "local_unsafe"


def test_runner_name_can_be_configured_as_mapping() -> None:
    assert runner_name_from_assignment({"runner": {"type": "local_unsafe"}}) == "local_unsafe"


def test_runner_image_can_be_configured_as_mapping() -> None:
    assert runner_image_from_assignment({"runner": {"type": "podman", "image": "custom-cpp"}}) == "custom-cpp"


def test_create_runner_returns_local_unsafe_runner() -> None:
    assert isinstance(create_runner("local_unsafe"), LocalUnsafeRunner)


def test_create_runner_returns_podman_runner() -> None:
    runner = create_runner("podman", image="custom-cpp")

    assert isinstance(runner, PodmanCliRunner)
    assert runner.image == "custom-cpp"


def test_create_runner_rejects_unsupported_runner() -> None:
    with pytest.raises(ValueError, match="Unsupported sandbox runner: docker"):
        create_runner("docker")


def test_podman_runner_constructs_compile_command(tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    source = tmp_path / "main.cpp"
    output = tmp_path / "program"
    source.write_text("int main() { return 0; }\n", encoding="utf-8")

    result = PodmanCliRunner(image="custom-cpp", run_command=fake_run).compile_cpp(
        CompileRequest(compiler="g++", standard="c++17", source_files=[source], output_path=output),
        workspace=tmp_path,
    )

    command = captured["command"]
    assert result.succeeded
    assert command[:4] == ["podman", "run", "--rm", "--network"]
    assert "none" in command
    assert "--memory" in command
    assert "256m" in command
    assert "--cpus" in command
    assert "1" in command
    assert "--pids-limit" in command
    assert "64" in command
    assert "--read-only" in command
    assert "--security-opt" in command
    assert "no-new-privileges" in command
    assert "--cap-drop" in command
    assert "ALL" in command
    assert "--userns" in command
    assert "keep-id" in command
    assert "--user" in command
    assert "1000:1000" in command
    assert "--volume" in command
    assert f"{tmp_path.resolve()}:/workspace:rw" in command
    assert "custom-cpp" in command
    assert command[-5:] == ["g++", "-std=c++17", "/workspace/main.cpp", "-o", "/workspace/program"]
    assert captured["kwargs"]["timeout"] == 20


def test_podman_runner_constructs_run_command_with_stdin(tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")

    program = tmp_path / "program"
    program.write_text("", encoding="utf-8")

    result = PodmanCliRunner(run_command=fake_run).run_executable(
        RunRequest(executable_path=program, stdin="4\n"),
        workspace=tmp_path,
    )

    assert result.succeeded
    assert captured["command"][-2:] == ["hamrforge-cpp-runner", "/workspace/program"]
    assert captured["kwargs"]["input"] == "4\n"
    assert captured["kwargs"]["timeout"] == 5


def test_podman_runner_reports_missing_podman_cli(tmp_path: Path) -> None:
    def fake_run(command, **kwargs):
        raise FileNotFoundError("podman")

    result = PodmanCliRunner(run_command=fake_run).compile_cpp(
        CompileRequest(
            compiler="g++",
            standard="c++17",
            source_files=[tmp_path / "main.cpp"],
            output_path=tmp_path / "program",
        ),
        workspace=tmp_path,
    )

    assert not result.succeeded
    assert result.returncode == 127
    assert "Podman CLI not found" in result.stderr


def test_podman_runner_reports_nonzero_container_exit(tmp_path: Path) -> None:
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 125, stdout="", stderr="image not known\n")

    result = PodmanCliRunner(run_command=fake_run).run_executable(
        RunRequest(executable_path=tmp_path / "program"),
        workspace=tmp_path,
    )

    assert not result.succeeded
    assert result.returncode == 125
    assert "image not known" in result.stderr
    assert "Podman container exited with status 125." in result.stderr


def test_podman_runner_reports_container_timeout(tmp_path: Path) -> None:
    def fake_run(command, **kwargs):
        exc = subprocess.TimeoutExpired(command, timeout=2, output="partial\n", stderr="")
        raise exc

    result = PodmanCliRunner(run_command=fake_run).run_executable(
        RunRequest(executable_path=tmp_path / "program", timeout_seconds=2),
        workspace=tmp_path,
    )

    assert not result.succeeded
    assert result.returncode == 124
    assert result.timed_out
    assert result.stdout == "partial\n"
    assert "Podman container timed out after 2 seconds." in result.stderr


def test_podman_runner_limits_captured_output(tmp_path: Path) -> None:
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="abcdefghijk", stderr="")

    result = PodmanCliRunner(run_command=fake_run).run_executable(
        RunRequest(executable_path=tmp_path / "program", max_output_bytes=5),
        workspace=tmp_path,
    )

    assert result.succeeded
    assert result.output_limited
    assert result.stdout.startswith("abcde")
    assert "HamrForge output truncated after 5 bytes" in result.stdout


def test_podman_runner_limits_timeout_output(tmp_path: Path) -> None:
    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, timeout=2, output="abcdefghijk", stderr="")

    result = PodmanCliRunner(run_command=fake_run).run_executable(
        RunRequest(executable_path=tmp_path / "program", timeout_seconds=2, max_output_bytes=5),
        workspace=tmp_path,
    )

    assert not result.succeeded
    assert result.timed_out
    assert result.output_limited
    assert result.stdout.startswith("abcde")
    assert "HamrForge output truncated after 5 bytes" in result.stdout
    assert "Podman container timed out after 2 seconds." in result.stderr


def test_local_unsafe_runner_compiles_cpp_file(tmp_path: Path) -> None:
    source = tmp_path / "main.cpp"
    source.write_text("int main() { return 0; }\n", encoding="utf-8")

    result = LocalUnsafeRunner().compile_cpp(
        CompileRequest(
            compiler="g++",
            standard="c++17",
            source_files=[source],
            output_path=tmp_path / "program",
        ),
        workspace=tmp_path,
    )

    assert result.succeeded
    assert result.combined_output == ""


def test_local_unsafe_runner_reports_compile_failure(tmp_path: Path) -> None:
    source = tmp_path / "main.cpp"
    source.write_text("int main() { return }\n", encoding="utf-8")

    result = LocalUnsafeRunner().compile_cpp(
        CompileRequest(
            compiler="g++",
            standard="c++17",
            source_files=[source],
            output_path=tmp_path / "program",
        ),
        workspace=tmp_path,
    )

    assert not result.succeeded
    assert result.returncode != 0
    assert result.combined_output


def test_local_unsafe_runner_runs_executable(tmp_path: Path) -> None:
    source = tmp_path / "main.cpp"
    program = tmp_path / "program"
    source.write_text('#include <iostream>\nint main() { std::cout << "ok\\n"; return 0; }\n', encoding="utf-8")
    compile_result = LocalUnsafeRunner().compile_cpp(
        CompileRequest(
            compiler="g++",
            standard="c++17",
            source_files=[source],
            output_path=program,
        ),
        workspace=tmp_path,
    )
    assert compile_result.succeeded

    run_result = LocalUnsafeRunner().run_executable(RunRequest(executable_path=program), workspace=tmp_path)

    assert run_result.succeeded
    assert run_result.stdout == "ok\n"


def test_local_unsafe_runner_passes_stdin_to_executable(tmp_path: Path) -> None:
    source = tmp_path / "main.cpp"
    program = tmp_path / "program"
    source.write_text(
        '#include <iostream>\nint main() { int n = 0; std::cin >> n; std::cout << n + 1 << "\\n"; }\n',
        encoding="utf-8",
    )
    compile_result = LocalUnsafeRunner().compile_cpp(
        CompileRequest(
            compiler="g++",
            standard="c++17",
            source_files=[source],
            output_path=program,
        ),
        workspace=tmp_path,
    )
    assert compile_result.succeeded

    run_result = LocalUnsafeRunner().run_executable(RunRequest(executable_path=program, stdin="4\n"), workspace=tmp_path)

    assert run_result.succeeded
    assert run_result.stdout == "5\n"
