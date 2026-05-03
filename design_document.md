# HamrForge Design Document

## Working Title

**HamrForge**

## Project Vision

HamrForge is an open-source, repo-based student coding workspace and autograding system designed for instructors who want the usefulness of commercial platforms like ZyBooks or zyLabs without vendor lock-in, opaque assignment design, difficult test authoring, or heavy student setup requirements. Rev 1 focuses on C++ through the first implemented language adapter.

The project begins with a local/home-server grading engine and scaffolds upward toward the real product goal: a student-facing, server-hosted assignment workspace system that can eventually launch from Canvas through LTI.

Instructor ZIP and batch grading are useful early utilities and compatibility paths. They help test the engine, support legacy submissions, and give instructors a fallback workflow. They are not the final center of the product.

The core promise:

> An instructor can create or fork an assignment repo, define simple tests without becoming a testing-framework or DevOps expert, let students work in server-side assignment workspaces, grade that work safely, generate useful feedback, and eventually pass scores back to Canvas.

This project is not intended to be a commercial courseware clone. It is intended to become an OER-friendly infrastructure layer for computer science and engineering education.

---

# 1. Guiding Principles

## 1.1 Repo-first

Every assignment should live in a plain folder or Git repository.

This keeps assignments:

- version-controlled
- remixable
- inspectable
- forkable
- shareable as OER
- portable across systems
- independent of a vendor database

Example assignment structure:

```text
assignment-byte-class/
  README.md
  assignment.yml
  rubric.yml
  starter/
    main.cpp
    Byte.h
    Byte.cpp
  tests/
    public.yml
    hidden.yml
  solution/
    Byte.h
    Byte.cpp
    main.cpp
  fixtures/
    perfect/
    compile-error/
    missing-files/
    bad-bit-order/
```

## 1.2 Teacher-friendly test authoring

The instructor should not need to write raw Catch2, CMake, Docker, or LTI code.

Teachers should be able to express test intent in simple YAML.

Example:

```yaml
checks:
  - name: Byte constructor stores value
    type: expression_test
    points: 10
    include:
      - Byte.h
    setup: |
      Byte b(13);
    expect:
      expression: b.toInt()
      equals: 13

  - name: Byte addition works
    type: expression_test
    points: 10
    include:
      - Byte.h
    setup: |
      Byte a(5);
      Byte b(7);
      Byte c = a + b;
    expect:
      expression: c.toInt()
      equals: 12
```

HamrForge generates the underlying C++ unit tests.

## 1.3 The tool should generate useful feedback

HamrForge should not only say:

```text
Test failed.
```

It should aim for feedback like:

```text
setValue/toInt failed for value 99.
Expected: 99
Actual: 198
Likely issue: your bit order may be reversed when storing or converting bits.
```

Feedback quality is part of the product, not an afterthought.

## 1.4 Use existing infrastructure where possible

HamrForge should not reinvent:

- C++ testing frameworks
- containerization
- LMS standards
- web authentication patterns
- queue systems

Instead, it should wrap existing tools in an instructor-friendly workflow.

Likely starting technologies:

- Python
- FastAPI
- YAML
- Catch2 or doctest
- Docker
- PostgreSQL later
- Redis + Celery/RQ later
- LTI 1.3 / LTI Advantage later

## 1.5 Build in stages

The project must be useful before it becomes ambitious.

The staged path is:

```text
Local CLI grading engine
→ folder/workspace grading
→ starter workspace creation
→ basic student workspace web UI
→ sandboxed runner
→ job queue
→ instructor batch/legacy ZIP utilities
→ Canvas LTI launch
→ grade passback
→ district-hosted solution
```

The CLI ZIP grader can come first because it is the smallest way to prove the grading engine. That does not make ZIP upload the primary long-term product model.

---

# 2. Scope

## 2.1 Initial scope

The first version should support:

- C++17 grading through the first implemented language adapter
- a simple language-adapter boundary so the core is not hard-coded to C++
- assignment repo format
- required file checks
- compile checks
- generated unit tests
- console I/O checks
- Markdown feedback reports
- JSON grading reports
- single-submission ZIP grading as an instructor/testing utility
- folder/workspace grading as the bridge to student-facing use
- basic private web UI for grading and inspecting results
- local or private-server use

## 2.2 Later scope

Later versions may support:

- additional language adapters
- Canvas LTI launch
- Canvas grade passback
- Deep Linking assignment selection
- instructor dashboards
- student attempt history
- server-side student workspaces/repos
- basic browser file editor
- reusable OER assignment library
- GitHub Classroom-style workflows
- richer browser-based coding environment
- instructor batch grading of legacy uploaded ZIP submissions
- plagiarism/similarity checks
- AI-assisted feedback drafting

## 2.3 Explicit non-goals for early versions

Do not build these first:

- full LMS replacement
- full browser IDE
- commercial-style courseware marketplace
- implemented multi-language support beyond C++
- district deployment
- Canvas LTI
- roster sync
- analytics dashboards
- AI grading
- plagiarism detection

The first useful tool is:

> assignment repo + grading engine → score reports and feedback

The first student-facing version is:

> assignment repo + starter files → server-side student workspace → grade current workspace → feedback report

The primary product model is:

```text
assignment repo
→ starter files
→ student workspace
→ attempt snapshot
→ grading result
→ feedback
```

ZIP submissions remain supported as a compatibility input source, not as the main student-facing workflow.

## 2.4 Language Adapter Architecture

HamrForge Core should not be hard-coded as a C++-only grader. From the beginning, the architecture should use a language-adapter model: the core owns the grading workflow, and a selected `LanguageAdapter` owns language-specific build, run, and test behavior.

This is an architecture decision, not a Rev 1 scope expansion. Rev 1 ships with only one implemented adapter: C++. Java, NASM, and RISC-V are planned future adapters and should not be implemented in Rev 1.

The reason for this boundary is practical: instructors should eventually be able to use the same HamrForge workflow for different teaching contexts without rewriting the core grading engine. But the first useful product is still a working C++ grader.

