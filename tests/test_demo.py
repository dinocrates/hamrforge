from __future__ import annotations

from pathlib import Path

import pytest

from hamrforge import workspace as workspace_module
from hamrforge.demo import reset_demo_data
from hamrforge.workspace import (
    WorkspaceError,
    create_workspace,
    grade_workspace_job,
    list_attempts,
    list_grading_jobs,
    list_workspace_files,
    load_workspace,
    write_workspace_file,
)


@pytest.fixture(autouse=True)
def isolated_workspace_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(workspace_module, "WORKSPACES_DIR", tmp_path / "workspaces")


def test_reset_demo_data_recreates_catalog_workspaces_and_preserves_non_demo() -> None:
    demo_workspace = create_workspace(Path("assignments/byte-class"), "demo-student")
    write_workspace_file(demo_workspace, "main.cpp", "// broken demo\n")
    grade_workspace_job(demo_workspace, runner_name="local_unsafe")
    non_demo_workspace = create_workspace(Path("assignments/byte-class"), "student-123")
    write_workspace_file(non_demo_workspace, "main.cpp", "// keep me\n")

    result = reset_demo_data("demo-student")

    reset_byte = load_workspace("demo-student", "byte-class")
    reset_constructors = load_workspace("demo-student", "byte-constructors")
    preserved = load_workspace("student-123", "byte-class")

    assert result.reset_count == 2
    assert {path.name for path in result.workspace_paths} == {"byte-class", "byte-constructors"}
    assert "main.cpp" in {file.path for file in list_workspace_files(reset_byte)}
    assert "main.cpp" in {file.path for file in list_workspace_files(reset_constructors)}
    assert list_attempts(reset_byte) == []
    assert list_grading_jobs(reset_byte) == []
    assert preserved.path.joinpath("main.cpp").read_text(encoding="utf-8") == "// keep me\n"


def test_reset_demo_data_rejects_non_demo_owner() -> None:
    with pytest.raises(WorkspaceError, match="demo owner keys"):
        reset_demo_data("student-123")
