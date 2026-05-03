from __future__ import annotations

import shutil
import time
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from hamrforge.grading import GradeError, grade_submission
from hamrforge.models import GradeResult
from hamrforge.runner import create_runner
from hamrforge.workspace import (
    Workspace,
    WorkspaceError,
    create_workspace,
    create_workspace_file,
    delete_workspace_file,
    grade_workspace,
    latest_attempt,
    list_attempts,
    list_workspace_files,
    load_workspace,
    read_workspace_file,
    rename_workspace_file,
    write_workspace_file,
)

app = FastAPI(title="HamrForge")

STATIC_DIR = Path(__file__).parent / "static"
DATA_DIR = Path("data")
UPLOADS_DIR = DATA_DIR / "uploads"
WEB_REPORTS_DIR = DATA_DIR / "reports"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(_render_page())


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
        grade_workspace(workspace, runner=selected_runner, runner_name=runner)
        return HTMLResponse(
            _render_workspace_page(
                workspace,
                selected_file=selected_file,
                notice="Workspace saved and graded.",
                runner=runner,
            )
        )
    except (WorkspaceError, GradeError, ValueError) as exc:
        return HTMLResponse(_render_page(error=str(exc)), status_code=400)


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


def _render_page(
    assignment: str = "assignments/byte-class",
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
    <section class="band card">
      <h2>Student workspace</h2>
      <form class="inline-grid" action="/workspace/create" method="post">
        <label>
          Assignment folder
          <input name="assignment" value="{_escape(assignment)}" required>
        </label>
        <label>
          Owner key
          <input name="owner_key" value="demo-student" required>
        </label>
        <button type="submit">Create / Open</button>
      </form>
    </section>
    <section class="band card">
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
    {result_html}
  </main>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/clike/clike.min.js"></script>
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
    }}
    const gradeForm = document.getElementById("workspace-grade-form");
    const gradeContent = document.getElementById("workspace-grade-content");
    if (gradeForm && gradeContent && editorTextarea) {{
      gradeForm.addEventListener("submit", () => {{
        if (workspaceEditor) {{
          gradeContent.value = workspaceEditor.getValue();
        }} else {{
          gradeContent.value = editorTextarea.value;
        }}
      }});
    }}
  </script>
</body>
</html>"""


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
    history_html = _render_attempt_history(workspace)

    file_links = "\n".join(
        f'<a class="{"active" if file.path == selected_file else ""}" href="{_workspace_url(workspace, file.path)}">{_escape(file.path)}</a>'
        for file in files
    )
    file_tools_html = _render_file_tools(workspace, selected_file)
    notice_html = f'<section class="notice" role="status">{_escape(notice)}</section>' if notice else ""
    read_error_html = f'<section class="notice error">{_escape(read_error)}</section>' if read_error else ""
    instructions_html = _render_assignment_instructions(workspace.assignment_path)
    editor_html = ""
    if selected_file and not read_error:
        editor_html = f"""
        <form class="stack" action="/workspace/save" method="post">
          <input type="hidden" name="owner_key" value="{_escape(workspace.owner_key)}">
          <input type="hidden" name="assignment_slug" value="{_escape(workspace.assignment_slug)}">
          <input type="hidden" name="file_path" value="{_escape(selected_file)}">
          <label>
            Editing {_escape(selected_file)}
            <textarea id="workspace-editor" class="code-editor" name="content" spellcheck="false">{_escape(content)}</textarea>
          </label>
          <div class="actions">
            <button type="submit">Save File</button>
          </div>
        </form>
        """
    return _render_page(
        extra_html=f"""
            <section class="band">
              <h2>Workspace: {_escape(workspace.owner_key)} / {_escape(workspace.assignment_slug)}</h2>
              <p class="muted">Path: {_escape(workspace.path)}</p>
              {notice_html}
              {read_error_html}
              {instructions_html}
              <div class="workspace-layout">
                <nav class="file-list" aria-label="Workspace files">
                  {file_links}
                  {file_tools_html}
                </nav>
                <div>
                  {editor_html}
                  <form id="workspace-grade-form" action="/workspace/grade" method="post">
                    <input type="hidden" name="owner_key" value="{_escape(workspace.owner_key)}">
                    <input type="hidden" name="assignment_slug" value="{_escape(workspace.assignment_slug)}">
                    <input type="hidden" name="selected_file" value="{_escape(selected_file)}">
                    <input type="hidden" name="file_path" value="{_escape(selected_file)}">
                    <textarea id="workspace-grade-content" name="content" hidden></textarea>
                    <label class="runner-control">
                      Runner
                      <select name="runner" required>
                        {_runner_option("local_unsafe", runner, "local_unsafe")}
                        {_runner_option("podman", runner, "podman")}
                      </select>
                    </label>
                    {_runner_notice(runner)}
                    <div class="actions">
                      <button type="submit">Save and Grade Workspace</button>
                    </div>
                  </form>
                </div>
              </div>
            </section>
            {history_html}
            {result_html}
            """
    )


def _render_attempt_history(workspace: Workspace) -> str:
    attempts = list_attempts(workspace)
    if not attempts:
        return """
        <section class="card attempt-history">
          <h2>Attempt History</h2>
          <p class="muted">No attempts yet. Save and grade the workspace to create the first snapshot.</p>
        </section>
        """

    best_attempt = max(attempts, key=lambda attempt: _attempt_percent(attempt))
    latest_attempt = attempts[0]
    rows = "\n".join(_render_attempt_row(workspace, attempt, is_latest=attempt is latest_attempt) for attempt in attempts)
    return f"""
    <section class="card attempt-history">
      <h2>Attempt History</h2>
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
          <input name="new_file_path" placeholder="helpers.cpp" required>
        </label>
        <button type="submit">Create</button>
      </form>
      {selected_controls}
    </section>
    """


def _render_assignment_instructions(assignment_path: Path) -> str:
    instructions_path = assignment_path / "README.md"
    if not instructions_path.exists():
        return ""
    instructions = instructions_path.read_text(encoding="utf-8").strip()
    if not instructions:
        return ""
    return f"""
    <article class="instructions" aria-labelledby="assignment-instructions-heading">
      <h3 id="assignment-instructions-heading">Assignment instructions</h3>
      <pre>{_escape(instructions)}</pre>
    </article>
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
