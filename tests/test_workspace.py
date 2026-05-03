from __future__ import annotations

from pathlib import Path

import pytest

from hamrforge import workspace as workspace_module
from hamrforge.workspace import (
    WorkspaceError,
    create_workspace,
    grade_workspace,
    list_workspace_files,
    read_workspace_file,
    write_workspace_file,
)


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


def test_grade_workspace_creates_attempt_snapshot_and_reports() -> None:
    workspace = create_workspace(Path("assignments/byte-class"), "demo-student")

    attempt = grade_workspace(workspace)

    assert attempt.result.score == 40
    assert attempt.report_json_path.exists()
    assert attempt.report_md_path.exists()
    assert (attempt.snapshot_path / "main.cpp").exists()
    assert (attempt.path / "attempt.json").exists()
