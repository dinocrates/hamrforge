from __future__ import annotations

import shutil
import time
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

import yaml
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from hamrforge.assignment import load_assignment, validate_assignment
from hamrforge.catalog import (
    CatalogError,
    CourseSection,
    AssignmentPublication,
    append_assignment_publication,
    load_catalog,
    publications_for_section,
    sections_for_user,
)
from hamrforge.demo import reset_demo_data
from hamrforge.grading import GradeError, grade_submission
from hamrforge.models import GradeResult
from hamrforge.runner import create_runner
from hamrforge.workspace import (
    GradingJob,
    ProgramRun,
    Workspace,
    WorkspaceError,
    create_workspace,
    create_workspace_file,
    delete_workspace_file,
    grade_workspace_job,
    latest_grading_job,
    latest_attempt,
    load_grading_job,
    list_attempts,
    list_grading_jobs,
    list_workspace_files,
    load_workspace,
    read_workspace_file,
    rename_workspace_file,
    reset_demo_workspace,
    run_workspace_program,
    write_workspace_file,
)

app = FastAPI(title="HamrForge")

STATIC_DIR = Path(__file__).parent / "static"
DATA_DIR = Path("data")
ASSIGNMENTS_DIR = Path("assignments")
UPLOADS_DIR = DATA_DIR / "uploads"
WEB_REPORTS_DIR = DATA_DIR / "reports"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def index(owner_key: str = "demo-student") -> HTMLResponse:
    return HTMLResponse(_render_front_door(owner_key=owner_key))


@app.post("/demo/reset-data", response_class=HTMLResponse)
def demo_reset_data(
    owner_key: str = Form("demo-student"),
    confirmation: str = Form(""),
) -> HTMLResponse:
    try:
        if confirmation.strip() != "reset demo data":
            raise WorkspaceError('type "reset demo data" to reset demo workspaces')
        result = reset_demo_data(owner_key=owner_key)
    except (WorkspaceError, CatalogError) as exc:
        return HTMLResponse(_render_front_door(owner_key=owner_key, error=str(exc)), status_code=400)
    return HTMLResponse(
        _render_front_door(
            owner_key=owner_key,
            notice=f"Demo data reset for {result.owner_key}. Recreated {result.reset_count} workspace(s).",
        )
    )


@app.get("/courses", response_class=HTMLResponse)
def course_portal(owner_key: str = "demo-student", role: str = "student") -> HTMLResponse:
    try:
        catalog = load_catalog()
    except CatalogError as exc:
        return HTMLResponse(_render_page(error=str(exc)), status_code=500)
    sections = sections_for_user(catalog, owner_key=owner_key, role=role)
    return HTMLResponse(_render_app_page(_render_course_portal(owner_key, role, sections), owner_key=owner_key, role=role))


@app.get("/courses/{section_id}", response_class=HTMLResponse)
def course_section_view(section_id: str, owner_key: str = "demo-student", role: str = "student") -> HTMLResponse:
    try:
        selected, publications = _section_context(section_id, owner_key, role)
    except CatalogError as exc:
        return HTMLResponse(_render_page(error=str(exc)), status_code=500)
    except WorkspaceError as exc:
        return HTMLResponse(_render_app_page(_not_found_panel("Course section was not found for this user.")), status_code=404)
    return HTMLResponse(
        _render_app_page(
            _render_course_section(owner_key, role, selected, publications),
            owner_key=owner_key,
            role=role,
            section=selected,
        )
    )


@app.get("/courses/{section_id}/results", response_class=HTMLResponse)
def instructor_results_view(section_id: str, owner_key: str = "stephen", role: str = "instructor") -> HTMLResponse:
    try:
        selected, publications = _section_context(section_id, owner_key, role)
    except CatalogError as exc:
        return HTMLResponse(_render_page(error=str(exc)), status_code=500)
    except WorkspaceError:
        return HTMLResponse(_render_app_page(_not_found_panel("Course section was not found for this user.")), status_code=404)
    return HTMLResponse(
        _render_app_page(
            _render_instructor_results(owner_key, selected, publications),
            owner_key=owner_key,
            role=role,
            section=selected,
        )
    )


@app.get("/courses/{section_id}/assignment-builder", response_class=HTMLResponse)
def instructor_assignment_builder_view(section_id: str, owner_key: str = "stephen", role: str = "instructor") -> HTMLResponse:
    try:
        selected, publications = _section_context(section_id, owner_key, role)
    except CatalogError as exc:
        return HTMLResponse(_render_page(error=str(exc)), status_code=500)
    except WorkspaceError:
        return HTMLResponse(_render_app_page(_not_found_panel("Course section was not found for this user.")), status_code=404)
    return HTMLResponse(
        _render_app_page(
            _render_assignment_builder_placeholder(selected, publications),
            owner_key=owner_key,
            role=role,
            section=selected,
        )
    )


@app.post("/courses/{section_id}/assignment-builder/create", response_class=HTMLResponse)
def instructor_assignment_builder_create(
    section_id: str,
    owner_key: str = Form("stephen"),
    role: str = Form("instructor"),
    title: str = Form(...),
    slug: str = Form(...),
    points: float = Form(40),
    due: str = Form("Sunday 11:59 PM"),
    status: str = Form("draft"),
    instructions: str = Form("Write your assignment instructions here."),
    required_files: str = Form("main.cpp"),
) -> HTMLResponse:
    try:
        selected, _publications = _section_context(section_id, owner_key, role)
        assignment_path = _create_assignment_from_builder(
            title=title,
            slug=slug,
            points=points,
            due=due,
            status=status,
            instructions=instructions,
            required_files=required_files,
            section_id=section_id,
        )
        refreshed = publications_for_section(load_catalog(), section_id)
        return HTMLResponse(
            _render_app_page(
                _render_assignment_builder_placeholder(
                    selected,
                    refreshed,
                    notice=f"Assignment draft created: {assignment_path.as_posix()}",
                ),
                owner_key=owner_key,
                role=role,
                section=selected,
            )
        )
    except (CatalogError, WorkspaceError, ValueError) as exc:
        try:
            selected, publications = _section_context(section_id, owner_key, role)
            content = _render_assignment_builder_placeholder(selected, publications, error=str(exc))
            return HTMLResponse(_render_app_page(content, owner_key=owner_key, role=role, section=selected), status_code=400)
        except (CatalogError, WorkspaceError):
            return HTMLResponse(_render_page(error=str(exc)), status_code=400)


@app.get("/courses/{section_id}/section-setup", response_class=HTMLResponse)
def instructor_section_setup_view(section_id: str, owner_key: str = "stephen", role: str = "instructor") -> HTMLResponse:
    try:
        selected, publications = _section_context(section_id, owner_key, role)
    except CatalogError as exc:
        return HTMLResponse(_render_page(error=str(exc)), status_code=500)
    except WorkspaceError:
        return HTMLResponse(_render_app_page(_not_found_panel("Course section was not found for this user.")), status_code=404)
    return HTMLResponse(
        _render_app_page(
            _render_section_setup_placeholder(selected, publications),
            owner_key=owner_key,
            role=role,
            section=selected,
        )
    )


@app.post("/grade", response_class=HTMLResponse)
def grade_upload(
    request: Request,
    assignment: str = Form("assignments/byte-class"),
    runner: str = Form("local_unsafe"),
    submission: UploadFile = File(...),
) -> HTMLResponse:
    request_id = uuid4().hex
    upload_dir = UPLOADS_DIR / request_id
    report_dir = WEB_REPORTS_DIR / request_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = Path(submission.filename or "submission.zip").name
    upload_path = upload_dir / safe_filename
    with upload_path.open("wb") as output:
        shutil.copyfileobj(submission.file, output)

    try:
        selected_runner = create_runner(runner)
        started_at = time.monotonic()
        result = grade_submission(Path(assignment), upload_path, report_dir, runner=selected_runner)
        duration_seconds = time.monotonic() - started_at
    except (GradeError, ValueError) as exc:
        return HTMLResponse(_render_page(error=str(exc), assignment=assignment, runner=runner), status_code=400)

    report_json_url = str(request.url_for("download_report", request_id=request_id, filename="report.json"))
    report_md_url = str(request.url_for("download_report", request_id=request_id, filename="report.md"))
    return HTMLResponse(
        _render_page(
            assignment=assignment,
            runner=runner,
            result=result,
            uploaded_filename=safe_filename,
            report_json_url=report_json_url,
            report_md_url=report_md_url,
            duration_seconds=duration_seconds,
        )
    )


@app.post("/workspace/create")
def workspace_create(
    assignment: str = Form("assignments/byte-class"),
    owner_key: str = Form("demo-student"),
    overwrite: str | None = Form(None),
):
    try:
        workspace = create_workspace(Path(assignment), owner_key, overwrite=bool(overwrite))
    except WorkspaceError as exc:
        return HTMLResponse(_render_page(error=str(exc), assignment=assignment), status_code=400)
    return RedirectResponse(_workspace_url(workspace), status_code=303)


@app.get("/workspace", response_class=HTMLResponse)
def workspace_view(
    owner_key: str = "demo-student",
    assignment_slug: str = "byte-class",
    file: str = "",
) -> HTMLResponse:
    try:
        workspace = load_workspace(owner_key, assignment_slug)
        return HTMLResponse(_render_workspace_page(workspace, selected_file=file))
    except WorkspaceError as exc:
        return HTMLResponse(_render_page(error=str(exc)), status_code=404)


@app.post("/workspace/save", response_class=HTMLResponse)
def workspace_save(
    owner_key: str = Form(...),
    assignment_slug: str = Form(...),
    file_path: str = Form(...),
    content: str = Form(...),
) -> HTMLResponse:
    try:
        workspace = load_workspace(owner_key, assignment_slug)
        write_workspace_file(workspace, file_path, content)
        return HTMLResponse(_render_workspace_page(workspace, selected_file=file_path, notice="File saved."))
    except WorkspaceError as exc:
        return HTMLResponse(_render_page(error=str(exc)), status_code=400)


