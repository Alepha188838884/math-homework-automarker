# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Math homework auto-grading system (中小学数学作业自动批改). Teachers upload an answer `.docx` or `.pdf`, students upload homework `.pdf`, backend does local image preprocessing then calls a vision model (Doubao/方舟 ARK by default, Qwen as fallback) for per-question grading. Written in Chinese for Chinese math education.

## Commands

### Backend
```bash
# Install dependencies
python3 -m pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start dev server
uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# Run tests (default: excludes external_smoke tests)
python3 -m pytest -q tests

# Run single test file
python3 -m pytest -q tests/test_grading_flow.py

# Run with coverage
python3 -m pytest -q tests --cov --cov-report=term-missing

# Run external smoke tests (requires a real ARK API key)
RUN_EXTERNAL_SMOKE=1 ARK_API_KEY=<key> python3 -m pytest -q tests/test_external_smoke.py -m external_smoke -o addopts=''
```

### Frontend
```bash
cd frontend
npm install
VITE_API_BASE_URL=http://localhost:8000 npm run dev
npm run build  # tsc -b && vite build
```

### Offline grading test
```bash
python3 quick_qwen_grade.py --answer-docx /path/to/answer.docx --student-pdf /path/to/submission.pdf
```

## Required Environment Variables

- `DATABASE_URL` — **import-time dependency** in `db.py`; must be set before any import
- `AUTH_SECRET_KEY` — must not be a placeholder value
- `ARK_API_KEY` — needed for actual grading via the default Doubao/方舟 provider (`GRADING_PROVIDER=doubao`)
- `DASHSCOPE_API_KEY` — needed for actual grading only when `GRADING_PROVIDER=qwen` (fallback provider; aliases: `QWEN_API_KEY`, `OPENAI_API_KEY`)

## Architecture

**Stack:** FastAPI + SQLAlchemy + Alembic (backend), React + Vite + TypeScript (frontend), deployed on Render.

**Active grading pipeline** (`grading_provider.py` + `grading_service.py`): Render both the teacher answer file (`.docx` or `.pdf`) and the student `.pdf` to page images (docx is converted to PDF via LibreOffice first) → feed all page images to the vision model (Doubao/方舟 ARK primary, Qwen fallback, selected via `GRADING_PROVIDER`) → normalize JSON results → store in DB. There is no more docx image-extraction or question/answer split — the vision model does whole-document matching instead. The old text/spec pipeline (`teacher_spec.py`, `student_parsing.py`, `grading.py`, `aggregate.py`) remains deprecated and unused in the active flow.

**Data model chain:** Teacher → Course → Student / Assignment → Submission → GradeResult → GradeQuestion

**Key backend files:**
- `main.py` — single-file FastAPI app with all routes and business orchestration
- `grading_provider.py` — vision-model provider abstraction (Doubao/ARK primary, Qwen fallback)
- `grading_service.py` — grading pipeline orchestration (page-image rendering, claiming/grading submissions, background job entry points)
- `file_processor.py` — docx→PDF conversion (via LibreOffice) and PDF→page-image rendering
- `student_images.py` — renders student PDF pages to PNG via PyMuPDF
- `models.py` — SQLAlchemy ORM models (best entry for understanding DB structure)
- `schemas.py` — Pydantic request/response schemas (frontend JSON contract)
- `auth.py` — JWT + PBKDF2-SHA256 password hashing
- `runtime_config.py` — `APP_DATA_DIR`, `FRONTEND_BASE_URL`, CORS config

**Key frontend files:**
- `frontend/src/api.ts` — centralized backend API calls (field contract lives here)
- `frontend/src/teacher/TeacherWorkspaceContext.tsx` — teacher workspace shared state; most teacher pages depend on this rather than fetching independently
- `frontend/src/auth/` — dual teacher/student auth contexts with single-role session policy

## Critical Constraints

- **Chinese error messages are contractual.** Tests assert exact `{"detail": "..."}` Chinese strings. Don't change error text without updating tests.
- **Frontend field contracts are locked.** Status values, `questions` array structure, `due_date` UTC `Z` serialization, and field names are tested. Check `schemas.py` + `frontend/src/api.ts` + relevant tests before changing.
- **Answer files accept `.docx` or `.pdf`.** No special layout or paragraph-marker requirement — the whole document is rendered to page images for the vision model.
- **Local docx grading requires LibreOffice** (`soffice` on PATH, or `SOFFICE_PATH` env var) to convert the teacher's `.docx` answer file to PDF before rendering.
- **CORS rejects wildcard.** `CORS_ALLOW_ORIGINS=*` throws an error.
- **Students belong to exactly one course.** No multi-course student model.
- **Submission is last-write-wins.** Re-upload replaces the previous submission and deletes old files + grades.
- **No `.env` auto-loading.** Environment variables must be explicitly exported or injected.

## Test Notes

- pytest config excludes `external_smoke` marker by default
- Tests redirect file paths to pytest temp directories (don't touch real `data/`)
- CI runs Python 3.11, requires `poppler-utils` system dependency
