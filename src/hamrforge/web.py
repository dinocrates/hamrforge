from __future__ import annotations

import shutil
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from hamrforge.grading import GradeError, grade_submission
from hamrforge.models import GradeResult
from hamrforge.workspace import (
    Workspace,
    WorkspaceError,
    create_workspace,
    grade_workspace,
    latest_attempt,
    list_workspace_files,
    load_workspace,
    read_workspace_file,
    write_workspace_file,
)

app = FastAPI(title="HamrForge")

DATA_DIR = Path("data")
UPLOADS_DIR = DATA_DIR / "uploads"
WEB_REPORTS_DIR = DATA_DIR / "reports"


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(_render_page())


@app.post("/grade", response_class=HTMLResponse)
def grade_upload(
    request: Request,
    assignment: str = Form("assignments/byte-class"),
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
        result = grade_submission(Path(assignment), upload_path, report_dir)
    except GradeError as exc:
        return HTMLResponse(_render_page(error=str(exc), assignment=assignment), status_code=400)

    report_json_url = str(request.url_for("download_report", request_id=request_id, filename="report.json"))
    report_md_url = str(request.url_for("download_report", request_id=request_id, filename="report.md"))
    return HTMLResponse(
        _render_page(
            assignment=assignment,
            result=result,
            uploaded_filename=safe_filename,
            report_json_url=report_json_url,
            report_md_url=report_md_url,
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


@app.post("/workspace/grade", response_class=HTMLResponse)
def workspace_grade(
    owner_key: str = Form(...),
    assignment_slug: str = Form(...),
    selected_file: str = Form(""),
) -> HTMLResponse:
    try:
        workspace = load_workspace(owner_key, assignment_slug)
        grade_workspace(workspace)
        return HTMLResponse(_render_workspace_page(workspace, selected_file=selected_file, notice="Workspace graded."))
    except (WorkspaceError, GradeError) as exc:
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
    result: GradeResult | None = None,
    uploaded_filename: str = "",
    error: str = "",
    report_json_url: str = "",
    report_md_url: str = "",
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
        result_html = _render_result(result, uploaded_filename, report_json_url, report_md_url)
    elif extra_html:
        result_html = extra_html

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HamrForge</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css">
  <style>
    :root {{
      color-scheme: light;
      --ink: #1f2933;
      --muted: #52616b;
      --line: #d9e2ec;
      --surface: #f7f9fb;
      --pass: #176f48;
      --fail: #a61b1b;
      --accent: #0b5cad;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: white;
    }}
    header {{
      padding: 24px clamp(16px, 4vw, 48px);
      border-bottom: 1px solid var(--line);
      background: var(--surface);
    }}
    h1 {{ margin: 0; font-size: 28px; letter-spacing: 0; }}
    main {{
      width: min(1040px, 100%);
      padding: 24px clamp(16px, 4vw, 48px) 48px;
    }}
    form.inline-grid {{
      display: grid;
      grid-template-columns: minmax(220px, 1fr) minmax(220px, 1fr) auto;
      gap: 12px;
      align-items: end;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--line);
    }}
    form.stack {{ display: grid; gap: 12px; }}
    label {{ display: grid; gap: 6px; font-weight: 650; }}
    input, textarea {{
      width: 100%;
      min-height: 40px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      font: inherit;
    }}
    textarea {{
      min-height: 420px;
      font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
      font-size: 14px;
      line-height: 1.45;
    }}
    .CodeMirror {{
      min-height: 420px;
      border: 1px solid var(--line);
      border-radius: 6px;
      font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
      font-size: 14px;
      line-height: 1.45;
    }}
    .CodeMirror-scroll {{ min-height: 420px; }}
    button {{
      min-height: 40px;
      border: 0;
      border-radius: 6px;
      padding: 0 16px;
      background: var(--accent);
      color: white;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 16px;
      border: 1px solid var(--line);
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{ background: var(--surface); }}
    .score {{ margin-top: 24px; font-size: 22px; font-weight: 750; }}
    .muted {{ color: var(--muted); }}
    .pass {{ color: var(--pass); font-weight: 750; }}
    .fail {{ color: var(--fail); font-weight: 750; }}
    .notice {{
      margin-top: 24px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface);
    }}
    .instructions {{
      margin-top: 16px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fbfcfd;
    }}
    .instructions h3 {{ margin: 0 0 10px; font-size: 18px; }}
    .instructions pre {{
      margin: 0;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      font-family: inherit;
      font-size: 14px;
      line-height: 1.5;
    }}
    .error {{ border-color: #efb0b0; background: #fff7f7; }}
    pre {{
      margin: 8px 0 0;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      font-size: 13px;
    }}
    .links {{ display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap; }}
    a {{ color: var(--accent); font-weight: 650; }}
    .band {{
      padding: 24px 0;
      border-bottom: 1px solid var(--line);
    }}
    .workspace-layout {{
      display: grid;
      grid-template-columns: 220px minmax(0, 1fr);
      gap: 20px;
      align-items: start;
      margin-top: 16px;
    }}
    .file-list {{
      display: grid;
      gap: 4px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px;
    }}
    .file-list a {{
      display: block;
      padding: 7px 8px;
      border-radius: 4px;
      text-decoration: none;
    }}
    .file-list a.active {{ background: var(--surface); }}
    .actions {{ display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; }}
    @media (max-width: 760px) {{
      form.inline-grid, .workspace-layout {{ grid-template-columns: 1fr; }}
      button {{ width: 100%; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>HamrForge</h1>
  </header>
  <main>
    <section class="band">
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
    <section class="band">
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
        <button type="submit">Grade ZIP</button>
      </form>
    </section>
    {result_html}
  </main>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/clike/clike.min.js"></script>
  <script>
    const editorTextarea = document.getElementById("workspace-editor");
    if (editorTextarea && window.CodeMirror) {{
      const editor = CodeMirror.fromTextArea(editorTextarea, {{
        mode: "text/x-c++src",
        lineNumbers: true,
        indentUnit: 4,
        tabSize: 4,
        viewportMargin: Infinity
      }});
      const editorForm = editorTextarea.closest("form");
      if (editorForm) {{
        editorForm.addEventListener("submit", () => editor.save());
      }}
    }}
  </script>
</body>
</html>"""


def _render_result(result: GradeResult, uploaded_filename: str, report_json_url: str, report_md_url: str) -> str:
    rows = "\n".join(_render_check_row(check) for check in result.checks)
    flags = ", ".join(result.flags) if result.flags else "None"
    return f"""
    <section>
      <div class="score">Score: {result.score:g} / {result.max_score:g}</div>
      <p class="muted">Submission: {_escape(uploaded_filename)} · Flags: {_escape(flags)}</p>
      <table>
        <thead>
          <tr>
            <th>Check</th>
            <th>Status</th>
            <th>Score</th>
            <th>Feedback</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
      <div class="links">
        <a href="{_escape(report_md_url)}">Markdown report</a>
        <a href="{_escape(report_json_url)}">JSON report</a>
      </div>
    </section>
    """


def _render_check_row(check: object) -> str:
    status_text = "Passed" if check.passed else "Failed"
    status_class = "pass" if check.passed else "fail"
    detail = f"<pre>{_escape(check.detail)}</pre>" if check.detail and not check.passed else ""
    return f"""
    <tr>
      <td>{_escape(check.name)}</td>
      <td class="{status_class}">{status_text}</td>
      <td>{check.score:g} / {check.max_score:g}</td>
      <td>{_escape(check.feedback)}{detail}</td>
    </tr>
    """


def _render_workspace_page(workspace: Workspace, selected_file: str = "", notice: str = "") -> str:
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
        result_html = _render_result(attempt.result, f"{workspace.owner_key}/{workspace.assignment_slug}", report_json_url, report_md_url)

    file_links = "\n".join(
        f'<a class="{"active" if file.path == selected_file else ""}" href="{_workspace_url(workspace, file.path)}">{_escape(file.path)}</a>'
        for file in files
    )
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
                </nav>
                <div>
                  {editor_html}
                  <form action="/workspace/grade" method="post">
                    <input type="hidden" name="owner_key" value="{_escape(workspace.owner_key)}">
                    <input type="hidden" name="assignment_slug" value="{_escape(workspace.assignment_slug)}">
                    <input type="hidden" name="selected_file" value="{_escape(selected_file)}">
                    <div class="actions">
                      <button type="submit">Grade Workspace</button>
                    </div>
                  </form>
                </div>
              </div>
            </section>
            {result_html}
            """
    )


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