### Conceptual flow

```text
assignment.yml
→ workspace snapshot or legacy submission files
→ HamrForge Core
→ selected LanguageAdapter
→ sandbox runner
→ build/run/check results
→ report
```

### HamrForge Core responsibilities

HamrForge Core should handle:

- `assignment.yml` parsing
- submission unpacking
- required file checks when language-neutral
- check orchestration
- report generation
- batch grading for instructor/legacy workflows
- sandbox runner selection
- later web/LTI integration

### Language adapter responsibilities

Language adapters should handle:

- language-specific build steps
- language-specific run steps
- language-specific test generation
- language-specific check types
- language-specific compiler/interpreter/simulator configuration
- language-specific feedback normalization

### Rev 1 Implemented Adapter: C++

C++ is the only language adapter implemented for Rev 1.

The Rev 1 `CppAdapter` should support:

- required file checks
- compile checks
- console I/O checks
- compatibility with instructor batch grading orchestration
- Markdown and JSON reports
- eventual generated Catch2 or doctest tests
- Linux grading runtime, even when developed from Windows/WSL

Rev 1 may have a simple adapter boundary. It does not need a sophisticated plugin system. The important thing is that `language: cpp` routes to the C++ adapter and unsupported languages fail clearly.

### Planned Future Adapters

Future adapters can be added without rewriting the core grading engine.

`JavaAdapter` may support:

- `javac` compile checks
- console I/O checks
- eventual JUnit tests

`NasmAdapter` may support:

- Linux x86-64 NASM first
- `.asm` and `.inc` support
- assemble checks
- link checks
- console I/O checks
- symbol checks
- instruction-pattern checks
- possible later function-level testing through known labels/functions and generated harnesses

`RiscVAdapter` may support:

- RARS simulator mode first for introductory teaching
- possible later QEMU/toolchain mode
- console I/O checks
- instruction-pattern checks
- simulator/toolchain-specific reports

### Shared vs. Adapter-Specific Checks

Shared/core checks may include:

- `file_check`
- `code_pattern` where language-neutral
- `console_io` where executable output is available
- `timeout`
- `output_contains` / `output_matches`
- `manual_flag`

C++ adapter checks may include:

- `compile`
- `expression_test`
- `catch2_test`
- `doctest_test`

Java adapter checks may include:

- `javac_compile`
- `junit_test`

NASM adapter checks may include:

- `assemble`
- `link`
- `symbol_check`
- `instruction_pattern`

RISC-V adapter checks may include:

- `rars_assemble`
- `rars_run`
- `riscv_instruction_pattern`

### Rev 1 Scope Guardrails

- Rev 1 implements only C++.
- The adapter architecture should exist, but only `CppAdapter` needs to be functional.
- Do not implement Java in Rev 1.
- Do not implement NASM in Rev 1.
- Do not implement RISC-V in Rev 1.
- Do not build a plugin marketplace in Rev 1.
- Do not delay the C++ MVP by over-engineering the adapter system.
- The goal is a working C++ grader with a clean path for future adapters.

---

# 3. Student Workspace Model

HamrForge's primary student-facing model is an assignment workspace, not a ZIP upload form.

Each assignment repo should provide starter files. When a student opens or launches an assignment, HamrForge creates or opens that student's private workspace for that assignment. In the early home-server version, a workspace can be a managed server folder under local storage. Later, the workspace may become Git-backed or otherwise versioned so student work can be tracked, restored, and moved more easily.

Students should eventually be able to:

- launch or open an assignment
- receive starter files in a server-side workspace
- edit project files in HamrForge
- click Run or Grade
- receive pass/fail feedback and useful details
- revise and try again multiple times

Grading should operate on a snapshot of the workspace, not directly on a mutable folder that may change while grading is running. This keeps each grading result tied to the exact source state that produced it.

The core workflow is:

```text
assignment repo
→ starter files
→ student workspace
→ attempt snapshot
→ grading result
→ feedback
```

ZIP and batch grading should remain available for early development, legacy submissions, and instructor-only workflows. They should not drive the main web product design.

## 3.1 Submission vs. Attempt vs. Workspace

`workspace`:
The current editable project folder for one student and one assignment. It contains the files the student sees and edits.

`attempt`:
A graded point-in-time snapshot of a workspace or uploaded ZIP. Attempts preserve what was graded, when it was graded, and what result was produced.

`submission`:
A compatibility input source for the grader. A submission may be an uploaded ZIP or a workspace snapshot. In the student-facing product, workspace snapshots should become the normal submission source.

## 3.2 Workspace Lifecycle

```text
Assignment published
→ student workspace created from starter files
→ student edits files
→ student clicks Grade
→ HamrForge creates attempt snapshot
→ grading worker grades the snapshot
→ feedback is stored and shown
→ best/latest score can later pass back to Canvas
```

For early prototypes, "student" may mean a demo `owner_key`, and "worker" may mean the same process running locally. The lifecycle should still be modeled this way so the project can grow into queues, sandboxes, accounts, and Canvas without changing the product concept.

---

# 4. Cross-Platform Strategy: Windows Development, Linux Runtime

## 4.1 The situation

The instructor/developer may run the project at home on Windows, but the eventual backend should be Linux-based.

This is not a blocker, but it must shape the architecture.

## 4.2 Design decision

HamrForge should be cross-platform at the orchestration layer, but Linux-based at the grading/runtime layer.

In practice:

```text
Windows host
  → runs project code, web app, or CLI
  → uses Docker Desktop / WSL2
  → launches Linux grading containers

Linux production server
  → runs the same backend services directly through Docker/Compose
  → uses the same Linux grading containers
```

The grading environment should be treated as Linux-canonical.

## 4.3 Why this works

C++ student code should be compiled and tested inside a Linux container regardless of whether the developer host is Windows or Linux.

That means the same assignment should behave consistently on:

- Windows + Docker Desktop + WSL2
- Linux server + Docker Engine
- future district-hosted Linux infrastructure

