from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse

from hamrforge.grading import GradeError, GradeResult, grade_submission

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

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HamrForge</title>
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
    form {{
      display: grid;
      grid-template-columns: minmax(220px, 1fr) minmax(220px, 1fr) auto;
      gap: 12px;
      align-items: end;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--line);
    }}
    label {{ display: grid; gap: 6px; font-weight: 650; }}
    input {{
      width: 100%;
      min-height: 40px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      font: inherit;
    }}
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
    .error {{ border-color: #efb0b0; background: #fff7f7; }}
    pre {{
      margin: 8px 0 0;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      font-size: 13px;
    }}
    .links {{ display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap; }}
    a {{ color: var(--accent); font-weight: 650; }}
    @media (max-width: 760px) {{
      form {{ grid-template-columns: 1fr; }}
      button {{ width: 100%; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>HamrForge</h1>
  </header>
  <main>
    <form action="/grade" method="post" enctype="multipart/form-data">
      <label>
        Assignment folder
        <input name="assignment" value="{_escape(assignment)}" required>
      </label>
      <label>
        Submission ZIP
        <input name="submission" type="file" accept=".zip" required>
      </label>
      <button type="submit">Grade</button>
    </form>
    {result_html}
  </main>
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


def _escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
