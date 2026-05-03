from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient

from hamrforge.web import app


def zip_folder(source_dir: Path, zip_path: Path) -> Path:
    with ZipFile(zip_path, "w") as archive:
        for path in source_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir))
    return zip_path


def test_web_index_loads_upload_form() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "HamrForge" in response.text
    assert "Submission ZIP" in response.text


def test_web_grades_uploaded_zip(tmp_path: Path) -> None:
    client = TestClient(app)
    submission = zip_folder(Path("fixtures/perfect"), tmp_path / "perfect.zip")

    with submission.open("rb") as input_file:
        response = client.post(
            "/grade",
            data={"assignment": "assignments/byte-class"},
            files={"submission": ("perfect.zip", input_file, "application/zip")},
        )

    assert response.status_code == 200
    assert "Score: 100 / 100" in response.text
    assert "Menu accepts user input" in response.text
    assert "Markdown report" in response.text


def test_web_reports_bad_zip_error(tmp_path: Path) -> None:
    client = TestClient(app)
    bad_zip = tmp_path / "bad.zip"
    bad_zip.write_text("not a zip", encoding="utf-8")

    with bad_zip.open("rb") as input_file:
        response = client.post(
            "/grade",
            data={"assignment": "assignments/byte-class"},
            files={"submission": ("bad.zip", input_file, "application/zip")},
        )

    assert response.status_code == 400
    assert "Could not grade submission" in response.text