## 4.4 Coding rules for cross-platform sanity

The application code should follow these rules:

### Use `pathlib`, not string paths

Use:

```python
from pathlib import Path
assignment_dir = Path(args.assignment).resolve()
```

Avoid:

```python
assignment_dir = args.assignment + "\\tests\\public.yml"
```

### Never hardcode Windows paths

Avoid:

```text
C:\Users\Stephen\Desktop\submissions
```

Use configuration:

```yaml
storage:
  submissions_dir: ./data/submissions
  reports_dir: ./data/reports
```

### Normalize ZIP extraction

Student ZIP files may contain:

- nested folders
- Windows paths
- macOS metadata
- Visual Studio junk
- build outputs
- spaces in filenames
- odd capitalization

The submission parser should normalize and report what it finds.

ZIP normalization remains important for legacy and instructor workflows. Student-facing workspace grading should normally avoid ZIP upload entirely by grading attempt snapshots.

### Treat containers as the only place student code executes

The host operating system should not matter because student code should run only inside grading containers.

### Keep line endings flexible

Student submissions may use CRLF or LF. Tests and output comparison should normalize line endings unless exact output is explicitly required.

### Avoid shell-specific assumptions

The Python backend should invoke subprocesses using lists, not shell strings.

Use:

```python
subprocess.run(["g++", "-std=c++17", "main.cpp", "-o", "program"])
```

Avoid:

```python
subprocess.run("g++ -std=c++17 main.cpp -o program", shell=True)
```

### Keep grading commands inside Linux containers

The host should not need `g++` installed. The grading image should contain:

- g++
- make/cmake if needed
- Catch2/doctest headers
- Python runner scripts if needed
- timeout utilities

## 4.5 Development recommendation

For Windows home development:

- Use Docker Desktop with WSL2 backend.
- Use VS Code with WSL extension if desired.
- Store the repo either in WSL’s Linux filesystem for best performance or in a clean Windows project folder if performance is acceptable.
- Use Docker Compose so the same service definitions can later run on Linux.

---

# 5. System Evolution

## 5.1 Version 0: Local CLI Grading Engine

### Goal

Create a command-line tool that proves the grading engine against one assignment repo and one input source.

This version may grade ZIP files first because ZIPs are easy to test from the terminal. That is an engine-testing convenience, not the final product model.

### Example command

```bash
hamrforge grade assignments/byte-class submissions/student.zip
```

### Output

```text
Score: 82 / 100

✓ Required files found
✓ Compiles with C++17
✓ Constructor stores value
✗ Addition edge case failed

Reports saved:
- report.json
- report.md
```

### Features

- load `assignment.yml`
- validate assignment config
- route `language: cpp` to the C++ language adapter
- return a clear unsupported-language error for any non-C++ Rev 1 assignment
- unzip student submission
- ignore common junk folders
- find source files
- check required files
- compile C++ code through `CppAdapter`
- run basic C++ tests through `CppAdapter`
- generate JSON and Markdown reports

### No web app yet

This version should not include:

- user accounts
- database
- LTI
- Canvas
- public server
- student-facing interface

### Success criteria

HamrForge can grade at least ten fake fixture submissions and produce expected scores.

---

## 5.2 Version 1: Folder and Workspace Grader

### Goal

Allow HamrForge to grade either a ZIP submission or an already-existing folder/workspace.

This is the bridge from instructor-uploaded ZIP files to student-facing server-side work.

### Example command

```bash
hamrforge grade assignments/byte-class data/workspaces/demo-student/byte-class
```

### Output

```text
data/workspaces/demo-student/byte-class/
  main.cpp
  Byte.h
  Byte.cpp

reports/demo-student-byte-class/
  report.json
  report.md
```

### Features

- grade a ZIP file or a directory using the same grading engine
- avoid assuming submissions always arrive as archives
- preserve the current safe ZIP unpacking path for instructor/testing workflows
- make workspace paths explicit and reportable
- prepare for server-side student assignment folders

### Success criteria

HamrForge can grade a checked-out or copied student workspace folder without first creating a ZIP.

---

## 5.3 Version 2: Starter Workspace Prototype

### Goal

Create a student workspace from an assignment's `starter/` files.

### Basic model

```text
Assignment repo
  → starter files
  → data/workspaces/demo-student/byte-class/
  → grade workspace
  → feedback report
```

### Features

- add starter files to sample assignments
- create a workspace for a demo student or local test user
- list workspace files
- prevent writes outside the workspace root
- grade the workspace folder

### Success criteria

The private web app can create a demo workspace from `assignments/byte-class/starter/`, then grade that workspace.

---

## 5.4 Version 3: Basic Student Workspace Web App

### Goal

Run HamrForge as a private web app where a student can edit starter files and grade the current workspace.

### Intended user

One local/demo student identity at first. Real accounts and Canvas identities come later.

### Workflow

```text
Student opens HamrForge web app
→ selects or launches an assignment
→ edits files in a server-side workspace
→ saves changes
→ clicks Grade
→ sees score and feedback
```

### Features

- assignment discovery from local assignment folders
- demo student workspace creation
- simple browser file list
- simple browser editor with lightweight syntax highlighting for starter/source files
- save file changes
- grade current workspace
- display feedback

### Not yet

- full IDE
- terminal access
- advanced editor tooling such as autocomplete, debugging, or project-wide search
- accounts
- collaboration
- Canvas/LTI identity

### Success criteria

A user can complete a small assignment loop through the browser without uploading a ZIP:

```text
create workspace → edit code → save → grade → read feedback
```

---

## 5.5 Version 4: Containerized Workspace Grader

### Goal

Move compilation and execution into containers.

### Why

Student code should not run directly on the host machine.

### Basic execution model

```text
CLI tool
  → prepares attempt snapshot
  → launches Linux grading container
  → container compiles/runs tests
  → container emits results
  → CLI collects reports
```

### Container restrictions

The grading container should eventually use:

