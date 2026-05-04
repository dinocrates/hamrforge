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
    assert "C++ Grading Diagnostics" in response.text
    assert "Semester Assignments" in response.text
    assert "Unit 02 - Byte Class Construction" in response.text
    assert "Unit 03 - Byte Overloaded Constructors" in response.text
    assert "Workspace" in response.text
    assert "Diagnostic Tools" in response.text
    assert "Submission ZIP" in response.text
    assert 'name="runner"' in response.text
    assert "local_unsafe runs student code directly" in response.text
    assert "/static/diagnostic.css" in response.text


def test_web_course_portal_lists_student_courses() -> None:
    client = TestClient(app)

    response = client.get("/courses", params={"owner_key": "demo-student", "role": "student"})

    assert response.status_code == 200
    assert "student portal" in response.text
    assert "My Courses" in response.text
    assert "CS 102-01" in response.text
    assert "CS 150-02" in response.text
    assert "Open Course" in response.text
    assert "Diagnostic Console" in response.text


def test_web_course_section_lists_assignment_publications(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(workspace_module, "WORKSPACES_DIR", tmp_path / "workspaces")
    client = TestClient(app)

    response = client.get(
        "/courses/cs102-01-spring-2026",
        params={"owner_key": "demo-student", "role": "student"},
    )

    assert response.status_code == 200
    assert "CS 102-01" in response.text
    assert "Assignments" in response.text
    assert "Unit 02 - Byte Class Construction" in response.text
    assert "Unit 03 - Byte Overloaded Constructors" in response.text
    assert "Create Workspace" in response.text


def test_web_instructor_course_section_shows_catalog_analytics() -> None:
    client = TestClient(app)

    response = client.get(
        "/courses/cs102-01-spring-2026",
        params={"owner_key": "stephen", "role": "instructor"},
    )

    assert response.status_code == 200
    assert "instructor portal" in response.text
    assert "Published" in response.text
    assert "Drafts" in response.text
    assert "Catalog Source" in response.text


def test_web_landing_page_shows_existing_workspace_scores(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(workspace_module, "WORKSPACES_DIR", tmp_path / "workspaces")
    client = TestClient(app)

    create_response = client.post(
        "/workspace/create",
        data={"assignment": "assignments/byte-class", "owner_key": "demo-student"},
        follow_redirects=True,
    )
    assert create_response.status_code == 200

    grade_response = client.post(
        "/workspace/grade",
        data={
            "owner_key": "demo-student",
            "assignment_slug": "byte-class",
            "selected_file": "main.cpp",
            "runner": "local_unsafe",
        },
    )
    assert grade_response.status_code == 200

    response = client.get("/", params={"owner_key": "demo-student"})

    assert response.status_code == 200
    assert "Workspace ready" in response.text
    assert "Open Workspace" in response.text
    assert "40 / 40" in response.text


def test_web_grades_uploaded_zip(tmp_path: Path) -> None:
    client = TestClient(app)
    submission = zip_folder(Path("fixtures/perfect"), tmp_path / "perfect.zip")

    with submission.open("rb") as input_file:
        response = client.post(
            "/grade",
            data={"assignment": "assignments/byte-class", "runner": "local_unsafe"},
            files={"submission": ("perfect.zip", input_file, "application/zip")},
        )

    assert response.status_code == 200
    assert "Score: 40 / 40" in response.text
    assert "100.0%" in response.text
    assert "Runner" in response.text
    assert "local_unsafe" in response.text
    assert "Program runs to completion" in response.text
    assert "Output and Reports" in response.text
    assert "Compiler stdout" in response.text
    assert "Compiler stderr" in response.text
    assert "Program stdout" in response.text
    assert "Runner logs" in response.text
    assert "Raw report.json" in response.text
    assert "Rendered report.md" in response.text
    assert "Markdown report" in response.text


def test_web_shows_compiler_errors_in_diagnostic_panels(tmp_path: Path) -> None:
    client = TestClient(app)
    submission = zip_folder(Path("fixtures/compile-error"), tmp_path / "compile-error.zip")

    with submission.open("rb") as input_file:
        response = client.post(
            "/grade",
            data={"assignment": "assignments/byte-class", "runner": "local_unsafe"},
            files={"submission": ("compile-error.zip", input_file, "application/zip")},
        )

    assert response.status_code == 200
    assert "Score: 12 / 40" in response.text
    assert "FAIL" in response.text
    assert "Compiler stderr" in response.text
    assert "Your code did not compile." in response.text
    assert "expected" in response.text
    assert "check-failed" in response.text


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
    assert "student workspace" in create_response.text
    assert "byte-class" in create_response.text
    assert "main.cpp" in create_response.text
    assert 'id="workspace-editor"' in create_response.text
    assert "CodeMirror.fromTextArea" in create_response.text
    assert "/static/workspace.js" in create_response.text
    assert "HamrForgeWorkspace.init" in create_response.text
    assert "Assignment instructions" in create_response.text
    assert "Build a C++ `Byte` class" in create_response.text
    assert 'name="runner"' in create_response.text
    assert "Project Explorer" in create_response.text
    assert "file-tree" in create_response.text
    assert "pane-title" in create_response.text
    assert "Feedback" in create_response.text
    assert "New file" in create_response.text
    assert "include/helpers.hpp" in create_response.text
    assert "Rename selected" in create_response.text
    assert "Delete Selected" in create_response.text
    assert "workspace-command-bar" in create_response.text
    assert ">Save</button>" in create_response.text
    assert ">Run</button>" in create_response.text
    assert ">Grade</button>" in create_response.text
    assert "Run Output" in create_response.text
    assert 'id="workspace-run-output-region"' in create_response.text

    create_file_response = client.post(
        "/workspace/file/create",
        data={"owner_key": "demo-student", "assignment_slug": "byte-class", "new_file_path": "include/helpers.cpp"},
    )
    assert create_file_response.status_code == 200
    assert "File created." in create_file_response.text
    assert "include" in create_file_response.text
    assert "helpers.cpp" in create_file_response.text

    rename_file_response = client.post(
        "/workspace/file/rename",
        data={
            "owner_key": "demo-student",
            "assignment_slug": "byte-class",
            "file_path": "include/helpers.cpp",
            "new_file_path": "src/helpers.hpp",
        },
    )
    assert rename_file_response.status_code == 200
    assert "File renamed." in rename_file_response.text
    assert "helpers.hpp" in rename_file_response.text
    assert "src" in rename_file_response.text

    delete_file_response = client.post(
        "/workspace/file/delete",
        data={"owner_key": "demo-student", "assignment_slug": "byte-class", "file_path": "src/helpers.hpp"},
    )
    assert delete_file_response.status_code == 200
    assert "File deleted." in delete_file_response.text
    assert "src/helpers.hpp" not in delete_file_response.text

    unsafe_file_response = client.post(
        "/workspace/file/create",
        data={"owner_key": "demo-student", "assignment_slug": "byte-class", "new_file_path": "../nope.cpp"},
    )
    assert unsafe_file_response.status_code == 400
    assert "escapes workspace" in unsafe_file_response.text

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
    assert ">Save</button>" in save_response.text

    run_response = client.post(
        "/workspace/run",
        data={
            "owner_key": "demo-student",
            "assignment_slug": "byte-class",
            "selected_file": "main.cpp",
            "file_path": "main.cpp",
            "content": Path("assignments/byte-class/starter/main.cpp").read_text(encoding="utf-8"),
            "runner": "local_unsafe",
        },
    )

    assert run_response.status_code == 200
    assert "Workspace saved and program run." in run_response.text
    assert "Run Output" in run_response.text
    assert "Program finished" in run_response.text
    assert "Int:    99" in run_response.text
    assert "String: 01100011" in run_response.text
    assert "No grade attempts yet." in run_response.text

    grade_response = client.post(
        "/workspace/grade",
        data={
            "owner_key": "demo-student",
            "assignment_slug": "byte-class",
            "selected_file": "main.cpp",
            "runner": "local_unsafe",
        },
    )

    assert grade_response.status_code == 200
    assert "Workspace saved and graded." in grade_response.text
    assert "Score: 40 / 40" in grade_response.text
    assert "Latest Result" in grade_response.text
    assert "Attempt History" in grade_response.text
    assert "Latest Detailed Diagnostics" in grade_response.text
    assert "Latest" in grade_response.text
    assert "Best" in grade_response.text
    assert "Total Attempts" in grade_response.text
    assert "report.md" in grade_response.text
    assert "report.json" in grade_response.text
    assert "Runner" in grade_response.text
    assert "local_unsafe" in grade_response.text

    grade_after_edit_response = client.post(
        "/workspace/grade",
        data={
            "owner_key": "demo-student",
            "assignment_slug": "byte-class",
            "selected_file": "Byte.cpp",
            "file_path": "Byte.cpp",
            "content": Path("fixtures/compile-error/Byte.cpp").read_text(encoding="utf-8"),
            "runner": "local_unsafe",
        },
    )

    assert grade_after_edit_response.status_code == 200
    assert "Workspace saved and graded." in grade_after_edit_response.text
    assert "Score: 12 / 40" in grade_after_edit_response.text
    assert "Best" in grade_after_edit_response.text
    assert "40 / 40" in grade_after_edit_response.text
    assert "Total Attempts" in grade_after_edit_response.text
    assert "2" in grade_after_edit_response.text
    assert "Your code did not compile." in grade_after_edit_response.text
    assert 'id="workspace-grade-form"' in grade_after_edit_response.text
    assert 'id="workspace-grade-content"' in grade_after_edit_response.text


def test_api_workspace_run_returns_json_without_page_refresh(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(workspace_module, "WORKSPACES_DIR", tmp_path / "workspaces")
    client = TestClient(app)
    client.post(
        "/workspace/create",
        data={"assignment": "assignments/byte-class", "owner_key": "demo-student"},
        follow_redirects=True,
    )

    response = client.post(
        "/api/workspace/run",
        data={
            "owner_key": "demo-student",
            "assignment_slug": "byte-class",
            "selected_file": "main.cpp",
            "file_path": "main.cpp",
            "content": Path("assignments/byte-class/starter/main.cpp").read_text(encoding="utf-8"),
            "runner": "local_unsafe",
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["notice"] == "Workspace saved and program run."
    assert payload["run"]["succeeded"] is True
    assert payload["run"]["program_stdout"].count("Int:    99") == 1
    assert "Run Output" in payload["run_output_html"]
    assert "Program finished" in payload["run_output_html"]
