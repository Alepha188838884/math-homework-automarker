# Backend Testing Notes

## Overview

The backend test suite uses `pytest` with FastAPI's in-process `TestClient`.
The default suite runs against the real application routes in `main.py`, but it
does not call real DashScope or Qwen services unless the optional
`external_smoke` group is enabled explicitly.

Run the suite with:

```bash
python3 -m pytest -q tests
```

Run only the auth smoke tests with:

```bash
python3 -m pytest -q tests/test_auth.py
```

Run the response-contract tests with:

```bash
python3 -m pytest -q tests/test_response_contracts.py
```

Run the full suite with coverage and generate an HTML report with:

```bash
python3 -m pytest -q tests --cov --cov-report=term-missing --cov-report=html
```

Run the optional live DashScope/Qwen smoke test with:

```bash
RUN_EXTERNAL_SMOKE=1 \
QWEN_VISION_MODEL=<your_vision_model> \
DASHSCOPE_API_KEY=<your_real_key> \
python3 -m pytest -q tests/test_external_smoke.py -m external_smoke -o addopts=''
```

## CI

- GitHub Actions runs the backend suite on every push and pull request via
  [backend-tests.yml](/Users/erichuang/Desktop/MathHomeworkAutomarker/.github/workflows/backend-tests.yml).
- CI installs Python dependencies from `requirements.txt`, installs
  `poppler-utils` for the offline PDF preprocessing tests, and runs:
  `python3 -m pytest -q tests`
- CI uses only safe test defaults. It does not require real DashScope/Qwen API
  keys and does not run live external smoke tests.
- The same local command to mirror CI is:
  `python3 -m pytest -q tests`
- What CI does not run:
  real external AI calls, deployment steps, frontend build checks, or any
  opt-in local-only experiments outside `tests/`.

## External Smoke Tests

- The repository now includes one opt-in live smoke test in
  [test_external_smoke.py](/Users/erichuang/Desktop/MathHomeworkAutomarker/tests/test_external_smoke.py).
- It is marked `external_smoke` and excluded from the default test run via
  `pytest.ini`, so `python3 -m pytest -q tests` stays fully offline.
- Exact activation prerequisites:
  `RUN_EXTERNAL_SMOKE=1`, one real DashScope key via any env var supported by
  [qwen_client.py](/Users/erichuang/Desktop/MathHomeworkAutomarker/qwen_client.py):
  `DASHSCOPE_API_KEY`, `DASSCOPE_API_KEY`, `DASHSCOPE_APIKEY`,
  `QWEN_API_KEY`, or `OPENAI_API_KEY`, plus `QWEN_VISION_MODEL` set explicitly
  to a vision-capable model available in your DashScope account.
- `DASHSCOPE_BASE_URL` remains optional and falls back to the repo default.
- If `RUN_EXTERNAL_SMOKE` is omitted, the test remains skipped even when valid
  credentials exist. This is intentional so normal development and CI stay
  offline by default.
- What the smoke test does:
  it uploads one real teacher `.docx` through the production upload route,
  uploads one real student `.pdf`, then performs one real `/submissions/{id}/grade`
  request and verifies that the result is persisted and readable from
  `/submissions/{id}/result`.
- What it does not do:
  it does not run in CI, does not replace the offline suite, and does not try
  to cover retries, rate limits, or large-file production behavior.
- If credentials are missing, `RUN_EXTERNAL_SMOKE` is not enabled, or the
  external service is temporarily unavailable, the smoke test skips cleanly
  with an explicit reason.

## Test Database

- Tests force `DATABASE_URL` to a dedicated SQLite file under `.pytest_runtime/`.
- Before each test, the suite drops and recreates all SQLAlchemy tables from
  `Base.metadata`.
- This keeps each test isolated while still exercising the real ORM models and
  session flow.

## File Upload Isolation

- `main.SOLUTIONS_DIR` and `main.SUBMISSIONS_DIR` are redirected to pytest's
  per-test `tmp_path`.