- no network
- memory limits
- CPU limits
- process limits
- output limits
- non-root user
- read-only filesystem where possible
- temporary writable workspace
- automatic cleanup

### Success criteria

Bad submissions cannot hang or damage the host system.

Test fixtures should include:

- infinite loop
- huge memory allocation
- huge output loop
- compile error
- missing files
- forbidden include
- wrong file type

### Runner Verification Checkpoint

Before adding more grading features on top of the container runner, HamrForge needs a focused runner verification checkpoint.

The checkpoint should prove that:

- perfect submissions still grade correctly through the local unsafe runner and the Podman runner
- compile-error submissions produce clear compile feedback
- infinite-loop submissions time out instead of hanging the grader
- huge-output submissions have captured output limited
- missing-file submissions still report required-file failures clearly
- Podman command construction is covered by automated tests without requiring Podman in CI
- manual Podman smoke tests are documented for a developer or instructor running HamrForge locally

The current Podman runner should apply or document these limits where supported:

- no network
- memory limit
- CPU limit
- process limit
- timeout
- captured output limit
- non-root user
- host user namespace mapping where needed for writable workspaces
- read-only root filesystem where practical
- dropped capabilities and no-new-privileges where practical

This checkpoint is still not the final production sandbox. It is the MVP proof that grading commands flow through the sandbox boundary and that the next grading features can target the runner interface instead of the host.

---

## 5.6 Version 5: Job Queue and Worker Architecture

### Goal

Separate the web app from the grading worker.

### Why

Grading can be slow, dangerous, and resource intensive. A student clicking Grade should create a job and receive status updates while a worker grades an attempt snapshot.

### Architecture

```text
Web App
  → saves workspace changes
  → creates attempt snapshot
  → creates grading job
  → returns job status

Queue
  → holds pending grading jobs

Worker
  → pulls job
  → launches sandbox
  → grades snapshot
  → stores result and report
```

### Success criteria

Multiple student grading attempts can be queued and processed without freezing the web app.

---

## 5.7 Version 6: Private Instructor Utilities

### Goal

Add instructor-only workflows to the private web app.

### Intended user

The instructor only.

### Workflow

```text
Instructor opens HamrForge web app
→ selects assignment
→ uploads one or many legacy ZIP submissions if needed
→ grading jobs run in containers
→ reports are displayed/downloadable
```

This is a support workflow. It is useful for early development, legacy submissions, and instructor-only grading. It should not become the primary student-facing product direction.

### Backend components

For the first home-server version:

```text
FastAPI web app
SQLite database
local file storage
Podman/OCI grading containers
```

Later:

```text
FastAPI web app
PostgreSQL
Redis queue
Celery/RQ workers
Podman/OCI grading containers
```

### Success criteria

The instructor can still grade legacy ZIP submissions and download grades plus feedback, while the main product path remains student workspaces.

---

## 5.8 Version 7: Canvas LTI Pilot

### Goal

Allow a student to launch a HamrForge assignment from Canvas and work in the correct server-side workspace.

### LTI features needed

- LTI 1.3 launch
- Assignment and Grade Services for grade passback
- Deep Linking eventually for assignment selection
- Names and Roles eventually for roster and role support

### First LTI test

The first LTI test should not run the autograder.

It should simply prove launch identity:

```text
Canvas launches HamrForge
HamrForge displays:
- user name or opaque user id
- course/context id
- role: instructor/student
- assignment/resource id
```

### Second LTI test

Fake grade passback:

```text
Student launches assignment
Student clicks “Complete Test”
HamrForge sends 10/10 to Canvas
Canvas gradebook updates
```

### Third LTI test

Real grade passback:

```text
Student launches assignment
HamrForge opens or creates the student's workspace
Student edits code and requests grading
HamrForge grades workspace
Score and feedback appear
Score passes back to Canvas
```

### Success criteria

Canvas gradebook receives a real autograder score from a real C++ workspace attempt.

---

## 5.9 Version 8: Deep Linking Assignment Picker

### Goal

Allow instructors to select an HamrForge activity while creating a Canvas assignment.

### Workflow

```text
Canvas assignment setup
→ External Tool
→ HamrForge
→ instructor selects “Byte Class Assignment”
→ Canvas creates link
→ students launch directly into that activity
```

### Success criteria

An instructor can choose an assignment from the HamrForge library without manually copying URLs or IDs.

---

## 5.10 Version 9: District-Hosted Solution

### Goal

Move from personal/home-server use to institutionally hosted infrastructure.

### Hosting model

```text
District Linux servers or cloud environment
  → HamrForge web app
  → database
  → queue
  → worker pool
  → sandboxed grading containers
  → Canvas LTI integration
```

### Institutional requirements

A district-hosted solution will need:

- security review
- FERPA/privacy review
- accessibility review
- disaster recovery plan
- backup plan
- logging policy
- retention policy
- support contact
- update process
- admin documentation
- LTI configuration documentation

### Success criteria

HamrForge is approved for limited or district-wide Canvas use.

---

# 6. Backend Architecture

## 6.1 Home-server MVP architecture

```text
Browser
  ↓
FastAPI Web App
  ↓
SQLite Database
  ↓
Local File Storage
  ↓
Podman/OCI Grading Container
  ↓
Report Files
```

This version is simple and private.

## 6.2 Scalable architecture

```text
Browser / Canvas
  ↓
FastAPI Web App
  ↓
PostgreSQL
  ↓
Redis Queue
  ↓
Celery/RQ Worker
  ↓
Sandboxed Grading Container
  ↓
Report Storage
  ↓
Canvas Grade Passback
```

## 6.3 Service responsibilities

### Web app

- serve instructor/student pages
- receive legacy uploads when needed
- create and open student workspaces
- serve a basic file editor with lightweight syntax highlighting
- save workspace file changes
- create attempt snapshots from workspaces
- validate file types
- create grading jobs
- display results
- handle LTI launch later
- handle grade passback later

### Database

- assignments
- users or owner_keys
- workspaces
- workspace files or filesystem roots
- attempts
- workspace snapshots
- submissions as compatibility input records
- jobs
- results
- reports
- user/course context later
- LTI deployment information later