@app.post("/workspace/file/create", response_class=HTMLResponse)
def workspace_file_create(
    owner_key: str = Form(...),
    assignment_slug: str = Form(...),
    new_file_path: str = Form(...),
) -> HTMLResponse:
    try:
        workspace = load_workspace(owner_key, assignment_slug)
        create_workspace_file(workspace, new_file_path)
        return HTMLResponse(_render_workspace_page(workspace, selected_file=new_file_path, notice="File created."))
    except WorkspaceError as exc:
        return HTMLResponse(_render_page(error=str(exc)), status_code=400)


@app.post("/workspace/file/rename", response_class=HTMLResponse)
def workspace_file_rename(
    owner_key: str = Form(...),
    assignment_slug: str = Form(...),
    file_path: str = Form(...),
    new_file_path: str = Form(...),
) -> HTMLResponse:
    try:
        workspace = load_workspace(owner_key, assignment_slug)
        rename_workspace_file(workspace, file_path, new_file_path)
        return HTMLResponse(_render_workspace_page(workspace, selected_file=new_file_path, notice="File renamed."))
    except WorkspaceError as exc:
        return HTMLResponse(_render_page(error=str(exc)), status_code=400)


@app.post("/workspace/file/delete", response_class=HTMLResponse)
def workspace_file_delete(
    owner_key: str = Form(...),
    assignment_slug: str = Form(...),
    file_path: str = Form(...),
) -> HTMLResponse:
    try:
        workspace = load_workspace(owner_key, assignment_slug)
        delete_workspace_file(workspace, file_path)
        return HTMLResponse(_render_workspace_page(workspace, notice="File deleted."))
    except WorkspaceError as exc:
        return HTMLResponse(_render_page(error=str(exc)), status_code=400)


@app.post("/workspace/reset-demo", response_class=HTMLResponse)
def workspace_reset_demo(
    owner_key: str = Form(...),
    assignment_slug: str = Form(...),
    confirmation: str = Form(""),
) -> HTMLResponse:
    try:
        workspace = load_workspace(owner_key, assignment_slug)
        reset_workspace = reset_demo_workspace(workspace, confirmation)
        return HTMLResponse(
            _render_workspace_page(
                reset_workspace,
                notice="Demo workspace reset from starter files.",
            )
        )
    except WorkspaceError as exc:
        return HTMLResponse(_render_page(error=str(exc)), status_code=400)


@app.post("/workspace/grade", response_class=HTMLResponse)
def workspace_grade(
    owner_key: str = Form(...),
    assignment_slug: str = Form(...),
    selected_file: str = Form(""),
    file_path: str = Form(""),
    content: str | None = Form(None),
    runner: str = Form("local_unsafe"),
) -> HTMLResponse:
    try:
        workspace = load_workspace(owner_key, assignment_slug)
        if content is not None and file_path:
            write_workspace_file(workspace, file_path, content)
            selected_file = file_path
        selected_runner = create_runner(runner)
        grade_workspace_job(workspace, runner=selected_runner, runner_name=runner)
        return HTMLResponse(
            _render_workspace_page(
                workspace,
                selected_file=selected_file,
                notice="Workspace saved and grading job completed.",
                runner=runner,
            )
        )
    except (WorkspaceError, GradeError, ValueError) as exc:
        return HTMLResponse(_render_page(error=str(exc)), status_code=400)


@app.post("/workspace/run", response_class=HTMLResponse)
def workspace_run(
    owner_key: str = Form(...),
    assignment_slug: str = Form(...),
    selected_file: str = Form(""),
    file_path: str = Form(""),
    content: str | None = Form(None),
    runner: str = Form("local_unsafe"),
) -> HTMLResponse:
    try:
        workspace = load_workspace(owner_key, assignment_slug)
        if content is not None and file_path:
            write_workspace_file(workspace, file_path, content)
            selected_file = file_path
        selected_runner = create_runner(runner)
        run_result = run_workspace_program(workspace, runner=selected_runner, runner_name=runner)
        return HTMLResponse(
            _render_workspace_page(
                workspace,
                selected_file=selected_file,
                notice="Workspace saved and program run.",
                runner=runner,
                run_result=run_result,
            )
        )
    except (WorkspaceError, ValueError) as exc:
        return HTMLResponse(_render_page(error=str(exc)), status_code=400)


