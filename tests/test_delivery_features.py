from __future__ import annotations

from pathlib import Path

import pytest

from models import AnswerFile, Assignment, Course, GradeQuestion, GradeResult, Student, Submission


def _grade_a_submission(api, teacher_account, student_auth, assignment, stub_successful_grading, *, manual_review=False):
    stub_successful_grading(manual_review=manual_review)
    solution_response = api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )
    assert solution_response.status_code == 200
    submit_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
    )
    assert submit_response.status_code == 201
    submission_id = submit_response.json()["id"]
    grade_response = api.grade_submission(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )
    assert grade_response.status_code == 202
    return submission_id


# ---------------------------------------------------------------------------
# Feature 1: teacher manual per-question override
# ---------------------------------------------------------------------------


def test_override_needs_review_question_flips_status_to_graded(
    api,
    teacher_account,
    student_auth,
    assignment,
    stub_successful_grading,
    db_session_factory,
):
    submission_id = _grade_a_submission(
        api, teacher_account, student_auth, assignment, stub_successful_grading, manual_review=True
    )

    # Sanity: submission starts out needing manual review, Q2 has no grade_questions row yet.
    pre_result = api.get_submission_result(teacher_headers=teacher_account["headers"], submission_id=submission_id)
    assert pre_result.status_code == 200
    assert pre_result.json()["status"] == "needs_manual_review"

    with db_session_factory() as db:
        grade_result = db.query(GradeResult).filter(GradeResult.submission_id == submission_id).one()
        rows_before = db.query(GradeQuestion).filter(GradeQuestion.grade_result_id == grade_result.id).all()
        assert len(rows_before) == 1  # only Q1 (auto-graded)

    response = api.override_question(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
        question_number=2,
        score=1.0,
        is_correct=True,
        comment="人工复核后正确。",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "graded"
    assert body["total_score"] == 2.0
    q2 = next(q for q in body["questions"] if q["number"] == 2)
    assert q2["score"] == 1.0
    assert q2["is_correct"] is True
    assert "需人工复核" not in (q2["comment"] or "")

    with db_session_factory() as db:
        submission = db.get(Submission, submission_id)
        assert submission.status == "graded"

        grade_result = db.query(GradeResult).filter(GradeResult.submission_id == submission_id).one()
        assert grade_result.total_score == 2.0

        normalized_questions = grade_result.raw_json["normalized"]["questions"]
        q2_normalized = next(q for q in normalized_questions if q["question_number"] == 2)
        assert q2_normalized["manual_override"] is True
        assert q2_normalized["score"] == 1.0
        assert q2_normalized["is_correct"] is True

        rows_after = (
            db.query(GradeQuestion)
            .filter(GradeQuestion.grade_result_id == grade_result.id)
            .order_by(GradeQuestion.question_number.asc())
            .all()
        )
        assert len(rows_after) == 2
        assert rows_after[1].question_number == 2
        assert rows_after[1].score == 1.0
        assert rows_after[1].is_correct is True


def test_override_score_out_of_bounds_returns_400(
    api, teacher_account, student_auth, assignment, stub_successful_grading
):
    submission_id = _grade_a_submission(api, teacher_account, student_auth, assignment, stub_successful_grading)

    response = api.override_question(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
        question_number=1,
        score=5.0,
        is_correct=True,
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "score 必须在 0 到 1.0 之间。"}


def test_override_nonexistent_question_returns_404(
    api, teacher_account, student_auth, assignment, stub_successful_grading
):
    submission_id = _grade_a_submission(api, teacher_account, student_auth, assignment, stub_successful_grading)

    response = api.override_question(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
        question_number=99,
        score=1.0,
        is_correct=True,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "题目 99 不存在。"}


def test_override_forbidden_for_other_teacher(
    api, teacher_account, second_teacher_account, student_auth, assignment, stub_successful_grading
):
    submission_id = _grade_a_submission(api, teacher_account, student_auth, assignment, stub_successful_grading)

    response = api.override_question(
        teacher_headers=second_teacher_account["headers"],
        submission_id=submission_id,
        question_number=1,
        score=1.0,
        is_correct=True,
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Feature 2: cascading deletion endpoints
# ---------------------------------------------------------------------------


def test_delete_assignment_cascades_rows_and_files(
    api, teacher_account, student_auth, assignment, stub_successful_grading, db_session_factory
):
    submission_id = _grade_a_submission(api, teacher_account, student_auth, assignment, stub_successful_grading)

    with db_session_factory() as db:
        submission = db.get(Submission, submission_id)
        submission_file_path = Path(submission.file_path)
        answer_file = db.query(AnswerFile).filter(AnswerFile.assignment_id == assignment["id"]).one()
        answer_file_path = Path(answer_file.file_path)
    assert submission_file_path.exists()
    assert answer_file_path.exists()

    response = api.delete_assignment(teacher_headers=teacher_account["headers"], assignment_id=assignment["id"])
    assert response.status_code == 204

    with db_session_factory() as db:
        assert db.get(Submission, submission_id) is None
        assert db.query(GradeResult).filter(GradeResult.submission_id == submission_id).one_or_none() is None
        assert db.query(GradeQuestion).count() == 0
        assert db.query(AnswerFile).filter(AnswerFile.assignment_id == assignment["id"]).one_or_none() is None
        assert db.get(Assignment, assignment["id"]) is None

    assert not submission_file_path.exists()
    assert not answer_file_path.exists()

    list_response = api.list_assignments(teacher_headers=teacher_account["headers"])
    assert assignment["id"] not in [a["id"] for a in list_response.json()]


def test_delete_assignment_forbidden_for_other_teacher(api, teacher_account, second_teacher_account, assignment):
    response = api.delete_assignment(
        teacher_headers=second_teacher_account["headers"], assignment_id=assignment["id"]
    )
    assert response.status_code == 403


def test_delete_course_student_cascades(
    api, teacher_account, student_auth, student_account, assignment, stub_successful_grading, course, db_session_factory
):
    submission_id = _grade_a_submission(api, teacher_account, student_auth, assignment, stub_successful_grading)

    response = api.delete_course_student(
        teacher_headers=teacher_account["headers"],
        course_id=course["id"],
        student_id=student_account["id"],
    )
    assert response.status_code == 204

    with db_session_factory() as db:
        assert db.get(Submission, submission_id) is None
        assert db.get(Student, student_account["id"]) is None


def test_delete_course_student_not_in_course_returns_404(api, teacher_account, course):
    response = api.delete_course_student(
        teacher_headers=teacher_account["headers"],
        course_id=course["id"],
        student_id=999999,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Student 999999 不存在。"}


def test_delete_course_cascades_assignments_and_students(
    api, teacher_account, student_auth, student_account, assignment, stub_successful_grading, course, db_session_factory
):
    submission_id = _grade_a_submission(api, teacher_account, student_auth, assignment, stub_successful_grading)

    response = api.delete_course(teacher_headers=teacher_account["headers"], course_id=course["id"])
    assert response.status_code == 204

    with db_session_factory() as db:
        assert db.get(Submission, submission_id) is None
        assert db.get(Assignment, assignment["id"]) is None
        assert db.get(Student, student_account["id"]) is None
        assert db.get(Course, course["id"]) is None


def test_delete_course_forbidden_for_other_teacher(api, teacher_account, second_teacher_account, course):
    response = api.delete_course(teacher_headers=second_teacher_account["headers"], course_id=course["id"])
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Feature 3: teacher signup invite code
# ---------------------------------------------------------------------------


def test_teacher_entry_new_account_wrong_code_returns_403(api, teacher_account, monkeypatch):
    monkeypatch.setenv("TEACHER_SIGNUP_CODE", "correct-code")
    response = api.teacher_entry(name="New Teacher", email="new1@example.com", signup_code="wrong-code")
    assert response.status_code == 403
    assert response.json() == {"detail": "邀请码不正确，无法注册新教师账号。"}


def test_teacher_entry_new_account_missing_code_returns_403(api, teacher_account, monkeypatch):
    monkeypatch.setenv("TEACHER_SIGNUP_CODE", "correct-code")
    response = api.teacher_entry(name="New Teacher", email="new2@example.com")
    assert response.status_code == 403
    assert response.json() == {"detail": "邀请码不正确，无法注册新教师账号。"}


def test_teacher_entry_new_account_correct_code_succeeds(api, teacher_account, monkeypatch):
    monkeypatch.setenv("TEACHER_SIGNUP_CODE", "correct-code")
    response = api.teacher_entry(name="New Teacher", email="new3@example.com", signup_code="correct-code")
    assert response.status_code == 200


def test_teacher_entry_no_env_no_code_required(api, teacher_account):
    response = api.teacher_entry(name="New Teacher", email="new4@example.com")
    assert response.status_code == 200


def test_teacher_entry_login_branch_unaffected_by_signup_code(api, teacher_account, monkeypatch):
    monkeypatch.setenv("TEACHER_SIGNUP_CODE", "correct-code")
    response = api.teacher_entry(
        name="Test Teacher",
        email=teacher_account["email"],
        password=teacher_account["password"],
    )
    assert response.status_code == 200


def test_bootstrap_teacher_signup_code_gate(api, monkeypatch):
    monkeypatch.setenv("TEACHER_SIGNUP_CODE", "correct-code")
    wrong = api.bootstrap_teacher(email="boot1@example.com", signup_code="wrong")
    assert wrong.status_code == 403
    assert wrong.json() == {"detail": "邀请码不正确，无法注册新教师账号。"}

    ok = api.bootstrap_teacher(email="boot1@example.com", signup_code="correct-code")
    assert ok.status_code == 200


# ---------------------------------------------------------------------------
# Feature 4: student viewing own per-question result
# ---------------------------------------------------------------------------


def test_student_can_view_own_result(
    api, teacher_account, student_auth, assignment, stub_successful_grading
):
    submission_id = _grade_a_submission(api, teacher_account, student_auth, assignment, stub_successful_grading)

    response = api.get_my_submission_result(student_headers=student_auth["headers"], submission_id=submission_id)
    assert response.status_code == 200
    body = response.json()
    assert body["submission_id"] == submission_id
    assert body["total_score"] == 1.5


def test_student_cannot_view_others_result(
    api,
    teacher_account,
    course,
    student_auth,
    assignment,
    stub_successful_grading,
):
    submission_id = _grade_a_submission(api, teacher_account, student_auth, assignment, stub_successful_grading)

    other_response = api.create_student(
        teacher_headers=teacher_account["headers"],
        course_id=course["id"],
        name="另一个学生",
        email="other-student@example.com",
        password="pw123456",
    )
    assert other_response.status_code == 200
    other_login = api.student_login(email="other-student@example.com", password="pw123456")
    assert other_login.status_code == 200
    other_headers = api.auth_headers(other_login.json()["access_token"])

    response = api.get_my_submission_result(student_headers=other_headers, submission_id=submission_id)
    assert response.status_code == 404
    assert response.json() == {"detail": f"Submission {submission_id} 不存在。"}


def test_student_result_404_when_not_graded_yet(api, teacher_account, student_auth, assignment):
    submit_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
    )
    submission_id = submit_response.json()["id"]

    response = api.get_my_submission_result(student_headers=student_auth["headers"], submission_id=submission_id)
    assert response.status_code == 404
    assert response.json() == {"detail": "该 submission 尚未完成评分。"}


# ---------------------------------------------------------------------------
# Feature 5: teacher password reset for a student
# ---------------------------------------------------------------------------


def test_reset_password_old_password_fails_new_password_works(
    api, teacher_account, student_account, course
):
    reset_response = api.reset_student_password(
        teacher_headers=teacher_account["headers"],
        course_id=course["id"],
        student_id=student_account["id"],
        new_password="new-secret-1",
    )
    assert reset_response.status_code == 200
    assert reset_response.json() == {"detail": "密码已重置。"}

    old_login = api.student_login(email=student_account["email"], password=student_account["password"])
    assert old_login.status_code == 401

    new_login = api.student_login(email=student_account["email"], password="new-secret-1")
    assert new_login.status_code == 200


def test_reset_password_forbidden_for_other_teacher(
    api, teacher_account, second_teacher_account, student_account, course
):
    response = api.reset_student_password(
        teacher_headers=second_teacher_account["headers"],
        course_id=course["id"],
        student_id=student_account["id"],
        new_password="new-secret-2",
    )
    assert response.status_code == 403


def test_reset_password_student_not_in_course_returns_404(api, teacher_account, course):
    response = api.reset_student_password(
        teacher_headers=teacher_account["headers"],
        course_id=course["id"],
        student_id=999999,
        new_password="new-secret-3",
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Student 999999 不存在。"}