### Worker

- pull grading jobs
- prepare grading workspace from an attempt snapshot or legacy ZIP submission
- launch sandbox
- collect results
- store reports

### Sandbox container

- compile C++
- run unit tests
- run console tests
- enforce limits
- produce structured report

---

# 7. Assignment Format

## 7.1 Example `assignment.yml`

```yaml
title: Unit 02 - Byte Class Construction
slug: byte-class
language: cpp
standard: c++17
compiler: g++
max_score: 40

submission:
  required_files:
    - main.cpp
    - Byte.h
    - Byte.cpp
  accepted_extensions:
    - .cpp
    - .h
    - .hpp
    - .zip
  ignored_paths:
    - .vs
    - Debug
    - Release
    - x64
    - __MACOSX

checks:
  - name: Required files
    type: file_check
    points: 12

  - name: Compiles
    type: compile
    points: 6

  - name: setValue stores integer value
    type: expression_test
    points: 3
    include:
      - Byte.h
    setup: |
      Byte b;
      b.setValue(99);
    expect:
      expression: b.toInt()
      equals: 99

  - name: at returns expected bits
    type: expression_test
    points: 3
    include:
      - Byte.h
    setup: |
      Byte b;
      b.setValue(99);
    expect:
      expression: b.at(0) == 1 && b.at(1) == 1 && b.at(2) == 0 && b.at(3) == 0 && b.at(4) == 0 && b.at(5) == 1 && b.at(6) == 1 && b.at(7) == 0
      equals: true

  - name: toString returns reversed bit string
    type: expression_test
    points: 2
    include:
      - Byte.h
    setup: |
      Byte b;
      b.setValue(99);
    expect:
      expression: b.toString()
      equals: "01100011"

  - name: Boundary value 255 works
    type: expression_test
    points: 2
    include:
      - Byte.h
    setup: |
      Byte b;
      b.setValue(255);
    expect:
      expression: b.toInt() == 255 && b.toString() == "11111111"
      equals: true

  - name: Program runs to completion
    type: console_io
    points: 12
    input: ""
    expected_contains: []
```

## 7.2 Check types

### `file_check`

Checks required files and forbidden files.

### `compile`

Compiles student C++ source files.

### `expression_test`

Generates a unit test around a C++ expression.

### `console_io`

Runs the program with scripted input and checks output.

### `code_pattern`

Checks source code for required or forbidden patterns.

### `manual_flag`

Flags submissions for instructor review.

---

# 8. Grading Reports

## 8.1 JSON report

```json
{
  "assignment": "Unit 02 - Byte Class Construction",
  "score": 32,
  "max_score": 40,
  "checks": [
    {
      "name": "Required files",
      "type": "file_check",
      "score": 12,
      "max_score": 12,
      "passed": true,
      "feedback": "All required files were found."
    },
    {
      "name": "setValue stores integer value",
      "type": "expression_test",
      "score": 0,
      "max_score": 3,
      "passed": false,
      "feedback": "Expression test failed.",
      "detail": "Expected: 99\nActual: 198"
    }
  ],
  "flags": [
    "expression_test_failed"
  ]
}
```

## 8.2 Markdown report

```markdown
# HamrForge Feedback Report

Assignment: Unit 02 - Byte Class Construction
Score: 32 / 40

## Results

### Required files — 12 / 12
All required files were found.

### Compiles — 6 / 6
Your code compiled successfully using C++17.

### setValue stores integer value — 0 / 3
Expression test failed.

Expected: 99
Actual: 198

Suggestion: Check whether the bits are being stored and converted in the expected order.
```

---

# 9. Sandbox Design

## 9.1 Sandbox purpose

The sandbox protects the host system from untrusted or broken student code.

Student code may:

- run forever
- allocate huge memory
- produce massive output
- write files endlessly
- attempt network access
- attempt system calls
- crash unexpectedly

## 9.2 MVP sandbox

The MVP sandbox can use OCI containers. Podman is the first implemented CLI-backed runner because it can run rootless on Linux development and server environments.

Minimum restrictions:

```bash
podman run --rm \
  --network none \
  --memory 256m \
  --cpus 1 \
  --pids-limit 64 \
  --read-only \
  --tmpfs /tmp:rw,size=64m \
  --security-opt no-new-privileges \
  --cap-drop ALL \
  --user 1000:1000 \
  --volume /path/to/workspace:/workspace:rw \
  --workdir /workspace \
  hamrforge-cpp-runner
```

Rev 1 should keep `local_unsafe` as the development default until the container image and host setup are easy to install. Assignments can opt into Podman with:

```yaml
runner:
  type: podman
  image: hamrforge-cpp-runner
```

The first `hamrforge-cpp-runner` image should be intentionally small:

- Debian slim or another small Linux base suitable for C++ grading
- `g++`
- `make`
- no Python unless the runner starts needing Python inside the container
- Catch2/doctest added later when generated framework-based tests are introduced

Smoke test:

```bash
podman run --rm hamrforge-cpp-runner g++ --version
```

## 9.3 Future sandbox hardening

Later versions may use:

- nsjail
- isolate
- gVisor
- Firecracker microVMs
- separate worker VM pool

## 9.4 Production isolation principle

For a district-hosted version, grading workers should not have access to:

- database credentials beyond what they need
- Canvas secrets
- internal district network resources
- web app admin functions
- long-term file storage except through controlled paths

If a grading sandbox fails, the blast radius should be limited.

---

# 10. Canvas LTI Design

## 10.1 LTI version

Target LTI 1.3 / LTI Advantage.

## 10.2 Required services

### Core launch

Allows users to launch HamrForge from Canvas.

### Assignment and Grade Services

Allows HamrForge to send scores back to the Canvas gradebook.

### Deep Linking

Allows instructors to select HamrForge assignments while creating Canvas assignments.

### Names and Roles

Optional later. Useful for roster-aware dashboards.

