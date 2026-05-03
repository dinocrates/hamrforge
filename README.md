# HamrForge

HamrForge is an open-source, repo-based autograding project for instructors. Rev 1 is deliberately focused on C++, but the grading core now has a small language-adapter boundary so future languages can be added without rewriting the whole engine.

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
hamrforge grade assignments/byte-class test-cases/bad-bit-order.zip
hamrforge grade assignments/byte-class test-cases/compile-error.zip
hamrforge grade assignments/byte-class test-cases/infinite-loop.zip
hamrforge grade assignments/byte-class test-cases/huge-output.zip
hamrforge grade assignments/byte-class test-cases/missing-files.zip
```

You can also grade an existing folder/workspace:

```bash
hamrforge grade assignments/byte-class data/workspaces/demo-student/byte-class
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

The private web UI can open a student workspace and can still grade one legacy ZIP at a time for instructor testing. Uploads and web reports are written under `data/`.

## Student Workspace Prototype

Create a demo workspace from assignment starter files:

```bash
hamrforge create-workspace assignments/byte-class --owner demo-student
```

This creates:

```text
data/workspaces/demo-student/byte-class/
  .hamrforge/
    workspace.json
  Byte.cpp
  Byte.h
  main.cpp
```

From the web UI, use **Create / Open** to read the assignment instructions, edit files in a syntax-highlighted browser editor, save changes, and grade the current workspace. Workspace grading stores attempt reports and snapshots under `.hamrforge/attempts/`.

## Language Adapter Boundary

HamrForge Core handles assignment parsing, submission unpacking, shared checks, orchestration, reports, batch grading, and web/workspace flow.

Language adapters handle language-specific build, run, test generation, compiler/interpreter configuration, and feedback normalization.

Rev 1 implements only:

```text
LanguageAdapter
  CppAdapter
```

Assignments with `language: cpp` are routed to `CppAdapter`. Other languages return a clear unsupported-language error until their adapters are intentionally added later.

## Runner Backends

HamrForge now routes compile execution through a runner abstraction.

The default backend is `LocalUnsafeRunner`, which invokes the compiler and student executables directly on your machine. This is useful for MVP development, but it is unsafe and not appropriate for real untrusted student submissions.

Assignments can select the current development runner in `assignment.yml`:

```yaml
runner: local_unsafe
```

If `runner` is omitted, HamrForge currently defaults to `local_unsafe`. Unsupported runner names fail clearly.

HamrForge can also run compile and executable commands through the Podman CLI:

```yaml
runner:
  type: podman
  image: hamrforge-cpp-runner
```

The image defaults to `hamrforge-cpp-runner` when omitted. The Podman runner mounts the temporary grading workspace at `/workspace` and applies basic safety flags: no network, memory limit, CPU limit, process limit, read-only root filesystem, dropped capabilities, no-new-privileges, and a non-root user.

You can also override the runner from the CLI for one grading run:

```bash
hamrforge grade assignments/byte-class test-cases/perfect.zip --runner local_unsafe
hamrforge grade assignments/byte-class test-cases/perfect.zip --runner podman
```

Use a custom image with:

```bash
hamrforge grade assignments/byte-class test-cases/perfect.zip --runner podman --runner-image my-cpp-runner
```

Future backends will plug into the same interface:

```text
SandboxRunner
  LocalUnsafeRunner
  DockerCliRunner
  PodmanCliRunner
```

For real classroom or production use, HamrForge should use an OCI-compatible sandbox backend with CPU, memory, process, filesystem, and network limits.

## Installing and Testing Podman

On Ubuntu:

```bash
sudo apt update
sudo apt install podman
podman --version
```

Build or pull an image that contains the C++ toolchain HamrForge expects. The default image name is:

```text
hamrforge-cpp-runner
```

HamrForge includes a minimal C++ runner image definition. From the repository root, build it with:

```bash
podman build -t hamrforge-cpp-runner .
```

Smoke-test the image:

```bash
podman run --rm hamrforge-cpp-runner g++ --version
```

Then smoke-test HamrForge through both current runners:

```bash
hamrforge grade assignments/byte-class test-cases/perfect.zip --runner local_unsafe
hamrforge grade assignments/byte-class test-cases/perfect.zip --runner podman
```

The Podman runner is expected to report clear failures for:

- missing Podman CLI: `Podman CLI not found`
- missing runner image: Podman's image error plus `Podman container exited with status ...`
- nonzero container command: `Podman container exited with status ...`
- timeout: `Podman container timed out after ... seconds`

The runner applies or enforces these limits where the current Podman CLI path supports them:

- no network: `--network none`
- memory limit: `--memory 256m`
- CPU limit: `--cpus 1`
- process limit: `--pids-limit 64`
- timeout: Python subprocess timeout around each compile/run container invocation
- output limit: captured stdout and stderr are each truncated after 65,536 bytes
- read-only root filesystem: `--read-only`, with a writable mounted workspace and `/tmp` tmpfs
- non-root user: `--userns keep-id` and `--user 1000:1000`
- reduced privileges: `--security-opt no-new-privileges` and `--cap-drop ALL`

Manual runner verification checklist:

```bash
hamrforge grade assignments/byte-class test-cases/perfect.zip --runner podman
hamrforge grade assignments/byte-class test-cases/compile-error.zip --runner podman
hamrforge grade assignments/byte-class test-cases/missing-files.zip --runner podman
hamrforge grade assignments/byte-class test-cases/infinite-loop.zip --runner podman
hamrforge grade assignments/byte-class test-cases/huge-output.zip --runner podman
```

The normal automated test suite does not require Podman to be installed. It tests command construction and runner failure handling with fake subprocess calls.

## Run Tests

```bash
pytest
```

## Current Scope

This scaffold implements assignment validation, single-ZIP grading, folder/workspace grading, batch grading, required-file checks, a C++ adapter, local unsafe compile checks, generated C++ expression tests, console I/O checks, a runner abstraction, an initial Podman C++ runner path, a private web UI, and a first student workspace prototype. It does not implement Java/NASM/RISC-V adapters, production-grade sandboxing, accounts, a job queue, or Canvas LTI yet.

## License

HamrForge uses a split license:

- Software code: `AGPL-3.0-or-later`
- Assignment/content library and documentation: `CC-BY-SA-4.0`

Copyright is retained by Stephen Hamrick. See [LICENSE.md](LICENSE.md).

## Console I/O Flexibility

Current `console_io` checks use loose `expected_contains` matching. That keeps prompts, menu wording, spacing, and menu display order flexible. A later version should let instructors choose stricter exact matching or looser pass-any input variants.