@app.post("/api/workspace/run")
def api_workspace_run(
    owner_key: str = Form(...),
    assignment_slug: str = Form(...),
    selected_file: str = Form(""),
    file_path: str = Form(""),
    content: str | None = Form(None),
    runner: str = Form("local_unsafe"),
) -> JSONResponse:
    try:
        workspace = load_workspace(owner_key, assignment_slug)
        if content is not None and file_path:
            write_workspace_file(workspace, file_path, content)
            selected_file = file_path
        selected_runner = create_runner(runner)
        run_result = run_workspace_program(workspace, runner=selected_runner, runner_name=runner)
        return JSONResponse(
            {
                "ok": True,
                "notice": "Workspace saved and program run.",
                "selected_file": selected_file,
                "run": _program_run_payload(run_result),
                "run_output_html": _render_run_output(run_result),
            }
        )
    except (WorkspaceError, ValueError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


@app.post("/api/workspace/grade")
def api_workspace_grade(
    owner_key: str = Form(...),
    assignment_slug: str = Form(...),
    selected_file: str = Form(""),
    file_path: str = Form(""),
    content: str | None = Form(None),
    runner: str = Form("local_unsafe"),
) -> JSONResponse:
    try:
        workspace = load_workspace(owner_key, assignment_slug)
        if content is not None and file_path:
            write_workspace_file(workspace, file_path, content)
            selected_file = file_path
        selected_runner = create_runner(runner)
        job = grade_workspace_job(workspace, runner=selected_runner, runner_name=runner)
        refreshed_workspace = load_workspace(owner_key, assignment_slug)
        return JSONResponse(
            {
                "ok": True,
                "notice": "Workspace saved and grading job completed.",
                "selected_file": selected_file,
                "job": _grading_job_payload(job),
                **_workspace_grade_fragments(refreshed_workspace),
            }
        )
    except (WorkspaceError, GradeError, ValueError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


@app.get("/api/workspace/jobs/{owner_key}/{assignment_slug}/{job_id}")
def api_workspace_job(owner_key: str, assignment_slug: str, job_id: str) -> JSONResponse:
    try:
        workspace = load_workspace(owner_key, assignment_slug)
        job = load_grading_job(workspace, job_id)
        return JSONResponse(
            {
                "ok": True,
                "job": _grading_job_payload(job),
                **_workspace_grade_fragments(workspace),
            }
        )
    except WorkspaceError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=404)


@app.get("/workspace/report/{owner_key}/{assignment_slug}/{attempt_id}/{filename}")
def workspace_report(owner_key: str, assignment_slug: str, attempt_id: str, filename: str) -> HTMLResponse:
    if filename not in {"report.json", "report.md"}:
        return HTMLResponse("Not found", status_code=404)
    try:
        workspace = load_workspace(owner_key, assignment_slug)
    except WorkspaceError:
        return HTMLResponse("Not found", status_code=404)
    report_path = workspace.path / ".hamrforge" / "attempts" / attempt_id / "reports" / filename
    if not report_path.exists():
        return HTMLResponse("Not found", status_code=404)
    media_type = "application/json" if filename.endswith(".json") else "text/markdown"
    return HTMLResponse(report_path.read_text(encoding="utf-8"), media_type=media_type)


@app.get("/reports/{request_id}/{filename}")
def download_report(request_id: str, filename: str) -> HTMLResponse:
    if filename not in {"report.json", "report.md"}:
        return HTMLResponse("Not found", status_code=404)
    report_path = WEB_REPORTS_DIR / request_id / filename
    if not report_path.exists():
        return HTMLResponse("Not found", status_code=404)
    media_type = "application/json" if filename.endswith(".json") else "text/markdown"
    return HTMLResponse(report_path.read_text(encoding="utf-8"), media_type=media_type)


def _section_context(section_id: str, owner_key: str, role: str) -> tuple[CourseSection, list[AssignmentPublication]]:
    catalog = load_catalog()
    sections = sections_for_user(catalog, owner_key=owner_key, role=role)
    selected = next((section for section in sections if section.section.id == section_id), None)
    if selected is None:
        raise WorkspaceError(f"course section was not found for {owner_key}: {section_id}")
    return selected, publications_for_section(catalog, section_id)


def _render_app_page(
    content: str,
    owner_key: str = "demo-student",
    role: str = "student",
    section: CourseSection | None = None,
) -> str:
    section_text = f"{section.section.display_name} · {section.term.name}" if section else "Course Portal"
    nav = ""
    if section:
        base_query = urlencode({"owner_key": owner_key, "role": role})
        nav = f"""
        <div class="app-toolbar">
          <nav class="main-nav" aria-label="Course navigation">
            <a class="active" href="/courses/{_escape_url(section.section.id)}?{base_query}">Assignments</a>
            <a href="/courses/{_escape_url(section.section.id)}?{base_query}">Workspace</a>
            <a href="/courses/{_escape_url(section.section.id)}?{base_query}">Results</a>
            <a href="/courses?{base_query}">All Courses</a>
          </nav>
        </div>
        """
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HamrForge Courses</title>
  <link rel="stylesheet" href="/static/diagnostic.css">
</head>
<body>
  <header class="hero">
    <div>
      <p class="eyebrow">{_escape(role)} portal</p>
      <h1>HamrForge</h1>
      <p class="subtitle">{_escape(section_text)}</p>
    </div>
    <div class="status-pill">{_escape(owner_key)}</div>
  </header>
  {nav}
  <main>
    {content}
  </main>
</body>
</html>"""


def _render_course_portal(owner_key: str, role: str, sections: list[CourseSection]) -> str:
    current_cards = "\n".join(_render_course_card(owner_key, role, section) for section in sections)
    if not current_cards:
        current_cards = '<p class="muted">No current courses were found for this demo identity.</p>'
    alternate_role = "instructor" if role == "student" else "student"
    alternate_owner = "stephen" if alternate_role == "instructor" else "demo-student"
    title = "My Sections" if role == "instructor" else "My Courses"
    description = (
        "Choose a section to review assignments, prototype analytics, and teaching tools."
        if role == "instructor"
        else "Choose a course to see your assignments and continue your workspaces."
    )
    secondary_html = _render_previous_courses_panel(role)
    return f"""
    <section class="course-portal band card">
      <div class="section-strip">
        <div>
          <h2>{_escape(title)}</h2>
          <p class="muted">{_escape(description)}</p>
        </div>
        <form class="owner-form" action="/courses" method="get">
          <label>
            Owner key
            <input name="owner_key" value="{_escape(owner_key)}" required>
          </label>
          <label>
            Role
            <select name="role">
              {_runner_option("student", role, "student")}
              {_runner_option("instructor", role, "instructor")}
            </select>
          </label>
          <button type="submit">Load Portal</button>
        </form>
      </div>
      <div class="assignment-grid">
        {current_cards}
      </div>
    </section>
    {secondary_html}
    <section class="band card">
      <h2>Prototype shortcuts</h2>
      <div class="links">
        <a class="button-link" href="/courses?owner_key={_escape_url(alternate_owner)}&role={_escape_url(alternate_role)}">Preview {_escape(alternate_role)}</a>
        <a class="button-link" href="/">Diagnostic Console</a>
      </div>
    </section>
    """


def _render_course_card(owner_key: str, role: str, section: CourseSection) -> str:
    query = urlencode({"owner_key": owner_key, "role": role})
    action = "Open Section" if role == "instructor" else "Open Course"
    helper = "Current section" if role == "instructor" else "Current course"
    return f"""
    <article class="assignment-card">
      <div>
        <span class="status-label pass">{_escape(helper)}</span>
        <h3>{_escape(section.section.display_name)}</h3>
        <p class="muted">{_escape(section.course.code)} · {_escape(section.course.title)}</p>
        <p class="muted">{_escape(section.term.name)} · {_escape(section.section.meeting_info)}</p>
      </div>
      <div class="assignment-metrics">
        <div class="metric">
          <span>Role</span>
          <strong>{_escape(section.enrollment.role)}</strong>
        </div>
        <div class="metric">
          <span>Section</span>
          <strong>{_escape(section.section.section_number)}</strong>
        </div>
      </div>
      <a class="button-link" href="/courses/{_escape_url(section.section.id)}?{query}">{_escape(action)}</a>
    </article>
    """


def _render_previous_courses_panel(role: str) -> str:
    title = "Previous Sections" if role == "instructor" else "Previous Courses"
    message = (
        "Archived sections will live here once real course history is connected."
        if role == "instructor"
        else "Archived courses will live here later. For now, this demo focuses on current courses."
    )
    return f"""
    <details class="card secondary-course-panel">
      <summary>{_escape(title)}</summary>
      <p class="muted">{_escape(message)}</p>
    </details>
    """


def _render_course_section(
    owner_key: str,
    role: str,
    section: CourseSection,
    publications: list[AssignmentPublication],
) -> str:
    cards = "\n".join(_render_publication_card(owner_key, publication, role=role) for publication in publications)
    if not cards:
        cards = '<p class="muted">No assignments have been published for this section yet.</p>'
    analytics = _render_instructor_analytics(publications) if role == "instructor" else ""
    actions = _render_instructor_section_actions(owner_key, section) if role == "instructor" else ""
    assignment_intro = (
        "Student assignments" if role == "student" else "Section assignments"
    )
    assignment_note = (
        "Start a new workspace or continue where you left off."
        if role == "student"
        else "Review published work and prototype assignment controls for this section."
    )
    return f"""
    <section class="band card">
      <div class="section-strip">
        <div>
          <h2>{_escape(section.section.display_name)} · {_escape(section.term.name)}</h2>
          <p class="muted">{_escape(section.course.title)} · {_escape(section.section.meeting_info)}</p>
        </div>
        <div class="links">
          <a class="button-link" href="/courses?owner_key={_escape_url(owner_key)}&role={_escape_url(role)}">Back to Courses</a>
        </div>
      </div>
      {analytics}
      {actions}
      <h2>{_escape(assignment_intro)}</h2>
      <p class="muted">{_escape(assignment_note)}</p>
      <div class="assignment-grid">
        {cards}
      </div>
    </section>
    """


def _render_publication_card(owner_key: str, publication: AssignmentPublication, role: str = "student") -> str:
    workspace = _try_load_workspace(owner_key, publication.slug)
    attempts = list_attempts(workspace) if workspace else []
    latest = attempts[0] if attempts else None
    best = max(attempts, key=lambda attempt: _attempt_percent(attempt)) if attempts else None
    workspace_status = "In progress" if workspace else "Not started"
    if role == "instructor":
        action_text = "Open Workspace" if workspace else "Create Demo Workspace"
    else:
        action_text = "Continue Assignment" if workspace else "Start Assignment"
    latest_text = f"{latest.result.score:g} / {latest.result.max_score:g}" if latest else "No attempts"
    best_text = f"{best.result.score:g} / {best.result.max_score:g}" if best else "No attempts"
    return f"""
    <article class="assignment-card">
      <div>
        <span class="status-label {'pass' if publication.status == 'published' else 'fail'}">{_escape(publication.status)}</span>
        <h3>{_escape(publication.title)}</h3>
        <p class="muted">Due: {_escape(publication.due)} · Points: {publication.points:g} · Language: {_escape(publication.language)}</p>
      </div>
      <div class="assignment-metrics">
        <div class="metric">
          <span>Latest</span>
          <strong>{_escape(latest_text)}</strong>
        </div>
        <div class="metric">
          <span>Best</span>
          <strong>{_escape(best_text)}</strong>
        </div>
      </div>
      <form action="/workspace/create" method="post">
        <input type="hidden" name="assignment" value="{_escape(publication.assignment_path.as_posix())}">
        <input type="hidden" name="owner_key" value="{_escape(owner_key)}">
        <button type="submit">{_escape(action_text)}</button>
      </form>
      <p class="muted">{_escape(workspace_status)}</p>
    </article>
    """


def _render_instructor_analytics(publications: list[AssignmentPublication]) -> str:
    published = sum(1 for publication in publications if publication.status == "published")
    drafts = sum(1 for publication in publications if publication.status != "published")
    total = len(publications)
    return f"""
    <div class="instructor-summary history-summary" aria-label="Instructor section summary">
      <div class="metric">
        <span>Published assignments</span>
        <strong>{published}</strong>
      </div>
      <div class="metric">
        <span>Draft assignments</span>
        <strong>{drafts}</strong>
      </div>
      <div class="metric">
        <span>Total assignments</span>
        <strong>{total}</strong>
      </div>
    </div>
    """


def _render_instructor_section_actions(owner_key: str, section: CourseSection) -> str:
    query = urlencode({"owner_key": owner_key, "role": "instructor"})
    base = f"/courses/{_escape_url(section.section.id)}"
    return f"""
    <section class="instructor-action-strip" aria-label="Instructor prototype actions">
      <a class="button-link muted-action" href="{base}/results?{query}">Results</a>
      <a class="button-link muted-action" href="{base}/assignment-builder?{query}">Assignment Builder</a>
      <a class="button-link muted-action" href="{base}/section-setup?{query}">Section Setup</a>
    </section>
    """


def _render_instructor_results(
    owner_key: str,
    section: CourseSection,
    publications: list[AssignmentPublication],
) -> str:
    rows = "\n".join(_render_results_placeholder_row(owner_key, publication) for publication in publications)
    if not rows:
        rows = '<p class="muted">No assignments are published for this section yet.</p>'
    return f"""
    <section class="band card">
      <div class="section-strip">
        <div>
          <p class="eyebrow">prototype instructor surface</p>
          <h2>Section Results</h2>
          <p class="muted">{_escape(section.section.display_name)} · student result data will appear here when rostered attempts exist.</p>
        </div>
        <a class="button-link" href="/courses/{_escape_url(section.section.id)}?owner_key={_escape_url(owner_key)}&role=instructor">Back to Section</a>
      </div>
      <div class="history-summary">
        <div class="metric">
          <span>Missing assignments</span>
          <strong>prototype</strong>
        </div>
        <div class="metric">
          <span>Average score</span>
          <strong>prototype</strong>
        </div>
        <div class="metric">
          <span>Compile errors</span>
          <strong>prototype</strong>
        </div>
      </div>
      <div class="prototype-table">
        {rows}
      </div>
    </section>
    """


def _render_results_placeholder_row(owner_key: str, publication: AssignmentPublication) -> str:
    workspace = _try_load_workspace(owner_key, publication.slug)
    attempts = list_attempts(workspace) if workspace else []
    latest = attempts[0] if attempts else None
    latest_text = f"{latest.result.score:g} / {latest.result.max_score:g}" if latest else "No demo attempts"
    return f"""
    <article class="attempt-row">
      <div>
        <span class="status-label {'pass' if publication.status == 'published' else 'fail'}">{_escape(publication.status)}</span>
        <h3>{_escape(publication.title)}</h3>
        <p class="muted">Due: {_escape(publication.due)} · Points: {publication.points:g}</p>
      </div>
      <div class="attempt-score">
        <strong>{_escape(latest_text)}</strong>
        <span>demo owner</span>
      </div>
    </article>
    """


def _render_assignment_builder_placeholder(
    section: CourseSection,
    publications: list[AssignmentPublication],
    notice: str = "",
    error: str = "",
) -> str:
    assignment_options = "\n".join(
        f"<option>{_escape(publication.title)}</option>" for publication in publications
    )
    if not assignment_options:
        assignment_options = "<option>No section assignments yet</option>"
    notice_html = f'<section class="notice" role="status">{_escape(notice)}</section>' if notice else ""
    error_html = f'<section class="notice error" role="alert"><strong>Could not create assignment.</strong><pre>{_escape(error)}</pre></section>' if error else ""
    return f"""
    <section class="band card">
      <div class="section-strip">
        <div>
          <p class="eyebrow">prototype instructor surface</p>
          <h2>Assignment Builder</h2>
          <p class="muted">This will become the teacher-friendly editor for assignment metadata, starter files, required files, checks, and publish state.</p>
        </div>
      </div>
      {notice_html}
      {error_html}
      <div class="assignment-builder-layout">
        <section class="builder-panel builder-primary-panel">
          <h3>New Assignment</h3>
          <form class="builder-form" action="/courses/{_escape_url(section.section.id)}/assignment-builder/create" method="post">
            <input type="hidden" name="owner_key" value="stephen">
            <input type="hidden" name="role" value="instructor">
            <label>
              Title
              <input name="title" value="Unit 04 - New C++ Assignment" required>
            </label>
            <label>
              Slug
              <input name="slug" value="unit-04-new-assignment" required>
            </label>
            <label>
              Language
              <input value="cpp" disabled>
            </label>
            <label>
              Points
              <input name="points" type="number" min="1" value="40" required>
            </label>
            <label>
              Due
              <input name="due" value="Sunday 11:59 PM">
            </label>
            <label>
              Publish status
              <select name="status">
                <option value="draft">draft</option>
                <option value="published">published</option>
              </select>
            </label>
            <label>
              Required files
              <textarea name="required_files" rows="3">main.cpp
Assignment.cpp
Assignment.h</textarea>
            </label>
            <label>
              Student instructions
              <textarea name="instructions" rows="7">Describe the assignment here. Students will receive starter files and can run/grade their work in HamrForge.</textarea>
            </label>
            <button type="submit">Create Assignment Draft</button>
          </form>
        </section>
        <aside class="builder-side-rail">
          <section class="builder-panel">
            <h3>Preview assignment.yml</h3>
            <pre class="mini-output">title: Unit 04 - New C++ Assignment
slug: unit-04-new-assignment
language: cpp
standard: c++17
compiler: g++
max_score: 40
runner: local_unsafe

checks:
  - name: Required files
    type: file_check
    points: 16
  - name: Compiles
    type: compile
    points: 12
  - name: Program runs to completion
    type: console_io
    points: 12</pre>
          </section>
          <section class="builder-panel">
            <h3>Current section assignments</h3>
            <label>
              Assignment
              <select>{assignment_options}</select>
            </label>
            <p class="muted">Created assignments are portable folders under <code>assignments/</code> and are published through the file-backed catalog for now.</p>
          </section>
          <section class="builder-panel">
            <h3>Preview student instructions</h3>
            <p class="muted">The generated <code>README.md</code> becomes the instructions students see in the workspace.</p>
          </section>
        </aside>
      </div>
    </section>
    """


def _render_section_setup_placeholder(
    section: CourseSection,
    publications: list[AssignmentPublication],
) -> str:
    return f"""
    <section class="band card">
      <div class="section-strip">
        <div>
          <p class="eyebrow">prototype instructor surface</p>
          <h2>Section Setup</h2>
          <p class="muted">Configure course section details, copy prior materials, and reserve Canvas/LTI connection information.</p>
        </div>
      </div>
      <div class="builder-grid">
        <section class="builder-panel">
          <h3>Section details</h3>
          <p><strong>{_escape(section.course.code)}</strong> · {_escape(section.course.title)}</p>
          <p class="muted">{_escape(section.section.display_name)} · {_escape(section.term.name)} · {_escape(section.section.meeting_info)}</p>
        </section>
        <section class="builder-panel">
          <h3>Copy from previous section</h3>
          <p class="muted">Future workflow: import assignments, starter files, checks, due dates, and publish states from a previous course or section.</p>
        </section>
        <section class="builder-panel">
          <h3>Canvas/LTI connection</h3>
          <p class="muted">Future workflow: store deployment details, launch mappings, deep linking configuration, and grade passback policy.</p>
        </section>
        <section class="builder-panel">
          <h3>Section assignments</h3>
          <p class="muted">{len(publications)} assignment publication(s) are currently listed in the file-backed catalog.</p>
        </section>
      </div>
    </section>
    """


def _create_assignment_from_builder(
    title: str,
    slug: str,
    points: float,
    due: str,
    status: str,
    instructions: str,
    required_files: str,
    section_id: str,
) -> Path:
    safe_slug = _safe_slug(slug)
    title = title.strip()
    if not title:
        raise ValueError("assignment title is required")
    if points <= 0:
        raise ValueError("points must be positive")
    if status not in {"draft", "published"}:
        raise ValueError("publish status must be draft or published")

    files = [_normalize_required_file(line) for line in required_files.splitlines() if line.strip()]
    if not files:
        raise ValueError("at least one required file is needed")
    if not any(Path(filename).suffix == ".cpp" for filename in files):
        files.insert(0, "main.cpp")

    assignment_dir = ASSIGNMENTS_DIR / safe_slug
    if assignment_dir.exists():
        raise ValueError(f"assignment already exists: {assignment_dir.as_posix()}")
    starter_dir = assignment_dir / "starter"
    starter_dir.mkdir(parents=True)

    assignment_config = {
        "title": title,
        "slug": safe_slug,
        "language": "cpp",
        "standard": "c++17",
        "compiler": "g++",
        "max_score": float(points),
        "runner": "local_unsafe",
        "submission": {
            "required_files": files,
            "accepted_extensions": [".cpp", ".h", ".hpp", ".zip"],
            "ignored_paths": [".vs", "Debug", "Release", "x64", "__MACOSX"],
        },
        "checks": [
            {"name": "Required files", "type": "file_check", "points": round(float(points) * 0.4, 2)},
            {"name": "Compiles", "type": "compile", "points": round(float(points) * 0.3, 2)},
            {
                "name": "Program runs to completion",
                "type": "console_io",
                "points": round(float(points) * 0.3, 2),
                "input": "",
                "expected_contains": [],
            },
        ],
    }
    (assignment_dir / "assignment.yml").write_text(yaml.safe_dump(assignment_config, sort_keys=False), encoding="utf-8")
    (assignment_dir / "README.md").write_text(_assignment_readme(title, instructions), encoding="utf-8")
    for filename in files:
        path = starter_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_starter_file_content(filename, title), encoding="utf-8")

    validation = validate_assignment(assignment_dir)
    if not validation.is_valid:
        shutil.rmtree(assignment_dir, ignore_errors=True)
        raise ValueError("generated assignment is invalid: " + "; ".join(validation.errors))

    append_assignment_publication(
        section_id=section_id,
        assignment_path=assignment_dir,
        status=status,
        due=due.strip() or "Sunday 11:59 PM",
        points=float(points),
    )
    return assignment_dir


def _safe_slug(value: str) -> str:
    safe = "".join(character.lower() if character.isalnum() else "-" for character in value.strip())
    safe = "-".join(part for part in safe.split("-") if part)
    if not safe:
        raise ValueError("assignment slug is required")
    return safe


def _normalize_required_file(value: str) -> str:
    filename = value.strip().replace("\\", "/")
    path = Path(filename)
    if path.is_absolute() or ".." in path.parts or not path.name:
        raise ValueError(f"invalid required file path: {value}")
    return path.as_posix()


def _assignment_readme(title: str, instructions: str) -> str:
    return f"# {title}\n\n{instructions.strip()}\n"


def _starter_file_content(filename: str, title: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".cpp" and Path(filename).name == "main.cpp":
        return f"""// {title}
// Starter main.cpp generated by HamrForge.

#include <iostream>

int main() {{
    std::cout << "Hello from HamrForge" << std::endl;
    return 0;
}}
"""
    if suffix in {".h", ".hpp"}:
        guard = _safe_slug(filename).replace("-", "_").upper()
        return f"""// {title}
// Starter header generated by HamrForge.

#ifndef {guard}
#define {guard}

#endif
"""
    return f"// {title}\n// Starter file generated by HamrForge.\n"


def _not_found_panel(message: str) -> str:
    return f"""
    <section class="notice error" role="alert">
      <strong>Not found.</strong>
      <p>{_escape(message)}</p>
    </section>
    """


def _render_page(
    assignment: str = "assignments/byte-class",
    owner_key: str = "demo-student",
    runner: str = "local_unsafe",
    result: GradeResult | None = None,
    uploaded_filename: str = "",
    error: str = "",
    report_json_url: str = "",
    report_md_url: str = "",
    duration_seconds: float | None = None,
    extra_html: str = "",
) -> str:
    result_html = ""
    if error:
        result_html = f"""
        <section class="notice error" role="alert">
          <strong>Could not grade submission.</strong>
          <pre>{_escape(error)}</pre>
        </section>
        """
    elif result:
        result_html = _render_result(
            result,
            uploaded_filename,
            report_json_url,
            report_md_url,
            runner=runner,
            duration_seconds=duration_seconds,
        )
    elif extra_html:
        result_html = extra_html

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HamrForge</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css">
  <link rel="stylesheet" href="/static/diagnostic.css">
</head>
<body>
  <header class="hero">
    <div>
      <p class="eyebrow">private diagnostic panel</p>
      <h1>HamrForge</h1>
      <p class="subtitle">C++ Grading Diagnostics</p>
    </div>
    <div class="status-pill">Rev 1 · C++ adapter · local lab build</div>
  </header>
  <main>
    {_render_assignment_launcher(owner_key)}
    {_render_diagnostic_tools(assignment, runner)}
    {result_html}
  </main>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/clike/clike.min.js"></script>
  <script src="/static/workspace.js"></script>
  <script>
    const editorTextarea = document.getElementById("workspace-editor");
    let workspaceEditor = null;
    if (editorTextarea && window.CodeMirror) {{
      workspaceEditor = CodeMirror.fromTextArea(editorTextarea, {{
        mode: "text/x-c++src",
        lineNumbers: true,
        indentUnit: 4,
        tabSize: 4,
        viewportMargin: Infinity
      }});
      const editorForm = editorTextarea.closest("form");
      if (editorForm) {{
        editorForm.addEventListener("submit", () => workspaceEditor.save());
      }}
      const saveForm = document.getElementById("workspace-save-form");
      if (saveForm) {{
        saveForm.addEventListener("submit", () => workspaceEditor.save());
      }}
    }}
    const bufferForms = document.querySelectorAll(".workspace-buffer-form");
    if (bufferForms.length && editorTextarea) {{
      bufferForms.forEach((form) => {{
        form.addEventListener("submit", () => {{
          const bufferContent = form.querySelector(".workspace-buffer-content");
          if (!bufferContent) {{
            return;
          }}
          if (workspaceEditor) {{
            bufferContent.value = workspaceEditor.getValue();
          }} else {{
            bufferContent.value = editorTextarea.value;
          }}
          const runnerSelect = document.getElementById("workspace-runner-select");
          const runRunner = document.getElementById("workspace-run-runner");
          if (runnerSelect && runRunner) {{
            runRunner.value = runnerSelect.value;
          }}
        }});
      }});
    }}
    if (window.HamrForgeWorkspace) {{
      window.HamrForgeWorkspace.init({{
        getEditorValue: () => workspaceEditor ? workspaceEditor.getValue() : (editorTextarea ? editorTextarea.value : "")
      }});
    }}
  </script>
</body>
</html>"""


def _render_front_door(
    owner_key: str = "demo-student",
    assignment: str = "assignments/byte-class",
    runner: str = "local_unsafe",
    notice: str = "",
    error: str = "",
) -> str:
    message_html = ""
    if notice:
        message_html = f'<section class="notice" role="status">{_escape(notice)}</section>'
    if error:
        message_html = f'<section class="notice error" role="alert"><strong>Could not reset demo data.</strong><pre>{_escape(error)}</pre></section>'
    return _render_page(
        owner_key=owner_key,
        assignment=assignment,
        runner=runner,
        extra_html=f"""
        <section class="front-door">
          <article class="front-door-panel">
            <p class="eyebrow">prototype front door</p>
            <h2>Choose a HamrForge demo path</h2>
            <p class="muted">Start from courses first, then open assignments and workspaces. The diagnostic tools are still here when we need the lab bench.</p>
            <div class="demo-path-grid">
              <a class="demo-path-card" href="/courses?owner_key=demo-student&role=student">
                <span class="status-label pass">Student Demo</span>
                <h3>Open student courses</h3>
                <p>See current course cards, open a section, launch an assignment workspace, run code, and grade.</p>
              </a>
              <a class="demo-path-card" href="/courses?owner_key=stephen&role=instructor">
                <span class="status-label">Instructor Demo</span>
                <h3>Open instructor sections</h3>
                <p>Preview section dashboards, assignment cards, and early analytics for teaching workflows.</p>
              </a>
            </div>
          </article>
        </section>
        <details class="card diagnostic-tools">
          <summary>Diagnostic Tools</summary>
          {message_html}
          {_render_assignment_launcher(owner_key)}
          {_render_demo_data_reset_tool(owner_key)}
          {_render_diagnostic_tools(assignment, runner)}
        </details>
        """,
    )


def _render_demo_data_reset_tool(owner_key: str) -> str:
    return f"""
    <section class="demo-data-reset">
      <h2>Demo data reset</h2>
      <p class="muted">Prototype-only: recreate the demo student workspaces from starter files and clear demo attempts/jobs. Non-demo workspaces are not touched.</p>
      <form class="inline-grid compact-inline-grid" action="/demo/reset-data" method="post">
        <label>
          Owner key
          <input name="owner_key" value="{_escape(owner_key)}" required>
        </label>
        <label>
          Type reset demo data
          <input name="confirmation" placeholder="reset demo data" required>
        </label>
        <button class="danger-button" type="submit">Reset Demo Data</button>
      </form>
    </section>
    """


def _render_diagnostic_tools(assignment: str, runner: str) -> str:
    return f"""
    <details class="card diagnostic-tools">
      <summary>Diagnostic Tools</summary>
      <section>
        <h2>Legacy ZIP grading</h2>
        <form class="inline-grid" action="/grade" method="post" enctype="multipart/form-data">
          <label>
            Assignment folder
            <input name="assignment" value="{_escape(assignment)}" required>
          </label>
          <label>
            Submission ZIP
            <input name="submission" type="file" accept=".zip" required>
          </label>
          <label>
            Runner
            <select name="runner" required>
              {_runner_option("local_unsafe", runner, "local_unsafe")}
              {_runner_option("podman", runner, "podman")}
            </select>
          </label>
          <button type="submit">Grade ZIP</button>
        </form>
        {_runner_notice(runner)}
      </section>
    </details>
    """


def _render_assignment_launcher(owner_key: str) -> str:
    assignments = _discover_assignments()
    cards = "\n".join(_render_assignment_card(owner_key, assignment) for assignment in assignments)
    if not cards:
        cards = '<p class="muted">No valid assignments were found under the assignments folder.</p>'
    return f"""
    <section class="band card">
      <h2>Semester Assignments</h2>
      <form class="owner-form" action="/" method="get">
        <label>
          Owner key
          <input name="owner_key" value="{_escape(owner_key)}" required>
        </label>
        <button type="submit">Load Semester</button>
      </form>
      <div class="assignment-grid">
        {cards}
      </div>
    </section>
    """


def _discover_assignments() -> list[dict[str, object]]:
    if not ASSIGNMENTS_DIR.exists():
        return []
    discovered: list[dict[str, object]] = []
    for assignment_dir in sorted(path for path in ASSIGNMENTS_DIR.iterdir() if path.is_dir()):
        validation = validate_assignment(assignment_dir)
        if not validation.is_valid:
            continue
        assignment = load_assignment(assignment_dir)
        discovered.append(
            {
                "path": assignment_dir,
                "title": str(assignment["title"]),
                "slug": str(assignment["slug"]),
                "language": str(assignment["language"]),
                "max_score": float(assignment["max_score"]),
                "runner": str(assignment.get("runner", "local_unsafe")),
            }
        )
    return discovered


def _render_assignment_card(owner_key: str, assignment: dict[str, object]) -> str:
    assignment_path = Path(assignment["path"])
    slug = str(assignment["slug"])
    workspace = _try_load_workspace(owner_key, slug)
    attempts = list_attempts(workspace) if workspace else []
    latest = attempts[0] if attempts else None
    best = max(attempts, key=lambda attempt: _attempt_percent(attempt)) if attempts else None
    workspace_status = "Workspace ready" if workspace else "Not started"
    action_text = "Open Workspace" if workspace else "Create Workspace"
    latest_text = f"{latest.result.score:g} / {latest.result.max_score:g}" if latest else "No attempts"
    best_text = f"{best.result.score:g} / {best.result.max_score:g}" if best else "No attempts"
    return f"""
    <article class="assignment-card">
      <div>
        <span class="status-label {'pass' if workspace else 'fail'}">{_escape(workspace_status)}</span>
        <h3>{_escape(assignment["title"])}</h3>
        <p class="muted">Slug: {_escape(slug)} · Language: {_escape(assignment["language"])}</p>
      </div>
      <div class="assignment-metrics">
        <div class="metric">
          <span>Latest</span>
          <strong>{_escape(latest_text)}</strong>
        </div>
        <div class="metric">
          <span>Best</span>
          <strong>{_escape(best_text)}</strong>
        </div>
      </div>
      <form action="/workspace/create" method="post">
        <input type="hidden" name="assignment" value="{_escape(assignment_path.as_posix())}">
        <input type="hidden" name="owner_key" value="{_escape(owner_key)}">
        <button type="submit">{_escape(action_text)}</button>
      </form>
    </article>
    """


def _try_load_workspace(owner_key: str, assignment_slug: str) -> Workspace | None:
    try:
        return load_workspace(owner_key, assignment_slug)
    except WorkspaceError:
        return None


def _render_result(
    result: GradeResult,
    uploaded_filename: str,
    report_json_url: str,
    report_md_url: str,
    runner: str = "local_unsafe",
    duration_seconds: float | None = None,
) -> str:
    rows = "\n".join(_render_check_row(check) for check in result.checks)
    flags = ", ".join(result.flags) if result.flags else "None"
    percent = (result.score / result.max_score * 100) if result.max_score else 0
    passed = all(check.passed for check in result.checks)
    status_text = "PASS" if passed else "FAIL"
    status_class = "pass" if passed else "fail"
    duration = f"{duration_seconds:.2f}s" if duration_seconds is not None else "not recorded"
    report_json_text = _read_report_text(result.report_json_path)
    report_md_text = _read_report_text(result.report_md_path)
    output_panels = _render_output_panels(result, report_json_text, report_md_text)
    return f"""
    <section class="results-grid">
      <article class="card summary-card">
        <div>
          <p class="eyebrow">grading result</p>
          <div class="score">Score: {result.score:g} / {result.max_score:g}</div>
          <p class="muted">{percent:.1f}% · Submission: {_escape(uploaded_filename)}</p>
        </div>
        <div class="summary-metrics" aria-label="Result summary">
          <div class="metric">
            <span>Status</span>
            <strong class="{status_class}">{status_text}</strong>
          </div>
          <div class="metric">
            <span>Runner</span>
            <strong>{_escape(runner)}</strong>
          </div>
          <div class="metric">
            <span>Duration</span>
            <strong>{_escape(duration)}</strong>
          </div>
          <div class="metric">
            <span>Flags</span>
            <strong>{_escape(flags)}</strong>
          </div>
        </div>
      </article>
      <article class="card">
        <h2>Checks</h2>
        <div class="check-list">
          {rows}
        </div>
      </article>
      <article class="card output-card">
        <h2>Output and Reports</h2>
        {output_panels}
      </article>
      <div class="links">
        <a class="button-link" href="{_escape(report_md_url)}">Markdown report</a>
        <a class="button-link" href="{_escape(report_json_url)}">JSON report</a>
      </div>
    </section>
    """


def _render_check_row(check: object) -> str:
    status_text = "Passed" if check.passed else "Failed"
    status_class = "pass" if check.passed else "fail"
    detail = f"<pre class=\"mini-output\">{_escape(check.detail)}</pre>" if check.detail and not check.passed else ""
    return f"""
    <section class="check-row {'check-failed' if not check.passed else 'check-passed'}">
      <div>
        <span class="status-label {status_class}">{status_text}</span>
        <h3>{_escape(check.name)}</h3>
        <p>{_escape(check.feedback)}</p>
        {detail}
      </div>
      <strong class="points">{check.score:g} / {check.max_score:g}</strong>
    </section>
    """


def _render_output_panels(result: GradeResult, report_json_text: str, report_md_text: str) -> str:
    compiler_details = "\n\n".join(
        f"{check.name}\n{check.detail}"
        for check in result.checks
        if check.detail and check.type in {"compile", "expression_test"}
    )
    console_details = "\n\n".join(
        f"{check.name}\n{check.detail}" for check in result.checks if check.detail and check.type == "console_io"
    )
    runner_logs = "\n".join(
        line
        for check in result.checks
        for line in check.detail.splitlines()
        if _is_runner_log_line(line)
    )

    compiler_stdout = _empty_panel_text("No separate compiler stdout captured yet.")
    compiler_stderr = compiler_details or _empty_panel_text("No compiler stderr or compile diagnostics captured.")
    program_stdout = _extract_labeled_block(console_details, "Program stdout:", "Program stderr:")
    program_stderr = _extract_labeled_block(console_details, "Program stderr:", None)

    panels = [
        ("Compiler stdout", compiler_stdout, False, "output-block"),
        ("Compiler stderr", compiler_stderr, bool(compiler_details), "output-block output-error"),
        ("Program stdout", program_stdout or _empty_panel_text("No program stdout captured."), bool(program_stdout), "output-block"),
        ("Program stderr", program_stderr or _empty_panel_text("No program stderr captured."), bool(program_stderr), "output-block output-error"),
        ("Runner logs", runner_logs or _empty_panel_text("No runner log lines captured."), bool(runner_logs), "output-block"),
        ("Raw report.json", report_json_text, False, "output-block"),
        ("Rendered report.md", report_md_text, False, "output-block"),
    ]
    return "\n".join(_render_output_panel(title, body, open_panel, css_class) for title, body, open_panel, css_class in panels)


def _render_output_panel(title: str, body: str, open_panel: bool, css_class: str) -> str:
    open_attr = " open" if open_panel else ""
    return f"""
    <details class="output-panel"{open_attr}>
      <summary>{_escape(title)}</summary>
      <pre class="{css_class}">{_escape(body)}</pre>
    </details>
    """


def _render_latest_result_panel(workspace: Workspace, attempt: Attempt | None) -> str:
    if attempt is None:
        return """
        <aside class="latest-panel">
          <h2>Latest Result</h2>
          <p class="muted">No grade attempts yet.</p>
        </aside>
        """
    percent = _attempt_percent(attempt)
    status_text = "Passed" if all(check.passed for check in attempt.result.checks) else "Review"
    status_class = "pass" if status_text == "Passed" else "fail"
    report_md_url = f"/workspace/report/{_escape_url(workspace.owner_key)}/{_escape_url(workspace.assignment_slug)}/{_escape_url(attempt.attempt_id)}/report.md"
    report_json_url = f"/workspace/report/{_escape_url(workspace.owner_key)}/{_escape_url(workspace.assignment_slug)}/{_escape_url(attempt.attempt_id)}/report.json"
    flags = ", ".join(attempt.result.flags) if attempt.result.flags else "None"
    return f"""
    <aside class="latest-panel">
      <h2>Latest Result</h2>
      <span class="status-label {status_class}">{status_text}</span>
      <div class="score compact-score">{attempt.result.score:g} / {attempt.result.max_score:g}</div>
      <p class="muted">{percent:.1f}% · Runner: {_escape(attempt.runner)}</p>
      <p class="muted">Flags: {_escape(flags)}</p>
      <div class="links">
        <a href="{_escape(report_md_url)}">report.md</a>
        <a href="{_escape(report_json_url)}">report.json</a>
      </div>
    </aside>
    """


def _render_latest_job_panel(job: GradingJob | None) -> str:
    if job is None:
        return """
        <aside class="latest-panel">
          <h2>Latest Job</h2>
          <p class="muted">No grading jobs yet.</p>
        </aside>
        """
    status_class = "pass" if job.status == "completed" else "fail" if job.status == "failed" else ""
    score_text = ""
    if job.score is not None and job.max_score is not None:
        score_text = f'<div class="score compact-score">{job.score:g} / {job.max_score:g}</div>'
    error_text = f'<p class="muted">Error: {_escape(job.error)}</p>' if job.error else ""
    attempt_text = f" · Attempt: {_escape(_format_attempt_id(job.attempt_id))}" if job.attempt_id else ""
    return f"""
    <aside class="latest-panel">
      <h2>Latest Job</h2>
      <span class="status-label {status_class}">{_escape(job.status)}</span>
      {score_text}
      <p class="muted">Runner: {_escape(job.runner)}{attempt_text}</p>
      {error_text}
    </aside>
    """


def _render_feedback_summary(workspace: Workspace, job: GradingJob | None, attempt: Attempt | None) -> str:
    if attempt is None:
        job_text = "No grading jobs yet." if job is None else f"Latest job: {job.status}"
        return f"""
        <aside class="latest-panel feedback-summary-card">
          <h2>Feedback Summary</h2>
          <p class="muted">No grade attempts yet.</p>
          <p class="muted">{_escape(job_text)}</p>
        </aside>
        """

    percent = _attempt_percent(attempt)
    passed = all(check.passed for check in attempt.result.checks)
    status_text = "Passed" if passed else "Review"
    status_class = "pass" if passed else "fail"
    flags = ", ".join(attempt.result.flags) if attempt.result.flags else "None"
    job_status = job.status if job else "not recorded"
    job_class = "pass" if job_status == "completed" else "fail" if job_status == "failed" else ""
    report_md_url = f"/workspace/report/{_escape_url(workspace.owner_key)}/{_escape_url(workspace.assignment_slug)}/{_escape_url(attempt.attempt_id)}/report.md"
    report_json_url = f"/workspace/report/{_escape_url(workspace.owner_key)}/{_escape_url(workspace.assignment_slug)}/{_escape_url(attempt.attempt_id)}/report.json"
    return f"""
    <aside class="latest-panel feedback-summary-card">
      <div class="summary-heading-row">
        <h2>Feedback Summary</h2>
        <span class="status-label {status_class}">{status_text}</span>
      </div>
      <div class="score compact-score">{attempt.result.score:g} / {attempt.result.max_score:g}</div>
      <p class="muted">{percent:.1f}% · Runner: {_escape(attempt.runner)}</p>
      <div class="feedback-meta-grid">
        <div>
          <span>Job</span>
          <strong class="{job_class}">{_escape(job_status)}</strong>
        </div>
        <div>
          <span>Flags</span>
          <strong>{_escape(flags)}</strong>
        </div>
      </div>
      <div class="links">
        <a href="{_escape(report_md_url)}">report.md</a>
        <a href="{_escape(report_json_url)}">report.json</a>
      </div>
    </aside>
    """


def _extract_labeled_block(text: str, start_label: str, end_label: str | None) -> str:
    if start_label not in text:
        return ""
    start = text.find(start_label) + len(start_label)
    end = text.find(end_label, start) if end_label else -1
    block = text[start:] if end == -1 else text[start:end]
    return block.strip()


def _is_runner_log_line(line: str) -> bool:
    markers = (
        "Podman",
        "Local unsafe",
        "timed out",
        "container exited",
        "HamrForge output truncated",
    )
    return any(marker in line for marker in markers)


def _read_report_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return "Report file was not available."


def _empty_panel_text(message: str) -> str:
    return f"[{message}]"


def _runner_option(value: str, selected: str, label: str) -> str:
    selected_attr = " selected" if value == selected else ""
    return f'<option value="{_escape(value)}"{selected_attr}>{_escape(label)}</option>'


def _runner_notice(runner: str) -> str:
    if runner == "local_unsafe":
        return '<p class="warning">local_unsafe runs student code directly on this machine. Use it only for development testing.</p>'
    return '<p class="runner-note">podman runs grading commands inside the configured C++ runner container.</p>'


def _render_workspace_page(
    workspace: Workspace,
    selected_file: str = "",
    notice: str = "",
    runner: str = "local_unsafe",
    run_result: ProgramRun | None = None,
) -> str:
    files = list_workspace_files(workspace)
    editable_files = [file for file in files if file.editable]
    if not selected_file and editable_files:
        selected_file = editable_files[0].path
    content = ""
    read_error = ""
    if selected_file:
        try:
            content = read_workspace_file(workspace, selected_file)
        except WorkspaceError as exc:
            read_error = str(exc)

    attempt = latest_attempt(workspace)
    result_html = ""
    if attempt:
        report_md_url = f"/workspace/report/{_escape_url(workspace.owner_key)}/{_escape_url(workspace.assignment_slug)}/{_escape_url(attempt.attempt_id)}/report.md"
        report_json_url = f"/workspace/report/{_escape_url(workspace.owner_key)}/{_escape_url(workspace.assignment_slug)}/{_escape_url(attempt.attempt_id)}/report.json"
        result_html = _render_result(
            attempt.result,
            f"{workspace.owner_key}/{workspace.assignment_slug}",
            report_json_url,
            report_md_url,
            runner=attempt.runner,
        )
    latest_job = latest_grading_job(workspace)
    latest_panel_html = _render_latest_result_panel(workspace, attempt)
    job_panel_html = _render_latest_job_panel(latest_job)
    feedback_summary_html = _render_feedback_summary(workspace, latest_job, attempt)
    history_html = _render_attempt_history(workspace)
    job_history_html = _render_job_history(workspace)
    diagnostics_html = _render_latest_diagnostics(result_html)
    activity_html = _render_workspace_activity(history_html, job_history_html, diagnostics_html)
    run_output_html = _render_run_output(run_result)

    file_tree_html = _render_file_tree(workspace, files, selected_file)
    file_tools_html = _render_file_tools(workspace, selected_file)
    notice_html = f'<section class="notice" role="status">{_escape(notice)}</section>' if notice else ""
    read_error_html = f'<section class="notice error">{_escape(read_error)}</section>' if read_error else ""
    instructions_html = _render_assignment_instructions(workspace.assignment_path)
    workspace_title_html = _render_workspace_title(workspace, notice_html, read_error_html)
    editor_html = ""
    if selected_file and not read_error:
        editor_html = f"""
        <label class="editor-label">
          Editing {_escape(selected_file)}
          <textarea id="workspace-editor" class="code-editor" name="content" form="workspace-save-form" spellcheck="false">{_escape(content)}</textarea>
        </label>
        """
    return _render_page(
        extra_html=f"""
            <section class="workspace-shell">
              {workspace_title_html}
              <div class="workspace-layout">
                <aside class="workspace-pane file-list" aria-label="Workspace files">
                  <h3>Project Explorer</h3>
                  {file_tree_html}
                  {file_tools_html}
                </aside>
                <section class="workspace-pane editor-panel">
                  <div class="pane-title">Editor</div>
                  <div class="workspace-command-bar" role="toolbar" aria-label="Workspace commands">
                    <form id="workspace-save-form" class="command-form" action="/workspace/save" method="post">
                      <input type="hidden" name="owner_key" value="{_escape(workspace.owner_key)}">
                      <input type="hidden" name="assignment_slug" value="{_escape(workspace.assignment_slug)}">
                      <input type="hidden" name="file_path" value="{_escape(selected_file)}">
                      <button type="submit">Save</button>
                    </form>
                    <form id="workspace-run-form" class="workspace-buffer-form command-form" action="/workspace/run" method="post">
                      <input type="hidden" name="owner_key" value="{_escape(workspace.owner_key)}">
                      <input type="hidden" name="assignment_slug" value="{_escape(workspace.assignment_slug)}">
                      <input type="hidden" name="selected_file" value="{_escape(selected_file)}">
                      <input type="hidden" name="file_path" value="{_escape(selected_file)}">
                      <textarea class="workspace-buffer-content" name="content" hidden></textarea>
                      <input id="workspace-run-runner" type="hidden" name="runner" value="{_escape(runner)}">
                      <button type="submit">Run</button>
                    </form>
                    <form id="workspace-grade-form" class="workspace-buffer-form command-form" action="/workspace/grade" method="post">
                      <input type="hidden" name="owner_key" value="{_escape(workspace.owner_key)}">
                      <input type="hidden" name="assignment_slug" value="{_escape(workspace.assignment_slug)}">
                      <input type="hidden" name="selected_file" value="{_escape(selected_file)}">
                      <input type="hidden" name="file_path" value="{_escape(selected_file)}">
                      <textarea id="workspace-grade-content" class="workspace-buffer-content" name="content" hidden></textarea>
                      <button type="submit">Grade</button>
                    </form>
                    <label class="runner-control command-runner">
                      Runner
                      <select id="workspace-runner-select" name="runner" form="workspace-grade-form" required>
                        {_runner_option("local_unsafe", runner, "local_unsafe")}
                        {_runner_option("podman", runner, "podman")}
                      </select>
                    </label>
                  </div>
                  <div class="pane-body">
                    {editor_html}
                  </div>
                </section>
                <aside class="workspace-pane feedback-panel">
                  <div class="pane-title">Feedback</div>
                  <div class="pane-body">
                    {_runner_notice(runner)}
                    <div id="workspace-run-output-region" aria-live="polite">
                      {run_output_html}
                    </div>
                    <div id="workspace-feedback-summary-region" aria-live="polite">
                      {feedback_summary_html}
                    </div>
                  </div>
                </aside>
              </div>
            </section>
            {instructions_html}
            <div id="workspace-activity-region">
              {activity_html}
            </div>
            <div id="workspace-latest-job-region" hidden>{job_panel_html}</div>
            <div id="workspace-latest-result-region" hidden>{latest_panel_html}</div>
            <div id="workspace-attempt-history-region" hidden>{history_html}</div>
            <div id="workspace-job-history-region" hidden>{job_history_html}</div>
            <div id="workspace-diagnostics-region" hidden>{diagnostics_html}</div>
            """
    )


def _render_workspace_title(workspace: Workspace, notice_html: str, read_error_html: str) -> str:
    return f"""
    <header class="workspace-title">
      <div>
        <p class="eyebrow">student workspace</p>
        <h2>{_escape(workspace.assignment_slug)}</h2>
        <p class="muted">{_escape(workspace.owner_key)} · {_escape(workspace.path)}</p>
      </div>
      <div class="workspace-title-status">
        {notice_html}
        {read_error_html}
      </div>
    </header>
    """


def _render_file_tree(workspace: Workspace, files: list[object], selected_file: str) -> str:
    tree: dict[str, object] = {}
    for workspace_file in files:
        node = tree
        parts = workspace_file.path.split("/")
        for folder in parts[:-1]:
            node = node.setdefault(folder, {})
        node[parts[-1]] = workspace_file
    return '<div class="file-tree">' + _render_file_tree_nodes(workspace, tree, selected_file) + "</div>"


def _render_file_tree_nodes(workspace: Workspace, node: dict[str, object], selected_file: str, depth: int = 0) -> str:
    folders = [(name, child) for name, child in sorted(node.items()) if isinstance(child, dict)]
    files = [(name, child) for name, child in sorted(node.items()) if not isinstance(child, dict)]
    rows: list[str] = []

    for folder_name, child in folders:
        child_html = _render_file_tree_nodes(workspace, child, selected_file, depth + 1)
        rows.append(
            f"""
            <details class="tree-folder" open>
              <summary class="tree-row tree-folder-row depth-{depth}">
                <span class="tree-icon folder-icon">dir</span>
                <span>{_escape(folder_name)}</span>
              </summary>
              <div class="tree-children">
                {child_html}
              </div>
            </details>
            """
        )

    for file_name, workspace_file in files:
        is_active = workspace_file.path == selected_file
        extension = Path(workspace_file.path).suffix.lstrip(".")[:3] or "txt"
        rows.append(
            f"""
            <a class="tree-row tree-file-row depth-{depth} {'active' if is_active else ''}" href="{_workspace_url(workspace, workspace_file.path)}">
              <span class="tree-icon file-icon">{_escape(extension)}</span>
              <span>{_escape(file_name)}</span>
            </a>
            """
        )

    return "\n".join(rows)


def _render_run_output(run_result: ProgramRun | None) -> str:
    if run_result is None:
        return """
        <article class="card run-output-card">
          <h2>Run Output</h2>
          <p class="muted">Click Save and Run Program to compile and run the current workspace without creating a graded attempt.</p>
        </article>
        """

    status_text = "Program finished" if run_result.succeeded else "Run needs attention"
    status_class = "pass" if run_result.succeeded else "fail"
    run_returncode = "not run" if run_result.run_returncode is None else str(run_result.run_returncode)
    limited = " · output truncated" if run_result.output_limited else ""
    timeout = " · timed out" if run_result.compile_timed_out or run_result.run_timed_out else ""
    compiler_missing = " · compiler missing" if run_result.compiler_missing else ""
    return f"""
    <article class="card run-output-card">
      <h2>Run Output</h2>
      <div class="run-summary">
        <span class="status-label {status_class}">{_escape(status_text)}</span>
        <p class="muted">Runner: {_escape(run_result.runner)} · Compile exit: {run_result.compile_returncode} · Program exit: {_escape(run_returncode)}{limited}{timeout}{compiler_missing}</p>
      </div>
      {_render_output_panel("Compiler stdout", run_result.compile_stdout or _empty_panel_text("No compiler stdout."), False, "output-block")}
      {_render_output_panel("Compiler stderr", run_result.compile_stderr or _empty_panel_text("No compiler stderr."), bool(run_result.compile_stderr), "output-block output-error")}
      {_render_output_panel("Program stdout", run_result.program_stdout or _empty_panel_text("No program stdout."), bool(run_result.program_stdout), "output-block")}
      {_render_output_panel("Program stderr", run_result.program_stderr or _empty_panel_text("No program stderr."), bool(run_result.program_stderr), "output-block output-error")}
    </article>
    """


def _program_run_payload(run_result: ProgramRun) -> dict[str, object]:
    return {
        "runner": run_result.runner,
        "compile_returncode": run_result.compile_returncode,
        "compile_stdout": run_result.compile_stdout,
        "compile_stderr": run_result.compile_stderr,
        "run_returncode": run_result.run_returncode,
        "program_stdout": run_result.program_stdout,
        "program_stderr": run_result.program_stderr,
        "compile_timed_out": run_result.compile_timed_out,
        "run_timed_out": run_result.run_timed_out,
        "output_limited": run_result.output_limited,
        "compiler_missing": run_result.compiler_missing,
        "compiled": run_result.compiled,
        "succeeded": run_result.succeeded,
    }


def _grading_job_payload(job: GradingJob) -> dict[str, object]:
    return {
        "job_id": job.job_id,
        "status": job.status,
        "owner_key": job.owner_key,
        "assignment_slug": job.assignment_slug,
        "runner": job.runner,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "attempt_id": job.attempt_id,
        "score": job.score,
        "max_score": job.max_score,
        "report_json_path": str(job.report_json_path) if job.report_json_path else None,
        "report_md_path": str(job.report_md_path) if job.report_md_path else None,
        "error": job.error,
    }


def _workspace_grade_fragments(workspace: Workspace) -> dict[str, str]:
    attempt = latest_attempt(workspace)
    result_html = ""
    if attempt:
        report_md_url = f"/workspace/report/{_escape_url(workspace.owner_key)}/{_escape_url(workspace.assignment_slug)}/{_escape_url(attempt.attempt_id)}/report.md"
        report_json_url = f"/workspace/report/{_escape_url(workspace.owner_key)}/{_escape_url(workspace.assignment_slug)}/{_escape_url(attempt.attempt_id)}/report.json"
        result_html = _render_result(
            attempt.result,
            f"{workspace.owner_key}/{workspace.assignment_slug}",
            report_json_url,
            report_md_url,
            runner=attempt.runner,
        )
    fragments = {
        "latest_job_html": _render_latest_job_panel(latest_grading_job(workspace)),
        "latest_result_html": _render_latest_result_panel(workspace, attempt),
        "feedback_summary_html": _render_feedback_summary(workspace, latest_grading_job(workspace), attempt),
        "attempt_history_html": _render_attempt_history(workspace),
        "job_history_html": _render_job_history(workspace),
        "diagnostics_html": _render_latest_diagnostics(result_html),
    }
    fragments["activity_html"] = _render_workspace_activity(
        fragments["attempt_history_html"],
        fragments["job_history_html"],
        fragments["diagnostics_html"],
    )
    return fragments


def _render_attempt_history(workspace: Workspace) -> str:
    attempts = list_attempts(workspace)
    if not attempts:
        return """
        <details class="card attempt-history">
          <summary>Attempt History</summary>
          <p class="muted">No attempts yet. Save and grade the workspace to create the first snapshot.</p>
        </details>
        """

    best_attempt = max(attempts, key=lambda attempt: _attempt_percent(attempt))
    latest_attempt = attempts[0]
    rows = "\n".join(_render_attempt_row(workspace, attempt, is_latest=attempt is latest_attempt) for attempt in attempts)
    return f"""
    <details class="card attempt-history">
      <summary>Attempt History</summary>
      <div class="history-summary">
        <div class="metric">
          <span>Latest</span>
          <strong>{latest_attempt.result.score:g} / {latest_attempt.result.max_score:g}</strong>
        </div>
        <div class="metric">
          <span>Best</span>
          <strong>{best_attempt.result.score:g} / {best_attempt.result.max_score:g}</strong>
        </div>
        <div class="metric">
          <span>Total Attempts</span>
          <strong>{len(attempts)}</strong>
        </div>
      </div>
      <div class="attempt-list">
        {rows}
      </div>
    </details>
    """


def _render_job_history(workspace: Workspace) -> str:
    jobs = list_grading_jobs(workspace)
    if not jobs:
        return """
        <details class="card attempt-history">
          <summary>Grading Jobs</summary>
          <p class="muted">No grading jobs yet. The next Grade click will create one.</p>
        </details>
        """

    rows = "\n".join(_render_job_row(job, is_latest=job is jobs[0]) for job in jobs)
    return f"""
    <details class="card attempt-history">
      <summary>Grading Jobs</summary>
      <div class="attempt-list">
        {rows}
      </div>
    </details>
    """


def _render_job_row(job: GradingJob, is_latest: bool) -> str:
    status_class = "pass" if job.status == "completed" else "fail" if job.status == "failed" else ""
    label = "Latest Job" if is_latest else "Job"
    score_text = f"{job.score:g} / {job.max_score:g}" if job.score is not None and job.max_score is not None else "not scored"
    detail = job.error or (f"Attempt: {_format_attempt_id(job.attempt_id)}" if job.attempt_id else "No attempt recorded yet.")
    return f"""
    <article class="attempt-row">
      <div>
        <span class="status-label {status_class}">{_escape(label)}: {_escape(job.status)}</span>
        <h3>{_escape(_format_attempt_id(job.job_id))}</h3>
        <p class="muted">Runner: {_escape(job.runner)} · {_escape(detail)}</p>
      </div>
      <div class="attempt-score">
        <strong>{_escape(score_text)}</strong>
      </div>
    </article>
    """


def _render_latest_diagnostics(result_html: str) -> str:
    return f"""
    <details class="card diagnostic-tools">
      <summary>Latest Detailed Diagnostics</summary>
      {result_html if result_html else '<p class="muted">No detailed result yet.</p>'}
    </details>
    """


def _render_workspace_activity(attempt_history_html: str, job_history_html: str, diagnostics_html: str) -> str:
    return f"""
    <section class="workspace-activity">
      <div class="section-strip compact-strip">
        <div>
          <h2>Workspace Activity</h2>
          <p class="muted">History and detailed diagnostic output live here so the editor stays primary.</p>
        </div>
      </div>
      <div class="activity-grid">
        {attempt_history_html}
        {job_history_html}
        {diagnostics_html}
      </div>
    </section>
    """


def _render_attempt_row(workspace: Workspace, attempt: Attempt, is_latest: bool) -> str:
    percent = _attempt_percent(attempt)
    status_text = "Passed" if all(check.passed for check in attempt.result.checks) else "Review"
    status_class = "pass" if status_text == "Passed" else "fail"
    flags = ", ".join(attempt.result.flags) if attempt.result.flags else "None"
    label = "Latest" if is_latest else "Attempt"
    report_md_url = f"/workspace/report/{_escape_url(workspace.owner_key)}/{_escape_url(workspace.assignment_slug)}/{_escape_url(attempt.attempt_id)}/report.md"
    report_json_url = f"/workspace/report/{_escape_url(workspace.owner_key)}/{_escape_url(workspace.assignment_slug)}/{_escape_url(attempt.attempt_id)}/report.json"
    return f"""
    <article class="attempt-row">
      <div>
        <span class="status-label {status_class}">{label}: {status_text}</span>
        <h3>{_escape(_format_attempt_id(attempt.attempt_id))}</h3>
        <p class="muted">Runner: {_escape(attempt.runner)} · Flags: {_escape(flags)}</p>
      </div>
      <div class="attempt-score">
        <strong>{attempt.result.score:g} / {attempt.result.max_score:g}</strong>
        <span>{percent:.1f}%</span>
      </div>
      <div class="attempt-links">
        <a href="{_escape(report_md_url)}">report.md</a>
        <a href="{_escape(report_json_url)}">report.json</a>
      </div>
    </article>
    """


def _attempt_percent(attempt: Attempt) -> float:
    if attempt.result.max_score == 0:
        return 0.0
    return attempt.result.score / attempt.result.max_score * 100


def _format_attempt_id(attempt_id: str) -> str:
    if len(attempt_id) >= 16 and "T" in attempt_id:
        date = attempt_id[:8]
        time = attempt_id[9:15]
        return f"{date[:4]}-{date[4:6]}-{date[6:8]} {time[:2]}:{time[2:4]}:{time[4:6]} UTC"
    return attempt_id


def _render_file_tools(workspace: Workspace, selected_file: str) -> str:
    selected_controls = ""
    if selected_file:
        selected_controls = f"""
        <form class="file-tool-form" action="/workspace/file/rename" method="post">
          <input type="hidden" name="owner_key" value="{_escape(workspace.owner_key)}">
          <input type="hidden" name="assignment_slug" value="{_escape(workspace.assignment_slug)}">
          <input type="hidden" name="file_path" value="{_escape(selected_file)}">
          <label>
            Rename selected
            <input name="new_file_path" value="{_escape(selected_file)}" required>
          </label>
          <button type="submit">Rename</button>
        </form>
        <form class="file-tool-form" action="/workspace/file/delete" method="post">
          <input type="hidden" name="owner_key" value="{_escape(workspace.owner_key)}">
          <input type="hidden" name="assignment_slug" value="{_escape(workspace.assignment_slug)}">
          <input type="hidden" name="file_path" value="{_escape(selected_file)}">
          <button class="danger-button" type="submit">Delete Selected</button>
        </form>
        """
    return f"""
    <section class="file-tools" aria-label="Workspace file tools">
      <h3>Files</h3>
      <form class="file-tool-form" action="/workspace/file/create" method="post">
        <input type="hidden" name="owner_key" value="{_escape(workspace.owner_key)}">
        <input type="hidden" name="assignment_slug" value="{_escape(workspace.assignment_slug)}">
        <label>
          New file
          <input name="new_file_path" placeholder="include/helpers.hpp" required>
        </label>
        <button type="submit">Create</button>
      </form>
      {selected_controls}
      {_render_demo_reset_tool(workspace)}
    </section>
    """


def _render_demo_reset_tool(workspace: Workspace) -> str:
    expected = f"reset {workspace.assignment_slug}"
    disabled_note = ""
    disabled_attr = ""
    if not workspace.owner_key.startswith("demo"):
        disabled_note = '<p class="muted">Reset is only available for demo workspaces.</p>'
        disabled_attr = " disabled"
    return f"""
      <details class="demo-reset-tool">
        <summary>Demo reset</summary>
        <p class="muted">Prototype-only: recreate this workspace from starter files and clear attempts/jobs.</p>
        <form class="file-tool-form" action="/workspace/reset-demo" method="post">
          <input type="hidden" name="owner_key" value="{_escape(workspace.owner_key)}">
          <input type="hidden" name="assignment_slug" value="{_escape(workspace.assignment_slug)}">
          <label>
            Type {_escape(expected)}
            <input name="confirmation" placeholder="{_escape(expected)}" required{disabled_attr}>
          </label>
          <button class="danger-button" type="submit"{disabled_attr}>Reset Demo Workspace</button>
        </form>
        {disabled_note}
      </details>
    """


def _render_assignment_instructions(assignment_path: Path) -> str:
    instructions_path = assignment_path / "README.md"
    if not instructions_path.exists():
        return ""
    instructions = instructions_path.read_text(encoding="utf-8").strip()
    if not instructions:
        return ""
    return f"""
    <details class="instructions" aria-labelledby="assignment-instructions-heading">
      <summary id="assignment-instructions-heading">Assignment instructions</summary>
      <pre>{_escape(instructions)}</pre>
    </details>
    """


def _workspace_url(workspace: Workspace, selected_file: str = "") -> str:
    query = {"owner_key": workspace.owner_key, "assignment_slug": workspace.assignment_slug}
    if selected_file:
        query["file"] = selected_file
    return "/workspace?" + urlencode(query)


def _escape_url(value: str) -> str:
    return urlencode({"v": value})[2:]


def _escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