## 10.3 LTI launch flow

```text
Student opens Canvas assignment
→ Canvas sends LTI launch to HamrForge
→ HamrForge validates launch
→ HamrForge identifies course/user/resource context
→ HamrForge opens or creates the student's workspace
→ Student edits code and requests grading
→ HamrForge grades workspace
→ HamrForge sends score to Canvas
```

## 10.4 Deep Linking flow

```text
Instructor creates Canvas assignment
→ chooses External Tool
→ launches HamrForge picker
→ selects assignment
→ HamrForge returns deep link
→ Canvas stores activity link
```

## 10.5 LTI deployment data

The system must store LTI deployment configuration securely:

- issuer
- client ID
- deployment ID
- platform public key/JWKS URL
- auth login URL
- token URL
- tool private/public keys
- allowed scopes

These should never be committed to Git.

---

# 11. Data Model

## 11.1 Early SQLite tables

### assignments

- id
- slug
- title
- path
- language
- created_at

### users or owner_keys

- id
- owner_key
- display_name nullable
- created_at

For early local use, `owner_key` may be a simple string such as `demo-student`. Later LTI users can map to this concept through platform identity.

### workspaces

- id
- assignment_id
- owner_key_id or owner_key
- workspace_path
- created_at
- updated_at
- last_opened_at nullable

### workspace_snapshots

- id
- workspace_id
- snapshot_path
- created_at
- source_kind

For student-facing grading, snapshots preserve the exact source state that was graded. Early versions may store snapshots inside `.hamrforge/attempts/<attempt-id>/snapshot/`.

### attempts

- id
- workspace_id
- workspace_snapshot_id nullable
- submission_id nullable
- created_at
- trigger_type
- status

An attempt represents a grading event. Most attempts should come from workspace snapshots. ZIP-backed attempts remain useful for instructor/legacy workflows.

### submissions

- id
- assignment_id
- original_filename
- storage_path
- submitted_at
- source_kind

Submissions are compatibility input records. A submission may refer to an uploaded ZIP or to a workspace snapshot prepared for grading.

### grading_jobs

- id
- attempt_id
- status
- created_at
- started_at
- completed_at
- error_message

### grading_results

- id
- job_id
- attempt_id
- score
- max_score
- created_at

### reports

- id
- grading_result_id
- report_json_path
- report_md_path
- created_at

## 11.2 Later LTI tables

### lti_platforms

- id
- issuer
- client_id
- deployment_id
- jwks_url
- auth_login_url
- auth_token_url

### lti_contexts

- id
- platform_id
- canvas_course_id
- context_label
- context_title

### lti_users

- id
- platform_id
- lti_subject
- display_name
- email_hash_or_email_if_allowed

### lti_resource_links

- id
- context_id
- assignment_id
- resource_link_id
- line_item_url

---

# 12. Security and Privacy

## 12.1 Data minimization

Collect only what is needed.

For the home-server/student-workspace version:

- owner keys or minimal user identifiers
- workspace files
- attempt snapshots
- grades
- feedback reports
- legacy submission files when instructor ZIP workflows are used

For LTI version:

- Canvas user identifier
- Canvas course/context identifier
- Canvas assignment/resource identifier
- workspace files and attempt snapshots
- grading results
- score returned to Canvas

Avoid collecting unnecessary personal data.

## 12.2 Secrets management

Never commit:

- LTI private keys
- Canvas tokens
- database passwords
- worker credentials

Use environment variables or mounted secret files.

## 12.3 Upload safety

The upload layer should:

- reject very large files
- reject suspicious file types where possible
- store uploads outside executable web paths
- scan archive structure before extraction
- prevent zip-slip path traversal
- normalize extracted files

## 12.4 Logging

Logs should include enough information to debug grading jobs but not expose unnecessary student data.

---

# 13. Accessibility

The web interface should target WCAG 2.1 AA.

Design expectations:

- keyboard navigable
- readable headings
- screen-reader-friendly feedback
- no color-only pass/fail indicators
- high contrast
- clear error messages
- downloadable plain-text/Markdown feedback

---

# 14. Codex Development Strategy

## 14.1 Use small tickets

Do not ask Codex to build the whole project at once.

Use narrow tasks.

Example first ticket:

```text
Create a Python package named hamrforge with a CLI command:

hamrforge validate-assignment path/to/assignment

The command should load assignment.yml, validate required fields, and print clear errors.
Do not implement grading yet.
```

## 14.2 Suggested Codex ticket sequence

### Ticket 1: Project scaffold

- Python package
- CLI entry point
- README
- basic tests

### Ticket 2: Assignment validator

- load `assignment.yml`
- validate required fields
- print useful errors

### Ticket 3: Initial language adapter boundary

- define the first simple `LanguageAdapter` interface or adapter boundary
- implement only `CppAdapter`
- route `language: cpp` assignments to `CppAdapter`
- return a clear unsupported-language error for any other language
- do not implement Java, NASM, or RISC-V yet

### Ticket 4: Submission unpacker

- unzip submissions
- ignore junk folders
- prevent zip-slip
- list discovered source files

### Ticket 5: File check grader

- check required files
- produce JSON result

### Ticket 6: C++ compile check

- compile C++ files through `CppAdapter`
- capture compiler output
- report success/failure

### Ticket 7: Markdown and JSON reports

- write `report.json`
- write `report.md`

### Ticket 8: C++ expression test generator

- generate C++ tests from `expression_test` through `CppAdapter`
- compile with student code
- parse test results

### Ticket 9: Console I/O tests

- run program with scripted input
- compare expected output

### Ticket 10: Folder/workspace grading

- grade an existing folder, not only a ZIP
- preserve ZIP grading as a compatibility path
- make report output paths explicit

### Ticket 11: Starter workspace creation

- add `starter/` files to the sample assignment
- create `data/workspaces/demo-student/<assignment-slug>/`
- copy starter files into the workspace safely
- list workspace files

### Ticket 12: Basic student workspace web UI