- The real repository `data/` directory is not used by the tests.

## Offline File Fixtures

- Binary fixtures live under `tests/fixtures/`.
- Current fixtures are:
  `valid_submission.pdf`, `valid_solution.docx`,
  `missing_solution_divider.docx`, `corrupted_submission.pdf`,
  `corrupted_solution.docx`, `empty_upload.pdf`, `empty_upload.docx`,
  `notes.txt`, and the tiny embedded image `tiny_square.png`.
- `valid_solution.docx` is intentionally different from the tiny placeholder
  fixtures: it now embeds one readable question image and one readable solution
  image so the same file can be used for real external smoke checks and
  `quick_qwen_grade.py`.
- The earlier version of `valid_solution.docx` embedded a `24x24` black-square
  test image. Local extraction was technically correct, but the real model only
  saw unreadable black blocks and correctly fell back to manual review.
- The remaining malformed/empty fixtures stay tiny and deterministic so the
  suite can cover local persistence and preprocessing failure paths without
  calling live external APIs.
- The offline file-processing tests use the real upload routes plus the real
  local helpers in `teacher_images.py` and `student_images.py` wherever those
  paths are separable from the external model call.

## External Grading Stubs

- `main.upload_file_to_qwen` is stubbed in every test and returns deterministic
  fake `qwen_file_id` values.
- `qwen_service.auto_grade_homework` is stubbed only in grading tests.
- The grading stub still exercises the real grading route, permission checks,
  submission status transitions, result persistence, and response serialization.
- The dedicated offline file-processing tests go one layer deeper:
  they stub `qwen_service.grade_with_qwen_vision` only, so local DOCX/PDF
  preprocessing still runs for valid-file grading paths.
- The only exception is the opt-in `external_smoke` group, which disables the
  upload stub and uses the real DashScope/Qwen integration path.

## Standardized File Errors

- Unsupported upload types are rejected at upload time:
  `官方答案必须是 .docx 文件。` and `学生作业必须是 .pdf 文件。`
- Empty or corrupted teacher DOCX files are currently accepted by the upload
  route if the extension is `.docx`, but grading now fails consistently with:
  `视觉评分失败: 老师答案 Word 文件无效，请检查文件是否为有效且非空的 .docx。`
- Empty or corrupted student PDF files are currently accepted by the upload
  route if the extension is `.pdf`, but grading now fails consistently with:
  `视觉评分失败: 学生提交 PDF 文件无效，请检查文件是否为有效且非空的 PDF。`
- Structured preprocessing rules inside valid DOCX files still surface their
  own business errors, such as:
  `视觉评分失败: 老师答案 Word 中未找到 'Solution' 分隔行。`
- These grading-time file failures are returned as JSON `{"detail": "..."}`
  with HTTP `502`, and the tests verify they do not leave grading results or
  stale student temp directories behind.

## due_date Contract

- `due_date` is accepted by `POST /courses/{course_id}/assignments`.
- Non-null `due_date` inputs are normalized to UTC at write time.
- All non-null `due_date` values are serialized back as UTC ISO-8601 strings
  with a trailing `Z`.
- Naive `due_date` inputs are treated as UTC.
- `null` remains `null`.
- The live endpoints that now follow this exact contract are:
  `POST /courses/{course_id}/assignments`,
  `GET /courses/{course_id}/assignments`,
  `GET /assignments`,
  `GET /students/me/assignments`.

## Adding New Endpoint Tests

- Put new tests under `tests/` so `pytest.ini` collects only the intended suite.
- Reuse fixtures from `tests/conftest.py` for teacher/student setup, auth
  headers, assignments, isolated DB state, and deterministic grading stubs.
- Prefer route-level assertions first, then add direct DB assertions only for
  state transitions or persistence rules that are not exposed via response data.

## Contract Tests

- Contract tests protect the JSON shape that the frontend depends on, not just
  the route success path.
