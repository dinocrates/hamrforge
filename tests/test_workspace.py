from __future__ import annotations

from pathlib import Path

import pytest

from hamrforge import workspace as workspace_module
from hamrforge.workspace import (
    WorkspaceError,
    create_workspace,
    create_workspace_file,
    delete_workspace_file,
    grade_workspace,
    list_attempts,
    list_workspace_files,
    read_workspace_file,
    rename_workspace_file,
    write_workspace_file,
)


class RecordingRunner:
    def __init__(self) -> None:
        self.compile_calls = 0
        self.run_calls = 0
        self.workspaces: list[Path] = []

    def compile_cpp(self, request, workspace: Path):
        self.compile_calls += 1
        self.workspaces.append(workspace)
        from hamrforge.runner import LocalUnsafeRunner

        return LocalUnsafeRunner().compile_cpp(request, workspace)

    def run_executable(self, request, workspace: Path):
        self.run_calls += 1
        from hamrforge.runner import LocalUnsafeRunner

        return LocalUnsafeRunner().run_executable(request, workspace)


@pytest.fixture(autouse=True)
def isolated_workspace_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(workspace_module, "WORKSPACES_DIR", tmp_path / "workspaces")


def test_create_workspace_copies_starter_files() -> None:
    workspace = create_workspace(Path("assignments/byte-class"), "demo-student")

    files = {file.path for file in list_workspace_files(workspace)}

    assert workspace.path.exists()
    assert workspace.metadata_path.exists()
    assert {"main.cpp", "Byte.h", "Byte.cpp"} <= files


def test_workspace_read_write_rejects_path_traversal() -> None:
    workspace = create_workspace(Path("assignments/byte-class"), "demo-student")

    write_workspace_file(workspace, "main.cpp", "// edited\n")

    assert read_workspace_file(workspace, "main.cpp") == "// edited\n"
    with pytest.raises(WorkspaceError, match="escapes workspace"):
        read_workspace_file(workspace, "../assignment.yml")


def test_workspace_write_works_with_relative_workspace_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    relative_root = Path("data") / "test-relative-workspaces"
    monkeypatch.setattr(workspace_module, "WORKSPACES_DIR", relative_root)
    workspace = create_workspace(Path("assignments/byte-class"), "relative-student", overwrite=True)

    write_workspace_file(workspace, "Byte.cpp", "// relative root edit\n")

    assert read_workspace_file(workspace, "Byte.cpp") == "// relative root edit\n"


def test_workspace_file_management_create_rename_delete() -> None:
    workspace = create_workspace(Path("assignments/byte-class"), "demo-student")

    create_workspace_file(workspace, "helpers.cpp", "// helper\n")
    assert read_workspace_file(workspace, "helpers.cpp") == "// helper\n"

    rename_workspace_file(workspace, "helpers.cpp", "src/helpers.hpp")
    files = {file.path for file in list_workspace_files(workspace)}
    assert "helpers.cpp" not in files
    assert "src/helpers.hpp" in files
    assert read_workspace_file(workspace, "src/helpers.hpp") == "// helper\n"

    delete_workspace_file(workspace, "src/helpers.hpp")
    files = {file.path for file in list_workspace_files(workspace)}
    assert "src/helpers.hpp" not in files


def test_workspace_file_management_rejects_unsafe_paths_and_metadata() -> None:
    workspace = create_workspace(Path("assignments/byte-class"), "demo-student")

    with pytest.raises(WorkspaceError, match="escapes workspace"):
        create_workspace_file(workspace, "../outside.cpp")
    with pytest.raises(WorkspaceError, match="metadata"):
        create_workspace_file(workspace, ".hamrforge/notes.cpp")
    with pytest.raises(WorkspaceError, match="editable text type"):
        create_workspace_file(workspace, "program.exe")
    with pytest.raises(WorkspaceError, match="already exists"):
        rename_workspace_file(workspace, "main.cpp", "Byte.cpp")


def test_grade_workspace_creates_attempt_snapshot_and_reports() -> None:
    workspace = create_workspace(Path("assignments/byte-class"), "demo-student")

    attempt = grade_workspace(workspace)

    assert attempt.result.score == 40
    assert attempt.report_json_path.exists()
    assert attempt.report_md_path.exists()
    assert (attempt.snapshot_path / "main.cpp").exists()
    assert (attempt.path / "attempt.json").exists()


def test_grade_workspace_accepts_runner_override() -> None:
    workspace = create_workspace(Path("assignments/byte-class"), "demo-student")
    runner = RecordingRunner()

    attempt = grade_workspace(workspace, runner=runner, runner_name="recording")

    assert attempt.result.score == 40
    assert attempt.runner == "recording"
    assert runner.compile_calls > 0
    assert runner.run_calls > 0
    assert runner.workspaces
    assert all(workspace.path != runner_workspace for runner_workspace in runner.workspaces)
    assert all(workspace.path not in runner_workspace.parents for runner_workspace in runner.workspaces)


def test_list_attempts_returns_newest_first_and_preserves_runner() -> None:
    workspace = create_workspace(Path("assignments/byte-class"), "demo-student")

    first = grade_workspace(workspace, runner_name="first-runner")
    write_workspace_file(workspace, "Byte.cpp", Path("fixtures/compile-error/Byte.cpp").read_text(encoding="utf-8"))
    second = grade_workspace(workspace, runner_name="second-runner")

    attempts = list_attempts(workspace)

    assert [attempt.attempt_id for attempt in attempts] == [second.attempt_id, first.attempt_id]
    assert attempts[0].runner == "second-runner"
    assert attempts[0].result.score == 12
    assert attempts[1].runner == "first-runner"
    assert attempts[1].result.score == 40
