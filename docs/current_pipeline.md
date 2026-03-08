# Current Pipeline (Before Dual-Model Refactor)

## Stack
- Backend: Python + FastAPI + SQLAlchemy + SQLite
- LLM: DashScope OpenAI-compatible API via `openai` Python SDK

## Upload + Storage Flow
1. Teacher uploads `.docx` solution.
2. Backend saves local file path to `answer_files.file_path`.
3. Backend uploads file to Qwen and stores `answer_files.qwen_file_id`.
4. Student uploads `.pdf` homework.
5. Backend saves local file path to `submissions.file_path`.
6. Backend uploads file to Qwen and stores `submissions.qwen_file_id`.

## Grading Flow (Legacy Single-Step)
1. `main.py` calls `qwen_service.grade_one_submission(db, submission_id)`.
2. `grade_one_submission` sends one chat request with `fileid://teacher,student`.
3. Model output JSON is parsed.
4. Backend writes:
   - `grade_results` (raw JSON + totals)
   - `grade_questions` (per question score)
5. Submission status transitions to `graded` or `failed_grading`.

## Key Modules
- `main.py`: route handlers, file persistence, status transitions.
- `qwen_service.py`: model call + JSON parsing + DB writeback.
- `quick_qwen_grade.py`: local script for direct grading smoke tests.
