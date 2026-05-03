# HamrForge Design Document

## Working Title

**HamrForge**

## Project Vision

HamrForge is an open-source, repo-based C++ autograding and courseware activity system designed for instructors who want the usefulness of commercial platforms like ZyBooks or zyLabs without vendor lock-in, opaque assignment design, or difficult test authoring.

The project begins as a local/home-server instructor tool and scaffolds upward toward a student-facing, server-hosted workspace system that can eventually launch from Canvas through LTI.

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
    bad-addition/
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
operator+ failed for 128 + 1.
Expected: 129
Actual: 1
Likely issue: your conversion method may be reading the bits in the wrong order or truncating values above 127.
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
Local CLI grader
→ private home-server web app
→ server-side student workspaces
→ lightweight browser coding environment
→ sandboxed worker system
→ Canvas LTI pilot
→ district-hosted solution
```

---

# 2. Scope

## 2.1 Initial scope

The first version should support:

- C++17 grading
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

- Canvas LTI launch
- Canvas grade passback
- Deep Linking assignment selection
- instructor dashboards
- student attempt history
- server-side student workspaces/repos
- basic browser file editor
- reusable OER assignment library
- additional languages
- GitHub Classroom-style workflows
- richer browser-based coding environment
- batch grading of uploaded ZIP submissions
- plagiarism/similarity checks
- AI-assisted feedback drafting

## 2.3 Explicit non-goals for early versions

Do not build these first:

- full LMS replacement
- full browser IDE
- commercial-style courseware marketplace
- multi-language support
- district deployment
- Canvas LTI
- roster sync
- analytics dashboards
- AI grading
- plagiarism detection

The first useful tool is:

> assignment repo + student ZIP submissions → score reports and feedback

The first student-facing version is:

> assignment repo + starter files → server-side student workspace → grade current workspace → feedback report

---

# 3. Cross-Platform Strategy: Windows Development, Linux Runtime

## 3.1 The situation

The instructor/developer may run the project at home on Windows, but the eventual backend should be Linux-based.

This is not a blocker, but it must shape the architecture.

## 3.2 Design decision

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

## 3.3 Why this works

C++ student code should be compiled and tested inside a Linux container regardless of whether the developer host is Windows or Linux.

That means the same assignment should behave consistently on:

- Windows + Docker Desktop + WSL2
- Linux server + Docker Engine
- future district-hosted Linux infrastructure

## 3.4 Coding rules for cross-platform sanity

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

## 3.5 Development recommendation

For Windows home development:

- Use Docker Desktop with WSL2 backend.
- Use VS Code with WSL extension if desired.
- Store the repo either in WSL’s Linux filesystem for best performance or in a clean Windows project folder if performance is acceptable.
- Use Docker Compose so the same service definitions can later run on Linux.

---

# 4. System Evolution

## 4.1 Version 0: Local CLI Grader

### Goal

Create a command-line tool that grades one student submission against one assignment repo.

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
- unzip student submission
- ignore common junk folders
- find source files
- check required files
- compile C++ code
- run basic tests
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

## 4.2 Version 1: Folder and Workspace Grader

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

## 4.3 Version 2: Starter Workspace Prototype

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

## 4.4 Version 3: Basic Student Workspace Web App

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
- simple text editor for starter/source files
- save file changes
- grade current workspace
- display feedback

### Not yet

- full IDE
- terminal access
- accounts
- collaboration
- Canvas/LTI identity

### Success criteria

A user can complete a small assignment loop through the browser without uploading a ZIP:

```text
create workspace → edit code → save → grade → read feedback
```

---

## 4.5 Version 4: Containerized Local Grader

### Goal

Move compilation and execution into containers.

### Why

Student code should not run directly on the host machine.

### Basic execution model

```text
CLI tool
  → prepares grading workspace
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

---

## 4.6 Version 5: Private Instructor Utilities

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

### Backend components

For the first home-server version:

```text
FastAPI web app
SQLite database
local file storage
Docker grading containers
```

Later:

```text
FastAPI web app
PostgreSQL
Redis queue
Celery/RQ workers
Docker grading containers
```

### Success criteria

The instructor can still grade legacy ZIP submissions and download grades plus feedback, but this is a support workflow rather than the main student-facing path.

---

## 4.7 Version 6: Job Queue and Worker Architecture

### Goal

Separate the web app from the grading worker.

### Why

Grading can be slow, dangerous, and resource intensive. The web app should not block while grading occurs.

### Architecture

