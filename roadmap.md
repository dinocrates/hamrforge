# HamrForge Productization Roadmap

HamrForge's north star is a student-facing coding workspace and autograding system for teaching. ZIP and batch grading are useful instructor utilities, but the primary product path is:

```text
assignment repo
→ starter files
→ student workspace
→ attempt snapshot
→ grading job
→ sandboxed grading result
→ feedback
→ eventual Canvas passback
```

Rev 1 stays C++ only. The architecture should keep the language-adapter boundary clean, but Java, NASM, and RISC-V are future adapters, not Rev 1 deliverables.

## Current Status

HamrForge already has the core Rev 1 spine:

- Python package and CLI
- assignment parser and validator
- C++ adapter boundary
- ZIP and folder/workspace grading
- required file checks
- compile checks
- expression tests
- console I/O checks
- Markdown and JSON reports
- batch ZIP grading utility
- starter workspace creation
- private web UI with course cards, assignment cards, editor, file tree, Run, Grade, feedback, and attempt history
- sandbox runner abstraction
- `LocalUnsafeRunner` for development
- `PodmanCliRunner` and `hamrforge-cpp-runner` image scaffold
- file-backed workspace attempts
- file-backed local grading job records

The project is currently in the private prototype stage. It is useful for local testing and department-demo iteration, but it is not ready for real student exposure.

## Productization Phases

## Phase 0: Local C++ Grading Engine

Status: mostly complete.

Goal: prove that assignment repos can grade C++ submissions and produce useful reports.

Tickets:

1. Project scaffold
2. Assignment validator
3. Initial language adapter boundary
4. Submission unpacker
5. Required file check grader
6. C++ compile check
7. Markdown and JSON reports
8. C++ expression test generator
9. Console I/O tests
10. Folder/workspace grading

Definition of done:

- `hamrforge validate-assignment assignments/byte-class` works.
- `hamrforge grade assignments/byte-class test-cases/perfect.zip` works.
- perfect, missing-files, compile-error, infinite-loop, and huge-output fixtures behave predictably.
- unsupported languages fail clearly.

## Phase 1: Student Workspace Prototype

Status: in progress, substantially functional.

Goal: prove that a student can work from starter files in a server-side workspace without uploading a ZIP.

Tickets:

1. Starter workspace creation
2. Basic course portal
3. Section-aware assignment dashboard
4. Browser editor with syntax highlighting
5. Save file changes
6. Project file tree
7. Create, rename, and delete files
8. Run current workspace without grading
9. Grade current workspace
10. Attempt snapshots
11. Attempt history
12. Local grading job records

Definition of done:

- A demo student opens a course card.
- The student opens an assignment card.
- HamrForge creates a private workspace from starter files.
- The student edits files in the browser.
- The student clicks Run and sees output.
- The student clicks Grade and sees feedback.
- Each graded result is tied to a snapshot.
- The live workspace can change after grading without changing prior attempts.

## Phase 2: Dynamic App Behavior

Status: next.

Goal: make the workspace feel like an app instead of a page-refresh form workflow.

Tickets:

1. Dynamic Run output
2. Dynamic Grade Jobs V1
3. Job status polling
4. Dynamic feedback refresh after grading completes
5. Clear running/queued/completed/failed states
6. Keep non-JavaScript form fallback routes

Dynamic Grade Jobs V1 should do this:

```text
student clicks Grade
→ editor content is saved
→ grading job is created
→ page returns immediately
→ UI shows queued/running
→ browser polls job status
→ UI updates with result when complete
```

For this phase, a local background task or simple process-local worker is enough. Do not add Redis/Celery yet unless the synchronous path is blocking meaningful testing.

Definition of done:

- Run does not refresh the page.
- Grade does not need a full page refresh for normal use.
- Job status is visible and understandable.
- Compiler errors and grading feedback appear in-place.
- The app still works with simple HTML fallback routes.

## Phase 3: Demo-Ready Student Experience

Status: planned.

Goal: make the prototype understandable enough for department review while still being honest about what is fake/demo.

Tickets:

1. Clean student landing page
2. Clean instructor landing page
3. Course cards for current and previous courses
4. Course-specific navigation
5. Assignment workspace layout pass
6. Feedback layout pass
7. Assignment instructions layout pass
8. Demo login/front door that clearly switches fake student/instructor views
9. Seed demo data for at least two Byte assignments
10. Demo reset command or button for restoring sample workspaces

Definition of done:

