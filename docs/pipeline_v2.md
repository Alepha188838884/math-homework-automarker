# Pipeline V2 (Dual-Model Architecture)

## Goal
Refactor grading into four layers while keeping existing API routes and database schema unchanged.

## Layers
1. **Structure Layer (`teacher_spec.py`, qwen-long + qwen-3.5-plus)**
   - Parse teacher docx into `teacher_spec.json`.
   - Canonical labels come from `teacher_spec.questions[*].label`.

2. **Student Parsing Layer (`student_parsing.py`, qwen-long)**
   - Parse student PDF page text.
   - For each teacher label, locate candidate answer snippets.
   - Output `student_answers_raw.json`.

3. **Evaluation Layer (`grading.py`, qwen-3.5-plus)**
   - Grade one question at a time using question type dispatch.
   - `numeric/expression`: direct compare.
   - `explanation`: rubric-based scoring.
   - `graph/mixed`: first version falls back to manual review.

4. **Aggregation Layer (`aggregate.py`, pure Python)**
   - Enforce label consistency (`expected` vs `returned`).
   - Fill missing labels with fallback manual-review records.
   - Build final result summary.

## Compatibility Adapter (`qwen_service.py`)
- `grade_one_submission` signature unchanged.
- Existing DB tables unchanged.
- Map label-based final results back to existing DB format:
  - `grade_questions.question_number` uses teacher label order.
  - label is retained in `grade_results.raw_json` for audit.

## Artifacts
- `data/pipeline/teacher_spec/*_teacher_spec.json`
- `data/pipeline/student_answers_raw/*_student_answers_raw.json`
- `data/pipeline/grading_results/*_grading_result.json`