```text
Web App
  → stores workspace changes or legacy upload
  → creates grading job
  → returns job status

Queue
  → holds pending grading jobs

Worker
  → pulls job
  → launches sandbox
  → runs grading
  → stores result
```

### Recommended components

```text
FastAPI
PostgreSQL
Redis
Celery or RQ
Docker worker containers
```

### Success criteria

Multiple workspace grading attempts or legacy ZIP submissions can be queued and processed without freezing the web app.

---

## 4.8 Version 7: Canvas LTI Pilot

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

## 4.9 Version 8: Deep Linking Assignment Picker

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

## 4.10 Version 9: District-Hosted Solution

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

# 5. Backend Architecture

## 5.1 Home-server MVP architecture

```text
Browser
  ↓
FastAPI Web App
  ↓
SQLite Database
  ↓
Local File Storage
  ↓
Docker Grading Container
  ↓
Report Files
```

This version is simple and private.

## 5.2 Scalable architecture

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

## 5.3 Service responsibilities

### Web app

- serve instructor/student pages
- receive uploads
- create and open student workspaces
- serve a basic file editor
- save workspace file changes
- validate file types
- create grading jobs
- display results
- handle LTI launch later
- handle grade passback later

### Database

- assignments
- workspaces
- workspace files or filesystem roots
- submissions
- attempts
- jobs
- results
- user/course context later
- LTI deployment information later

### Worker

- pull grading jobs
- prepare grading workspace from ZIP or existing student workspace
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

# 6. Assignment Format

## 6.1 Example `assignment.yml`

```yaml
title: Assignment 5 - Byte Class
slug: byte-class
language: cpp
standard: c++17
compiler: g++
max_score: 100

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
    points: 10

  - name: Compiles
    type: compile
    points: 20

  - name: Constructor stores value
    type: expression_test
    points: 15
    include:
      - Byte.h
    setup: |
      Byte b(13);
    expect:
      expression: b.toInt()
      equals: 13

  - name: Addition operator works
    type: expression_test
    points: 15
    include:
      - Byte.h
    setup: |
      Byte a(5);
      Byte b(7);
      Byte c = a + b;
    expect:
      expression: c.toInt()
      equals: 12

  - name: Edge case addition
    type: expression_test
    points: 20
    include:
      - Byte.h
    setup: |
      Byte a(128);
      Byte b(1);
      Byte c = a + b;
    expect:
      expression: c.toInt()
      equals: 129

  - name: Menu accepts user input
    type: console_io
    points: 20
    input: |
      1
      5
      7
      0
    expected_contains:
      - "12"
```

## 6.2 Check types

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

# 7. Grading Reports

## 7.1 JSON report

```json
{
  "assignment": "Assignment 5 - Byte Class",
  "score": 82,
  "max_score": 100,
  "checks": [
    {
      "name": "Required files",
      "type": "file_check",
      "score": 10,
      "max_score": 10,
      "passed": true,
      "feedback": "All required files were found."
    },
    {
      "name": "Edge case addition",
      "type": "expression_test",
      "score": 0,
      "max_score": 20,
      "passed": false,
      "feedback": "operator+ failed for 128 + 1. Expected 129."
    }
  ],
  "flags": [
    "manual_review_recommended"
  ]
}
```

## 7.2 Markdown report

```markdown
# HamrForge Feedback Report

Assignment: Assignment 5 - Byte Class
Score: 82 / 100

## Results

### Required files — 10 / 10
All required files were found.

### Compiles — 20 / 20
Your code compiled successfully using C++17.

### Edge case addition — 0 / 20
operator+ failed for 128 + 1.

Expected: 129  
Actual: 1

Suggestion: Check whether your binary conversion reads the bits in the correct order.
```

---

# 8. Sandbox Design

## 8.1 Sandbox purpose

The sandbox protects the host system from untrusted or broken student code.

Student code may:

- run forever
- allocate huge memory
- produce massive output
- write files endlessly
- attempt network access
- attempt system calls
- crash unexpectedly

## 8.2 MVP sandbox

The MVP sandbox can use Docker containers.

Minimum restrictions:

```bash
docker run --rm \
  --network none \
  --memory 256m \
  --cpus 1 \
  --pids-limit 64 \
  --read-only \
  --tmpfs /tmp:rw,size=64m \
  --security-opt no-new-privileges \
  --cap-drop ALL \
  hamrforge-cpp-runner
```

## 8.3 Future sandbox hardening

Later versions may use:

- nsjail
- isolate
- gVisor
- Firecracker microVMs
- separate worker VM pool

## 8.4 Production isolation principle

For a district-hosted version, grading workers should not have access to:

- database credentials beyond what they need
- Canvas secrets
- internal district network resources
- web app admin functions
- long-term file storage except through controlled paths

If a grading sandbox fails, the blast radius should be limited.

---

# 9. Canvas LTI Design

## 9.1 LTI version

Target LTI 1.3 / LTI Advantage.

## 9.2 Required services

### Core launch

Allows users to launch HamrForge from Canvas.

### Assignment and Grade Services

Allows HamrForge to send scores back to the Canvas gradebook.

### Deep Linking

Allows instructors to select HamrForge assignments while creating Canvas assignments.

### Names and Roles

Optional later. Useful for roster-aware dashboards.

## 9.3 LTI launch flow

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

## 9.4 Deep Linking flow

```text
Instructor creates Canvas assignment
→ chooses External Tool
→ launches HamrForge picker
→ selects assignment
→ HamrForge returns deep link
→ Canvas stores activity link
```

## 9.5 LTI deployment data

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

# 10. Data Model

## 10.1 Early SQLite tables

### assignments

- id
- slug
- title
- path
- created_at

### submissions

- id
- assignment_id
- original_filename
- storage_path
- submitted_at

### workspaces

- id
- assignment_id
- owner_key
- workspace_path
- created_at
- updated_at

### attempts

- id
- workspace_id
- submission_id nullable
- created_at
- source_snapshot_path
- trigger_type

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
- score
- max_score
- report_json_path
- report_md_path

## 10.2 Later LTI tables

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

# 11. Security and Privacy

## 11.1 Data minimization

Collect only what is needed.

For the home-server instructor version:

- submission files
- inferred student names if provided by filename
- grades
- feedback reports

For LTI version:

- Canvas user identifier
- Canvas course/context identifier
- Canvas assignment/resource identifier
- submission files
- grading results
- score returned to Canvas

Avoid collecting unnecessary personal data.

## 11.2 Secrets management

Never commit:

- LTI private keys
- Canvas tokens
- database passwords
- worker credentials

Use environment variables or mounted secret files.

## 11.3 Upload safety

The upload layer should:

- reject very large files
- reject suspicious file types where possible
- store uploads outside executable web paths
- scan archive structure before extraction
- prevent zip-slip path traversal
- normalize extracted files

## 11.4 Logging

Logs should include enough information to debug grading jobs but not expose unnecessary student data.

---

# 12. Accessibility

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

# 13. Codex Development Strategy

## 13.1 Use small tickets

Do not ask Codex to build the whole project at once.

Use narrow tasks.

Example first ticket:

```text
Create a Python package named hamrforge with a CLI command:

hamrforge validate-assignment path/to/assignment

The command should load assignment.yml, validate required fields, and print clear errors.
Do not implement grading yet.
```

## 13.2 Suggested Codex ticket sequence

### Ticket 1: Project scaffold

- Python package
- CLI entry point
- README
- basic tests

### Ticket 2: Assignment validator

- load `assignment.yml`
- validate required fields
- print useful errors

### Ticket 3: Submission unpacker

- unzip submissions
- ignore junk folders
- prevent zip-slip
- list discovered source files

### Ticket 4: File check grader

- check required files
- produce JSON result

### Ticket 5: Compile check

- compile C++ files
- capture compiler output
- report success/failure

### Ticket 6: Markdown and JSON reports

- write `report.json`
- write `report.md`

### Ticket 7: Batch grading utility

- grade all ZIP files in a directory
- export `grades.csv`
- keep this as an instructor utility, not the main student-facing path

### Ticket 8: Expression test generator

- generate C++ tests from `expression_test`
- compile with student code
- parse test results

### Ticket 9: Console I/O tests

- run program with scripted input
- compare expected output

### Ticket 10: Private single-ZIP web app

- upload assignment/submission
- run grading
- display report

### Ticket 11: Folder/workspace grading

- grade an existing folder, not only a ZIP
- preserve ZIP grading as a compatibility path
- make report output paths explicit

### Ticket 12: Starter workspace creation

- add `starter/` files to the sample assignment
- create `data/workspaces/demo-student/<assignment-slug>/`
- copy starter files into the workspace safely
- list workspace files

### Ticket 13: Basic student workspace web UI

- select assignment
- create/open demo workspace
- edit source files in a simple browser form
- save changes
- grade current workspace
- display feedback