- select assignment
- create/open demo workspace
- edit source files in a simple syntax-highlighted browser editor
- save changes
- grade current workspace
- display feedback

### Ticket 13: Sandboxed runner

- run grading in an OCI container
- set time/memory/process limits
- make Podman or Docker the real backend for untrusted code

### Ticket 14: Job queue

- add Redis/Celery or RQ
- async grading jobs

### Ticket 15: Instructor batch and legacy ZIP utilities

- grade all ZIP files in a directory
- export `grades.csv`
- keep this as an instructor utility, not the main student-facing path

### Ticket 16: LTI launch prototype

- validate Canvas launch
- display launch context
- map launch context to assignment/workspace

### Ticket 17: Grade passback prototype

- fake grade passback
- then real score passback

### Ticket 18: Deep Linking

- assignment picker
- return selected assignment to Canvas

### Post-Rev 1 adapter expansion roadmap

These are future roadmap items after the C++ Rev 1 grader is working:

- JavaAdapter prototype
- NasmAdapter prototype
- RiscVAdapter with RARS prototype

## 14.3 Definition of done for each ticket

Every ticket should include:

- code
- tests
- README update if needed
- sample data if needed
- clear manual test steps

---

# 15. First Build Target

The first real build target should be:

> HamrForge v0.1: Local CLI C++ Grader

This is Rev 1's first implemented adapter, not a commitment to making HamrForge Core C++-only.

## Features

- `hamrforge validate-assignment`
- `hamrforge grade`
- route `language: cpp` to `CppAdapter`
- clear unsupported-language errors for non-C++ assignments
- required file checks
- C++17 compile check
- generated expression tests
- console I/O tests
- Markdown report
- JSON report
- sample Byte Class assignment
- fake fixture submissions

## Success test

Run:

```bash
hamrforge grade assignments/byte-class test-cases/perfect.zip
hamrforge grade assignments/byte-class test-cases/missing-files.zip
hamrforge grade assignments/byte-class test-cases/compile-error.zip
```

Expected:

- perfect gets full credit for implemented checks
- missing-files loses file-check points
- compile-error loses compile points
- all produce readable feedback reports

This target proves the grader. The next build target should prove the student-workspace model.

This target is intentionally CLI-first because the grading engine has to exist before the workspace product can use it. It should not become the final product center.

---

# 15.1 Second Build Target

The second real build target should be:

> HamrForge v0.2: Private Student Workspace Prototype

## Features

- grade an existing folder/workspace
- sample assignment `starter/` files
- create/open a demo student workspace
- basic browser file list
- simple syntax-highlighted browser editor for source files
- save file changes
- grade current workspace
- display feedback in the browser

## Success test

Run the private web app, create a demo Byte Class workspace, edit a file, save it, grade it, and see feedback without uploading a ZIP.

---

# 16. Long-Term North Star

The long-term version of HamrForge is:

> A district-hosted, Canvas-integrated, open-source autograding and interactive activity platform where students work in server-side assignment workspaces and receive useful feedback.

But the first useful version is much smaller:

> A private C++ grading engine that can power student workspaces and still handle legacy ZIP submissions.

The next useful student-facing version is:

> A private web app where a student can open an assignment workspace, edit files, request grading, and read feedback.

The project should always preserve this ladder:

```text
Useful locally
→ useful on a home server
→ useful as a student workspace prototype
→ useful in one class
→ useful through Canvas
→ useful across a department
→ useful across a district
```

That ladder keeps the project grounded and prevents it from becoming another overbuilt courseware platform.

---

# 17. MVP Codex Kickoff Prompt

Use this prompt as the first Codex task from the root of the HamrForge repo.

```text
We are starting a new open-source project called HamrForge.

Read docs/DESIGN.md first and follow it. Build only the MVP scaffold. Do not build the whole project.

Goal for this ticket:
Create a Python-based local CLI tool that can validate an assignment folder.

Requirements:
1. Create a Python package named hamrforge.
2. Add a CLI command named hamrforge.
3. Implement this subcommand:

   hamrforge validate-assignment path/to/assignment

4. The command should load assignment.yml from the assignment folder.
5. Validate that assignment.yml includes:
   - title
   - slug
   - language
   - standard
   - compiler
   - max_score
   - submission.required_files
   - checks

6. Add the first simple language adapter boundary.
7. Implement only the C++ adapter for Rev 1.
8. Route `language: cpp` to the C++ adapter.
9. Return a clear unsupported-language error for any other language.
10. Print clear validation errors.
11. Add one sample assignment in assignments/byte-class/assignment.yml.
12. Add basic Python tests.
13. Update README.md with installation and usage instructions.
14. Keep the code cross-platform:
    - use pathlib
    - avoid hardcoded Windows paths
    - avoid shell=True unless there is a clear reason

Do not implement grading yet.
Do not implement Java, NASM, or RISC-V yet.
Do not implement Docker or Podman yet.
Do not implement Canvas or LTI yet.
Do not build a web app yet.
Keep this first ticket small, clean, and working.

Definition of done:
- I can run: hamrforge validate-assignment assignments/byte-class
- A valid assignment prints a success message.
- Invalid assignments print useful errors.
- Tests pass.
- README explains how to install and run the CLI locally.
```

---

# 18. MVP Build Sequence for Codex

After the kickoff ticket is complete and committed, use these next tickets one at a time.

## Ticket 2: Initial LanguageAdapter boundary

```text
Add the first adapter boundary without expanding Rev 1 beyond C++.

Requirements:
1. Define a simple LanguageAdapter interface or adapter boundary.
2. Implement CppAdapter only.
3. Route assignment language: cpp to CppAdapter.
4. Return a clear unsupported-language error for any other language.
5. Keep file parsing, report generation, and orchestration in HamrForge Core.
6. Add tests for cpp routing and unsupported language errors.

Do not implement Java in Rev 1.
Do not implement NASM in Rev 1.
Do not implement RISC-V in Rev 1.
Do not build a plugin marketplace.
```

## Ticket 3: Submission unpacker and file check

