from __future__ import annotations

from pathlib import Path

from hamrforge.cli import main


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