### Ticket 14: Docker sandbox runner

- run grading in container
- set time/memory/process limits
- make Docker/Podman the real backend for untrusted code

### Ticket 15: Job queue

- add Redis/Celery or RQ
- async grading jobs

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

## 13.3 Definition of done for each ticket

Every ticket should include:

- code
- tests
- README update if needed
- sample data if needed
- clear manual test steps

---

# 14. First Build Target

The first real build target should be:

> HamrForge v0.1: Local CLI C++ Grader

## Features

- `hamrforge validate-assignment`
- `hamrforge grade`
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

---

# 14.1 Second Build Target

The second real build target should be:

> HamrForge v0.2: Private Student Workspace Prototype

## Features

- grade an existing folder/workspace
- sample assignment `starter/` files
- create/open a demo student workspace
- basic browser file list
- simple text editor for source files
- save file changes
- grade current workspace
- display feedback in the browser

## Success test

Run the private web app, create a demo Byte Class workspace, edit a file, save it, grade it, and see feedback without uploading a ZIP.

---

# 15. Long-Term North Star

The long-term version of HamrForge is:

> A district-hosted, Canvas-integrated, open-source autograding and interactive activity platform where students work in server-side assignment workspaces and receive useful feedback.

But the first useful version is much smaller:

> A private instructor tool that grades C++ submissions and generates feedback.

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

# 16. MVP Codex Kickoff Prompt

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

6. Print clear validation errors.
7. Add one sample assignment in assignments/byte-class/assignment.yml.
8. Add basic Python tests.
9. Update README.md with installation and usage instructions.
10. Keep the code cross-platform:
    - use pathlib
    - avoid hardcoded Windows paths
    - avoid shell=True unless there is a clear reason

Do not implement grading yet.
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

# 17. MVP Build Sequence for Codex

After the kickoff ticket is complete and committed, use these next tickets one at a time.

## Ticket 2: Submission unpacker and file check

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

## Ticket 3: Compile check

```text
Add compile check support.

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

## Ticket 4: Batch grading utility

```text
Add batch grading support.

Command:
hamrforge batch-grade assignments/byte-class submissions/*.zip --out reports/week5

Requirements:
1. Grade every ZIP file matching the glob.
2. Generate one Markdown feedback file per submission.
3. Generate grades.csv with filename, score, max_score, percent, and flags.
4. Generate summary.json.
5. Continue grading other submissions if one fails.
6. Add tests.

Keep this as an instructor utility. Do not make batch ZIP upload the main web direction.
```

## Ticket 5: Container runner abstraction

```text
Add a sandbox runner abstraction, but do not require Docker Desktop.

Requirements:
1. Define a SandboxRunner interface.
2. Add a LocalUnsafeRunner for development only, clearly marked unsafe.
3. Add a DockerCliRunner stub or initial implementation if Docker is available.
4. Design the runner so PodmanCliRunner can be added later.
5. Keep the grading engine independent of the specific runtime.
6. Update docs to say HamrForge requires an OCI-compatible sandbox backend for real student submissions.
```

## Ticket 6: Expression tests

```text
Add generated expression_test support.

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

## Ticket 7: Console I/O tests

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

## Ticket 8: Private one-ZIP web UI

```text
Add a minimal FastAPI web app for private instructor testing.

Requirements:
1. Show a form with assignment path and one ZIP upload.
2. Run the existing grader.
3. Display score, checks, feedback, and failure details.
4. Link to report.md and report.json.
5. Store uploads and reports under data/.
6. Add web tests.

This is a temporary bridge UI. Do not expand it into batch-first product design unless explicitly needed.
```

## Ticket 9: Folder/workspace grading

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

## Ticket 10: Starter workspace creation

```text
Create server-side student workspaces from assignment starter files.

Requirements:
1. Add starter files to assignments/byte-class/starter/.
2. Implement workspace creation under data/workspaces/<owner>/<assignment-slug>/.
3. Copy starter files safely.
4. Prevent path traversal in workspace operations.
5. Add tests.
```

## Ticket 11: Basic student workspace web UI

```text
Add the first student-facing workflow.

Requirements:
1. List available assignments.
2. Create/open a demo student workspace.
3. Show workspace files.
4. Edit source files in a simple browser textarea.
5. Save changes.
6. Grade the current workspace.
7. Display feedback.

Do not build a full IDE yet.
Do not add accounts yet.
Do not add Canvas/LTI yet.
```