```text
Add a grade command that only performs required file checks.

Command:
hamrforge grade assignments/byte-class test-cases/missing-files.zip

Requirements:
1. Safely extract the ZIP into a temporary directory.
2. Prevent zip-slip path traversal.
3. Ignore junk folders like .vs, Debug, Release, x64, __MACOSX.
4. Search recursively for required files listed in assignment.yml.
5. Award points for the file_check check.
6. Produce report.json and report.md.
7. Print the score summary to the terminal.
8. Add fixture ZIPs or fixture folders for:
   - perfect
   - missing-files
9. Add tests.

Do not implement compile checks yet.
```

## Ticket 4: C++ compile check

```text
Add C++ compile check support through CppAdapter.

Requirements:
1. Find discovered .cpp files after extraction.
2. Compile them using g++ with the standard specified in assignment.yml.
3. Capture compiler stdout and stderr.
4. Award compile points only if compilation succeeds.
5. Include compiler output in report.md when compilation fails.
6. Add a compile-error fixture.
7. Add tests.

For now, it is acceptable for this to run locally. Containerized execution comes later.
```

## Ticket 5: Instructor batch grading utility

```text
Add legacy/instructor batch grading support.

Command:
hamrforge batch-grade assignments/byte-class submissions/*.zip --out reports/week5

Requirements:
1. Grade every ZIP file matching the glob.
2. Generate one Markdown feedback file per submission.
3. Generate grades.csv with filename, score, max_score, percent, and flags.
4. Generate summary.json.
5. Continue grading other submissions if one fails.
6. Add tests.

Keep this as an instructor utility. Do not make batch ZIP upload the main web direction. If workspace work is ready to proceed, this ticket can move later.
```

## Ticket 6: Container runner abstraction

```text
Add a sandbox runner abstraction, but do not require Docker Desktop.

Requirements:
1. Define a SandboxRunner interface.
2. Add a LocalUnsafeRunner for development only, clearly marked unsafe.
3. Add assignment-level or config-level runner selection, defaulting to `local_unsafe` for now.
4. Keep Docker/Podman unimplemented in this ticket.
5. Design the runner boundary so DockerCliRunner or PodmanCliRunner can be added later.
6. Keep the grading engine independent of the specific runtime.
7. Update docs to say HamrForge requires an OCI-compatible sandbox backend for real student submissions.
```

## Ticket 6.1: Podman CLI runner

```text
Add the first OCI-backed sandbox runner through the Podman CLI.

Requirements:
1. Implement PodmanCliRunner.
2. Mount the temporary grading workspace at /workspace.
3. Default the image to hamrforge-cpp-runner.
4. Support assignment runner config with type: podman and optional image.
5. Apply basic safety flags:
   - no network
   - memory limit
   - CPU limit
   - process limit
   - read-only root filesystem
   - tmpfs /tmp
   - no-new-privileges
   - dropped capabilities
   - non-root user where practical
6. If podman is missing, return a clear error.
7. Add tests for command construction without requiring Podman in CI.
8. Document Podman install and smoke-test steps.
```

## Ticket 7: C++ expression tests

```text
Add generated C++ expression_test support through CppAdapter.

Requirements:
1. Generate a small C++ harness from expression_test YAML.
2. Compile it with student support files.
3. Skip student main.cpp to avoid duplicate main functions.
4. Run the generated executable.
5. Award points when actual equals expected.
6. Report Expected and Actual on failure.
7. Add passing and failing fixtures.
8. Add tests.
```

## Ticket 8: Console I/O tests

```text
Add console_io support.

Requirements:
1. Compile the student's real program including main.cpp.
2. Run it with scripted stdin from assignment.yml.
3. Normalize line endings.
4. Check expected_contains values in stdout.
5. Report missing expected output and captured stdout/stderr.
6. Keep matching loose by default.
7. Add tests.

Future console_io options should let instructors choose stricter exact matching or looser pass-any input variants.
```

## Ticket 9: Private legacy one-ZIP web UI

```text
Add a minimal FastAPI web app for private instructor testing of legacy ZIP uploads.

Requirements:
1. Show a form with assignment path and one ZIP upload.
2. Run the existing grader.
3. Display score, checks, feedback, and failure details.
4. Link to report.md and report.json.
5. Store uploads and reports under data/.
6. Add web tests.

This is a temporary bridge UI. Do not expand it into batch-first product design unless explicitly needed.
```

## Ticket 10: Folder/workspace grading

```text
Allow the grader to grade a folder directly.

Requirements:
1. Accept either a ZIP file or a directory path.
2. Reuse the same grading engine for both.
3. Keep ZIP extraction safety for ZIP inputs.
4. Avoid modifying the original workspace while grading.
5. Write reports to explicit output directories.
6. Add tests for ZIP and folder grading parity.
```

## Ticket 11: Starter workspace creation

```text
Create server-side student workspaces from assignment starter files.

Requirements:
1. Add starter files to assignments/byte-class/starter/.
2. Implement workspace creation under data/workspaces/<owner>/<assignment-slug>/.
3. Copy starter files safely.
4. Prevent path traversal in workspace operations.
5. Add tests.
```

## Ticket 12: Basic student workspace web UI

```text
Add the first student-facing workflow.

Requirements:
1. List available assignments.
2. Create/open a demo student workspace.
3. Show workspace files.
4. Edit source files in a simple browser editor with lightweight syntax highlighting.
5. Save changes.
6. Grade the current workspace.
7. Display feedback.

Do not build a full IDE yet.
Do not add autocomplete, debugging, terminal access, or project-wide search yet.
Do not add accounts yet.
Do not add Canvas/LTI yet.
```

## Post-Rev 1 adapter expansion roadmap

After the C++ Rev 1 grader is working, future adapter tickets can be explored one at a time:

- JavaAdapter prototype
- NasmAdapter prototype
- RiscVAdapter with RARS prototype

Each future adapter should start with a narrow teaching use case, a small assignment fixture, and clear unsupported-feature errors.

