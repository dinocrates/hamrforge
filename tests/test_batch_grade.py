from __future__ import annotations

import csv
import json
from pathlib import Path
from zipfile import ZipFile

from hamrforge.batch import batch_grade


def zip_folder(source_dir: Path, zip_path: Path) -> Path:
    with ZipFile(zip_path, "w") as archive:
        for path in source_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir))
    return zip_path


def test_batch_grade_writes_csv_summary_and_feedback(tmp_path: Path) -> None:
    perfect = zip_folder(Path("fixtures/perfect"), tmp_path / "perfect.zip")
    compile_error = zip_folder(Path("fixtures/compile-error"), tmp_path / "compile-error.zip")

    result = batch_grade(
        Path("assignments/byte-class"),
        [str(perfect), str(compile_error)],
        tmp_path / "batch-report",
    )

    assert result.graded_count == 2
    assert result.failed_count == 0
    assert result.grades_csv_path.exists()
    assert result.summary_json_path.exists()
    assert (result.feedback_dir / "perfect.md").exists()
    assert (result.feedback_dir / "compile-error.md").exists()

    with result.grades_csv_path.open(newline="", encoding="utf-8") as input_file:
        rows = list(csv.DictReader(input_file))
    assert [row["filename"] for row in rows] == ["compile-error.zip", "perfect.zip"]
    assert rows[0]["score"] == "10"
    assert rows[1]["score"] == "100"

    summary = json.loads(result.summary_json_path.read_text(encoding="utf-8"))
    assert summary["total"] == 2
    assert summary["graded"] == 2
    assert summary["failed"] == 0


def test_batch_grade_continues_after_bad_submission(tmp_path: Path) -> None:
    perfect = zip_folder(Path("fixtures/perfect"), tmp_path / "perfect.zip")
    bad_zip = tmp_path / "not-a-real.zip"
    bad_zip.write_text("this is not a zip", encoding="utf-8")

    result = batch_grade(
        Path("assignments/byte-class"),
        [str(perfect), str(bad_zip)],
        tmp_path / "batch-report",
    )

    assert result.graded_count == 1
    assert result.failed_count == 1
    assert (result.feedback_dir / "not-a-real.md").exists()

    summary = json.loads(result.summary_json_path.read_text(encoding="utf-8"))
    failed = [row for row in summary["submissions"] if row["status"] == "failed"]
    assert failed[0]["filename"] == "not-a-real.zip"
    assert failed[0]["flags"] == ["manual_review_recommended"]


def test_batch_grade_expands_globs(tmp_path: Path) -> None:
    zip_folder(Path("fixtures/perfect"), tmp_path / "student-a.zip")
    zip_folder(Path("fixtures/missing-files"), tmp_path / "student-b.zip")

    result = batch_grade(
        Path("assignments/byte-class"),
        [str(tmp_path / "student-*.zip")],
        tmp_path / "batch-report",
    )

    assert [row.filename for row in result.rows] == ["student-a.zip", "student-b.zip"]