- The most important locked responses currently include:
  `auth/login`, assignment list, submission list, submission result, and
  critical Chinese error bodies.
- These tests assert required keys, nesting shape, value types, and nullable
  fields where the frontend expects `null`.

## Frontend-Critical Contracts

- The dedicated frontend acceptance contracts are inferred from the real
  frontend code in `frontend/src/api.ts`, the auth contexts, the teacher
  workspace, `StudentJoinPage`, `StudentUploadPage`, and `GradeResultModal`.
- Frontend-critical contracts now explicitly protect:
  `POST /auth/teacher/entry`,
  `POST /auth/student/login`,
  `POST /courses/{course_id}/join-link`,
  `GET /courses/join/{join_token}`,
  `POST /courses/join/{join_token}/register`,
  `GET /courses/{course_id}/assignments`,
  `GET /assignments/{assignment_id}/submissions`,
  `GET /assignments/{assignment_id}/students-status`,
  `GET /students/me/assignments`,
  `POST /submissions/{submission_id}/grade`,
  `GET /submissions/{submission_id}/result`,
  plus the key user-facing Chinese `{"detail": "..."}` error responses.
- These acceptance tests lock:
  required keys, primitive types, nullability, list ordering that affects
  default frontend selection, and the visible state transitions
  `uploaded -> graded` and `uploaded -> needs_manual_review`.
- The grade route and result route are intentionally protected as two distinct
  contracts:
  `/submissions/{id}/grade` returns a lightweight grading result for immediate
  teacher actions, while `/submissions/{id}/result` returns the modal/detail
  payload with `model_name`, `graded_at`, and question comments formatted for
  display.
- Intentionally outside this frontend-contract layer:
  `/health`, the opt-in `external_smoke` group, raw external DashScope/Qwen
  transport details, and low-level upload response internals that the current
  UI does not render directly.

## Covered Routes

- Covered with route-level integration tests:
  `/auth/bootstrap-teacher`, `/auth/teacher/login`, `/auth/student/login`,
  `/teachers/me/courses`, `/courses/{course_id}/assignments`, `/assignments`,
  `/courses/{course_id}/join-link`, `/courses/join/{join_token}`,
  `/courses/join/{join_token}/register`,
  `/assignments/{assignment_id}/solution`,
  `/teachers/{teacher_id}/assignments/{assignment_id}/solution`,
  `/assignments/{assignment_id}/submissions`,
  `/assignments/{assignment_id}/submissions/me`,
  `/assignments/{assignment_id}/submissions`,
  `/submissions/{submission_id}/grade`,
  `/assignments/{assignment_id}/students-status`,
  `/assignments/{assignment_id}/grade-all`,
  `/submissions/{submission_id}/result`,
  `/students/me/assignments`

## Remaining Business Flows

- Newly covered in the current suite:
  join-link generation/info/register, teacher-side submission upload on behalf
  of a student, the legacy teacher solution upload path, and assignment
  student-status aggregation.
- Inspected and intentionally not added in this round:
  `/health` (trivial health check) and the auth entry variants
  `/auth/teacher/entry` plus `/auth/student/entry`, because this round focused
  on the remaining assignment/course business flows rather than alternate login
  entry points.
- No targeted route in this round appeared dead or deprecated-only; the legacy
  solution upload path is still active and now has explicit regression tests.
- Still not covered in depth:
  broad live external grading cases beyond the single opt-in smoke request,
  and image-decoding failures inside otherwise valid DOCX files.
- Locally covered preprocessing routes/helpers:
  student PDF save path, teacher DOCX save path, `teacher_images.ensure_teacher_images`,
  `student_images.export_student_pdf_to_images`, empty/corrupted PDF failure,
  and missing `Solution` divider handling.
- Still not fully covered in local parsing:
  image-decoding failures inside otherwise valid DOCX files are still not
  covered by dedicated fixtures, and live external grading calls remain out of
  scope for the offline suite.