- A viewer can understand the product flow in under two minutes.
- The UI looks intentional, modern, and teaching-focused.
- The demo does not depend on explaining raw diagnostic controls.
- The Byte Class and Byte Constructors assignments are both available.
- The rough diagnostic tools are still available but tucked away.

## Phase 4: Instructor Authoring and Course Setup

Status: planned.

Goal: support the teacher workflow, especially building the course while teaching it.

Tickets:

1. Assignment builder prototype
2. Edit assignment metadata
3. Edit student-facing instructions
4. Manage starter files
5. Manage required files
6. Manage simple checks
7. Validate assignment from the builder
8. Preview student assignment page
9. Section setup workflow
10. Copy/import assignments from prior courses or sections
11. Reserve Canvas/LTI configuration fields for later

Definition of done:

- An instructor can create or copy an assignment without hand-editing YAML for every step.
- The output remains a portable assignment repo/folder.
- Assignment builder changes can be validated before publishing.
- Copying a previous assignment into a new section is fast and understandable.

## Phase 5: Sandbox Hardening

Status: partially implemented.

Goal: make student code run in a containerized Linux grading environment instead of directly on the host.

Tickets:

1. Podman runner verification
2. Runner image build documentation
3. Podman smoke-test command
4. Clear errors for missing Podman
5. Clear errors for missing runner image
6. Clear errors for nonzero container exits
7. Clear timeout behavior
8. Output limits
9. Memory, CPU, process, and network limits
10. Read-only root filesystem where practical
11. Manual test script for perfect, compile-error, infinite-loop, huge-output, and missing-files submissions

Definition of done:

- `podman build -t hamrforge-cpp-runner .` works.
- `podman run --rm hamrforge-cpp-runner g++ --version` works.
- `hamrforge grade ... --runner podman` works for the main fixtures.
- Bad student code times out or fails safely.
- The web UI can use Podman for workspace grading on a machine with Podman installed.

## Phase 6: Real Job Queue and Worker

Status: planned.

Goal: separate the web app from grading execution.

Tickets:

1. Decide queue backend for home-server MVP, likely RQ or Celery
2. Introduce worker process
3. Move grading execution out of web request handlers
4. Persist job state beyond process memory
5. Add retry/error states
6. Add cancellation or timeout state
7. Add job cleanup policy
8. Add worker logs
9. Add admin/diagnostic job view

Definition of done:

- Clicking Grade creates a job quickly.
- A worker grades the attempt snapshot.
- The web app can show status while grading is happening.
- Multiple grading jobs do not freeze the web app.
- Failed jobs are understandable and recoverable.

## Phase 7: Data Model and Storage Productization

Status: planned.

Goal: move from demo-only file discovery toward durable application records without losing repo-first assignment portability.

Tickets:

1. Decide SQLite schema for home-server MVP
2. Add migrations
3. Store users or demo owner records
4. Store courses, terms, sections, and enrollments
5. Store assignment publications
6. Store workspace records
7. Store attempt and job records
8. Store report metadata while keeping report files on disk
9. Add storage cleanup and retention rules
10. Preserve assignment repos/folders as the source of assignment content

Definition of done:

- Course and workspace data survives restarts cleanly.
- File paths are tracked explicitly.
- Workspace files remain filesystem-backed.
- Assignment content remains portable.
- The database supports the web app; it does not become opaque courseware storage.

## Phase 8: Instructor Utilities

Status: partially complete on CLI, planned for web.

Goal: support instructor-only legacy workflows without making them the product center.

Tickets:

1. Web batch ZIP upload
2. Batch job creation
3. Grades CSV download
4. Summary JSON download
5. Per-student report download
6. Error-tolerant batch processing
7. Section-aware batch association
8. Optional manual review flags

Definition of done:

- An instructor can grade old ZIP submissions when needed.
- Batch grading uses the same runner and job architecture.
- The UI clearly frames this as an instructor utility, not the student workflow.

## Phase 9: Accounts, Roles, and Access Control

Status: planned.

Goal: make the system safe enough for real students on a private server.

Tickets:

1. Add authentication strategy
2. Add role model: student, instructor, admin
3. Replace visible `owner_key` access with authenticated user context
4. Enforce workspace ownership checks
5. Enforce instructor section access
6. Protect report routes
7. Prevent direct static serving of workspace files
8. Add audit logging for grading and file operations
9. Add basic FERPA/privacy-minded data handling notes

Definition of done:

- Students can only see their own workspaces and reports.
- Instructors can only see their own sections unless granted admin access.
- Workspace and report URLs cannot be guessed to access another student's work.
- The app is no longer demo-identity-only.

## Phase 10: Home-Server Deployment

Status: planned.

Goal: make HamrForge installable on Stephen's own server for one-class pilot use.

Tickets:

1. Create deployment config
2. Add environment-based settings
3. Add storage directory configuration
4. Add backup documentation
5. Add Podman setup documentation
6. Add service process documentation
7. Add HTTPS/reverse proxy notes
8. Add admin setup steps
9. Add update procedure

Definition of done:

- HamrForge can run persistently on a Linux home server.
- Workspaces, jobs, attempts, and reports are stored in known locations.
- Backups are possible.
- The server uses the OCI runner for grading.

## Phase 11: Canvas LTI Launch Prototype

Status: planned.

Goal: prove Canvas can launch HamrForge and provide identity/context.

Tickets:

1. Add LTI 1.3 launch endpoints
2. Register a test developer key/tool in Canvas
3. Validate launch request
4. Display launch context
5. Map Canvas user/context/resource IDs to HamrForge records
6. Open or create matching student workspace
7. Store LTI deployment configuration

Definition of done:

- Canvas launches HamrForge.
- HamrForge shows the launched user, role, course/context, and assignment/resource.
- A student launch can open the correct assignment workspace.
- No grade passback is required yet.

## Phase 12: Canvas Grade Passback

Status: planned.

Goal: send HamrForge grading results back to Canvas.

Tickets:

1. Implement Assignment and Grade Services client
2. Fake passback test
3. Pass back latest score
4. Pass back best score option
5. Store passback status
6. Show passback errors to instructor
7. Add retry passback action
8. Decide what feedback link or comment should appear in Canvas

Definition of done:

- A real C++ workspace attempt can update the Canvas gradebook.
- Failed passback is visible and retryable.
- The instructor can choose latest or best score policy.

## Phase 13: Deep Linking

Status: planned.

Goal: let instructors choose HamrForge assignments while creating Canvas assignments.

Tickets:

1. Add Deep Linking launch handler
2. Show assignment picker
3. Return selected assignment/resource to Canvas
4. Support section publication mapping
5. Handle copied/imported assignments

Definition of done:

- An instructor can create a Canvas assignment that links directly to a HamrForge activity without manually copying URLs.

## Phase 14: Department Pilot Readiness

Status: planned.

Goal: prepare for limited use beyond Stephen's machine.

Tickets:

1. Accessibility pass
2. Security review checklist
3. Privacy/FERPA checklist
4. Error logging policy
5. Data retention policy
6. Backup and restore test
7. Instructor quick-start guide
8. Student quick-start guide
9. Admin deployment guide
10. Pilot support plan

Definition of done:

- The department can understand what HamrForge does and does not do.
- A limited pilot has documented risks and setup steps.
- The tool is credible as teaching infrastructure, not just a local experiment.

## Phase 15: Post-Rev 1 Language Adapters

Status: future.

Goal: expand beyond C++ only after the C++ workspace product is working.

Tickets:

1. JavaAdapter prototype
2. NASM x86-64 prototype
3. RISC-V RARS prototype

Guardrails:

- Do not implement these in Rev 1.
- Each adapter starts with one narrow teaching use case.
- Each adapter gets fixtures, clear unsupported-feature errors, and documentation.
- The core grading engine should not be rewritten for adapter expansion.

## Near-Term Ticket Backlog

These are the most likely next tickets from the current state:

1. Dynamic Grade Jobs V1
2. Demo reset command/button for sample workspaces
3. Workspace UI layout cleanup for department demo
4. Podman manual verification pass on Stephen's Ubuntu environment
5. Assignment builder static-to-real MVP
6. Section setup/import/copy static-to-real MVP
7. SQLite data model design spike
8. Authentication/access-control design spike

## Productization Guardrails

- Keep Rev 1 C++ only.
- Keep ZIP/batch grading as an instructor utility.
- Keep student workspaces as the primary product direction.
- Keep assignment content repo/folder based and portable.
- Keep workspace files on disk, not as database blobs.
- Add a database for records and relationships when it helps, not for source-code storage.
- Do not expose demo `owner_key` routes to real students.
- Do not run untrusted student code with `local_unsafe`.
- Do not delay the C++ MVP by over-engineering plugins, marketplaces, or multi-language support.
- Every ticket should include tests, docs, and a manual validation path when practical.
