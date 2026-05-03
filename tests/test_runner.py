from __future__ import annotations

from pathlib import Path

from hamrforge.runner import CompileRequest, LocalUnsafeRunner, RunRequest


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
