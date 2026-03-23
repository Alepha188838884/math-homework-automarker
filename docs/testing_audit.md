# Backend Test Audit

## Shallow Tests Found

- Auth tests originally verified only login success/failure payloads and did not
  prove that returned JWTs could access protected routes.
- Assignment and submission tests covered the HTTP happy path, but some of them
  did not assert local file persistence, DB rows, or overwrite cleanup behavior.
- Grading tests had the correct mock boundary, but several assertions stopped at
  status code or top-level totals and did not inspect the exact grading call
  inputs, persisted raw JSON, or failure-path residual state.
- Permission/error tests confirmed HTTP errors, but they were light on
  “no side effects” verification.

## Fixes Made

- Added recorder-style assertions around both external boundaries:
  `main.upload_file_to_qwen` and `qwen_service.auto_grade_homework`.
- Strengthened auth tests to decode JWT payloads and use returned tokens against
  real protected endpoints.
- Added file-path existence checks so uploads and grading still prove real local
  persistence instead of only mocked success responses.
- Added DB assertions for `AnswerFile`, `Submission`, `GradeResult`, and
  `GradeQuestion` rows after success, overwrite, failure, and manual-review
  flows.
- Strengthened per-question result assertions for both direct grading responses
  and `/submissions/{id}/result`.
- Added “no side effects” checks for forbidden requests and invalid upload
  requests.
- Added batch-grading assertions proving second `grade-all` requests are skipped
  before crossing the external grading boundary again.

## Remaining Risks

- The suite still does not exercise the real DashScope/Qwen network integration,
  by design.
- The real DOCX/PDF parsing and image extraction path is still not covered in
  routine tests because grading is stubbed before those heavy external-style
  dependencies are used.
- There is still no deep coverage for join-link registration, teacher-side
  submission upload wrapper routes, or concurrency behavior.
- To deepen parser/network coverage further, the codebase would benefit from a
  dedicated integration-test layer with real fixture files and opt-in secrets.
