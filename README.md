# HamrForge

HamrForge is an open-source, repo-based C++ autograding project for instructors. The first milestone is deliberately small: a local CLI that can validate an assignment folder before grading features are added.

## Install for Local Development

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Validate an Assignment

```bash
hamrforge validate-assignment assignments/byte-class
```

A valid assignment prints a success message. Invalid assignments print each validation error with a clear path to the missing or malformed field.

## Grade One ZIP Submission

The current MVP grader checks whether required files are present, whether discovered `.cpp` files compile, whether generated expression tests pass, and whether scripted console I/O output contains expected text.

```bash
hamrforge grade assignments/byte-class path/to/submission.zip
```

By default, reports are written under `reports/<submission-name>/`:

```text
reports/<submission-name>/
  report.json
  report.md
```

You can choose a report directory:

```bash
hamrforge grade assignments/byte-class path/to/submission.zip --out reports/test-run
```

Manual ZIP test cases live in `test-cases/`:

```bash
hamrforge grade assignments/byte-class test-cases/perfect.zip
hamrforge grade assignments/byte-class test-cases/bad-addition.zip
hamrforge grade assignments/byte-class test-cases/compile-error.zip
```

## Grade a Batch of ZIP Submissions

```bash
hamrforge batch-grade assignments/byte-class submissions/*.zip --out reports/week5
```

Batch grading writes:

```text
reports/week5/
  grades.csv
  summary.json
  feedback/
    student1.md
    student2.md
```

If one submission cannot be graded, HamrForge records the error and keeps grading the rest.

## Run the Private Web UI

```bash
hamrforge web --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

The first web UI grades one ZIP at a time and writes uploads/reports under `data/`.

## Runner Backends

HamrForge now routes compile execution through a runner abstraction.

The default backend is `LocalUnsafeRunner`, which invokes the compiler directly on your machine. This is useful for MVP development, but it is not appropriate for real untrusted student submissions.

Future backends will plug into the same interface:

```text
SandboxRunner
  LocalUnsafeRunner
  DockerCliRunner
  PodmanCliRunner
```

For real classroom or production use, HamrForge should use an OCI-compatible sandbox backend with CPU, memory, process, filesystem, and network limits.

## Run Tests

```bash
pytest
```

## Current Scope

This scaffold implements assignment validation, single-ZIP grading, batch grading, required-file checks, local unsafe compile checks, generated expression tests, console I/O checks, a runner abstraction, and a private one-ZIP web UI. It does not run C++ in containers, provide accounts, provide a job queue, or integrate with Canvas LTI yet.

## License

HamrForge uses a split license:

- Software code: `AGPL-3.0-or-later`
- Assignment/content library and documentation: `CC-BY-SA-4.0`

Copyright is retained by Stephen Hamrick. See [LICENSE.md](LICENSE.md).

## Console I/O Flexibility

Current `console_io` checks use loose `expected_contains` matching. That keeps prompts, menu wording, spacing, and menu display order flexible. A later version should let instructors choose stricter exact matching or looser pass-any input variants.
