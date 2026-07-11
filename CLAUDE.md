# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Math homework auto-grading system (中小学数学作业自动批改). Teachers upload answer `.docx`, students upload homework `.pdf`, backend does local image preprocessing then calls DashScope/Qwen vision model for per-question grading. Written in Chinese for Chinese math education.

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

# Run external smoke tests (requires real DashScope key)
RUN_EXTERNAL_SMOKE=1 DASHSCOPE_API_KEY=<key> python3 -m pytest -q tests/test_external_smoke.py -m external_smoke -o addopts=''
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
- `DASHSCOPE_API_KEY` — needed for actual grading (aliases: `QWEN_API_KEY`, `OPENAI_API_KEY`)

## Architecture

**Stack:** FastAPI + SQLAlchemy + Alembic (backend), React + Vite + TypeScript (frontend), deployed on Render.

**Active grading pipeline** (`qwen_service.py`): Extract images from teacher `.docx` → render student `.pdf` pages to grayscale PNG → feed to Qwen vision model → normalize JSON results → store in DB. The old text/spec pipeline (`teacher_spec.py`, `student_parsing.py`, `grading.py`, `aggregate.py`) is deprecated and not used in the active flow.

**Data model chain:** Teacher → Course → Student / Assignment → Submission → GradeResult → GradeQuestion

**Key backend files:**
- `main.py` — single-file FastAPI app with all routes and business orchestration
- `qwen_service.py` — core grading logic (vision model calls, result normalization, DB writes)
- `models.py` — SQLAlchemy ORM models (best entry for understanding DB structure)
- `schemas.py` — Pydantic request/response schemas (frontend JSON contract)
- `teacher_images.py` — extracts images from teacher `.docx`, splits on `"Solution"` paragraph
- `student_images.py` — renders student PDF pages to grayscale PNG via PyMuPDF
- `auth.py` — JWT + PBKDF2-SHA256 password hashing
- `runtime_config.py` — `APP_DATA_DIR`, `FRONTEND_BASE_URL`, CORS config

**Key frontend files:**
- `frontend/src/api.ts` — centralized backend API calls (field contract lives here)
- `frontend/src/teacher/TeacherWorkspaceContext.tsx` — teacher workspace shared state; most teacher pages depend on this rather than fetching independently
- `frontend/src/auth/` — dual teacher/student auth contexts with single-role session policy

## Critical Constraints

- **Chinese error messages are contractual.** Tests assert exact `{"detail": "..."}` Chinese strings. Don't change error text without updating tests.
- **Frontend field contracts are locked.** Status values, `questions` array structure, `due_date` UTC `Z` serialization, and field names are tested. Check `schemas.py` + `frontend/src/api.ts` + relevant tests before changing.
- **Teacher DOCX must contain a `"Solution"` paragraph** to split question images from answer images. This is a hard format requirement, not documentation.
- **CORS rejects wildcard.** `CORS_ALLOW_ORIGINS=*` throws an error.
- **Students belong to exactly one course.** No multi-course student model.
- **Submission is last-write-wins.** Re-upload replaces the previous submission and deletes old files + grades.
- **No `.env` auto-loading.** Environment variables must be explicitly exported or injected.

## Test Notes

- pytest config excludes `external_smoke` marker by default
- Tests redirect file paths to pytest temp directories (don't touch real `data/`)
- CI runs Python 3.11, requires `poppler-utils` system dependency
