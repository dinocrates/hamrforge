from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient

from hamrforge.web import app
from hamrforge import workspace as workspace_module


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
    assert "Score: 40 / 40" in response.text
    assert "Program runs to completion" in response.text
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


def test_web_workspace_create_edit_and_grade(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(workspace_module, "WORKSPACES_DIR", tmp_path / "workspaces")
    client = TestClient(app)

    create_response = client.post(
        "/workspace/create",
        data={"assignment": "assignments/byte-class", "owner_key": "demo-student"},
        follow_redirects=True,
    )

    assert create_response.status_code == 200
    assert "Workspace: demo-student / byte-class" in create_response.text
    assert "main.cpp" in create_response.text
    assert 'id="workspace-editor"' in create_response.text
    assert "CodeMirror.fromTextArea" in create_response.text
    assert "Assignment instructions" in create_response.text
    assert "Build a C++ `Byte` class" in create_response.text

    save_response = client.post(
        "/workspace/save",
        data={
            "owner_key": "demo-student",
            "assignment_slug": "byte-class",
            "file_path": "main.cpp",
            "content": Path("assignments/byte-class/starter/main.cpp").read_text(encoding="utf-8"),
        },
    )
    assert save_response.status_code == 200
    assert "File saved." in save_response.text
    assert "Save File" in save_response.text

    grade_response = client.post(
        "/workspace/grade",
        data={"owner_key": "demo-student", "assignment_slug": "byte-class", "selected_file": "main.cpp"},
    )

    assert grade_response.status_code == 200
    assert "Workspace graded." in grade_response.text
    assert "Score: 40 / 40" in grade_response.text
