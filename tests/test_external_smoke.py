from __future__ import annotations

import os
from pathlib import Path

import pytest

from models import GradeResult, Submission


pytestmark = pytest.mark.external_smoke

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def fixture_path(name: str) -> Path:
    return FIXTURES_DIR / name


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _require_external_smoke_env() -> None:
    if not _is_truthy(os.getenv("RUN_EXTERNAL_SMOKE")):
        pytest.skip("External smoke disabled. Set RUN_EXTERNAL_SMOKE=1 to enable live provider tests.")

    if not os.getenv("ARK_API_KEY"):
        pytest.skip("External smoke requires ARK_API_KEY to be set for the doubao vision model.")


def _maybe_skip_external_instability(response, *, stage: str) -> None:
    if response.status_code < 500:
        return

    body = response.json()
    detail = str(body.get("detail", ""))
    lowered = detail.lower()
    transient_markers = (
        "未配置 ark_api_key",
        "未配置 dashscope_api_key",
        "connection error",
        "api connection",
        "timeout",
        "timed out",
        "rate limit",
        "429",
        "503",
        "504",
        "service unavailable",
    )
    if any(marker in lowered for marker in transient_markers):
        pytest.skip(f"External smoke skipped during {stage}: {detail}")


def test_real_doubao_end_to_end_smoke(
    api,
    teacher_account,
    student_auth,
    assignment,
    db_session_factory,
):
    _require_external_smoke_env()

    solution_bytes = fixture_path("valid_solution.docx").read_bytes()
    pdf_bytes = fixture_path("valid_submission.pdf").read_bytes()

    solution_response = api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
        filename="valid_solution.docx",
        content=solution_bytes,
    )
    _maybe_skip_external_instability(solution_response, stage="teacher file upload")
    assert solution_response.status_code == 200

    solution_body = solution_response.json()
    assert solution_body["qwen_file_id"] is None

    upload_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
        filename="valid_submission.pdf",
        content=pdf_bytes,
    )
    assert upload_response.status_code == 201

    submission_id = upload_response.json()["id"]
    grade_response = api.grade_submission(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )
    _maybe_skip_external_instability(grade_response, stage="vision grading")
    assert grade_response.status_code == 202

    grade_body = grade_response.json()
    assert grade_body["submission_id"] == submission_id
    assert grade_body["status"] == "grading"

    # TestClient runs BackgroundTasks to completion before .post() returns,
    # so the real vision-model grading has already finished by this point.
    result_response = api.get_submission_result(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )
    _maybe_skip_external_instability(result_response, stage="result fetch")
    assert result_response.status_code == 200
    result_body = result_response.json()
    assert result_body["status"] in {"graded", "needs_manual_review"}
    assert isinstance(result_body["questions"], list)
    assert result_body["questions"]
    assert isinstance(result_body["total_score"], (int, float))
    assert isinstance(result_body["max_total_score"], (int, float))

    first_question = result_body["questions"][0]
    assert set(first_question) == {"number", "is_correct", "score", "max_score", "comment"}
    assert isinstance(first_question["number"], int)
    assert first_question["is_correct"] is None or isinstance(first_question["is_correct"], bool)
    assert first_question["score"] is None or isinstance(first_question["score"], (int, float))
    assert isinstance(first_question["max_score"], (int, float))
    assert isinstance(first_question["comment"], str)

    with db_session_factory() as db:
        submission = db.get(Submission, submission_id)
        grade_result = db.query(GradeResult).filter(GradeResult.submission_id == submission_id).one_or_none()
        assert submission is not None
        assert submission.status == result_body["status"]
        assert submission.error_message is None
        assert grade_result is not None
        assert grade_result.model_name.startswith("vision:doubao:")
        assert isinstance(grade_result.raw_json, dict)
