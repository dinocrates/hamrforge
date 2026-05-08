from __future__ import annotations

from pathlib import Path

import pytest

from hamrforge.cli import main
from hamrforge import workspace as workspace_module


@pytest.fixture
def isolated_workspace_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "workspaces"
    monkeypatch.setattr(workspace_module, "WORKSPACES_DIR", root)
    return root


def test_grade_cli_accepts_local_unsafe_runner_override(capsys, tmp_path: Path) -> None:
    exit_code = main(
        [
            "grade",
            "assignments/byte-class",
            "test-cases/perfect.zip",
            "--runner",
            "local_unsafe",
            "--out",
            str(tmp_path / "reports"),
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Score: 40 / 40" in output
    assert "Reports saved:" in output


def test_reset_demo_data_cli_recreates_demo_workspaces(capsys, isolated_workspace_root: Path) -> None:
    exit_code = main(["reset-demo-data"])

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Demo data reset for: demo-student" in output
    assert "Workspaces recreated: 2" in output
    assert (isolated_workspace_root / "demo-student" / "byte-class" / "main.cpp").exists()
    assert (isolated_workspace_root / "demo-student" / "byte-constructors" / "main.cpp").exists()
