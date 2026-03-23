from __future__ import annotations

from pathlib import Path

from models import GradeQuestion, GradeResult, Submission


def test_grading_before_official_answer_fails_with_exact_message(
    api,
    teacher_account,
    student_auth,
    assignment,
    db_session_factory,
):
    submit_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
    )
    assert submit_response.status_code == 201
    submit_body = submit_response.json()
    submission_id = submit_body["id"]
    assert Path(submit_body["file_path"]).exists()

    response = api.grade_submission(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "该 assignment 尚未上传官方答案文件。"}

    with db_session_factory() as db:
        submission = db.get(Submission, submission_id)
        grade_result = db.query(GradeResult).filter(GradeResult.submission_id == submission_id).one_or_none()
        assert submission is not None
        assert submission.status == "uploaded"
        assert submission.error_message is None
        assert submission.graded_at is None
        assert grade_result is None


def test_grading_after_official_answer_returns_result_and_updates_db(
    api,
    teacher_account,
    student_auth,
    assignment,
    stub_successful_grading,
    db_session_factory,
    qwen_upload_calls,
):
    grading_stub = stub_successful_grading()

    upload_solution_response = api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )
    submit_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
    )
    submission_id = submit_response.json()["id"]

    grade_response = api.grade_submission(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )
    result_response = api.get_submission_result(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )

    assert upload_solution_response.status_code == 200
    upload_solution_body = upload_solution_response.json()
    submit_body = submit_response.json()
    assert qwen_upload_calls == [
        str(Path(upload_solution_body["file_path"]).resolve()),
        str(Path(submit_body["file_path"]).resolve()),
    ]

    assert grade_response.status_code == 200
    grade_body = grade_response.json()
    assert len(grading_stub["calls"]) == 1
    grading_call = grading_stub["calls"][0]
    assert grading_call["teacher_docx"] == upload_solution_body["file_path"]
    assert grading_call["student_pdf"] == submit_body["file_path"]
    assert grading_call["answer_file_id"] == upload_solution_body["id"]
    assert grading_call["submission_id"] == submission_id
    assert Path(grading_call["teacher_docx"]).exists()
    assert Path(grading_call["student_pdf"]).exists()

    assert grade_body["submission_id"] == submission_id
    assert grade_body["status"] == "graded"
    assert grade_body["total_score"] == 1.5
    assert grade_body["max_total_score"] == 2.0
    assert len(grade_body["questions"]) == 2
    assert grade_body["questions"][0] == {
        "number": 1,
        "is_correct": True,
        "score": 1.0,
        "max_score": 1.0,
        "comment": "答案正确。",
    }
    assert grade_body["questions"][1] == {
        "number": 2,
        "is_correct": False,
        "score": 0.5,
        "max_score": 1.0,
        "comment": "部分正确。",
    }

    assert result_response.status_code == 200
    result_body = result_response.json()
    assert result_body["submission_id"] == submission_id
    assert result_body["status"] == "graded"
    assert result_body["model_name"].startswith("vision:")
    assert result_body["graded_at"] is not None
    assert result_body["total_score"] == 1.5
    assert result_body["max_total_score"] == 2.0
    assert len(result_body["questions"]) == 2
    assert result_body["questions"][0]["comment"] == "[Q1] 答案正确。"
    assert result_body["questions"][1] == {
        "number": 2,
        "is_correct": False,
        "score": 0.5,
        "max_score": 1.0,
        "comment": "[Q2] 部分正确。",
    }

    with db_session_factory() as db:
        submission = db.get(Submission, submission_id)
        grade_result = db.query(GradeResult).filter(GradeResult.submission_id == submission_id).one_or_none()
        grade_questions = (
            db.query(GradeQuestion)
            .filter(GradeQuestion.grade_result_id == grade_result.id)
            .order_by(GradeQuestion.question_number.asc())
            .all()
            if grade_result is not None
            else []
        )

        assert submission is not None
        assert submission.status == "graded"
        assert submission.graded_at is not None
        assert submission.error_message is None
        assert grade_result is not None
        assert grade_result.model_name.startswith("vision:")
        assert grade_result.total_score == 1.5
        assert grade_result.max_total_score == 2.0
        assert grade_result.raw_json["normalized"]["summary"]["total_score"] == 1.5
        assert grade_result.raw_json["normalized"]["questions"][0]["question_id"] == "Q1"
        assert len(grade_questions) == 2
        assert grade_questions[0].question_number == 1
        assert grade_questions[0].comment == "[Q1] 答案正确。"
        assert grade_questions[1].question_number == 2
        assert grade_questions[1].comment == "[Q2] 部分正确。"


def test_grading_failure_marks_submission_failed(
    api,
    teacher_account,
    student_auth,
    assignment,
    stub_failed_grading,
    db_session_factory,
    qwen_upload_calls,
):
    grading_stub = stub_failed_grading("mock grade failure")
    error_message = grading_stub["message"]

    solution_response = api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )
    submit_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
    )
    submission_id = submit_response.json()["id"]

    response = api.grade_submission(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )

    assert response.status_code == 502
    assert response.json() == {"detail": f"视觉评分失败: {error_message}"}
    assert len(grading_stub["calls"]) == 1
    assert qwen_upload_calls == [
        str(Path(solution_response.json()["file_path"]).resolve()),
        str(Path(submit_response.json()["file_path"]).resolve()),
    ]

    with db_session_factory() as db:
        submission = db.get(Submission, submission_id)
        grade_result = db.query(GradeResult).filter(GradeResult.submission_id == submission_id).one_or_none()
        assert submission is not None
        assert submission.status == "failed_grading"
        assert submission.error_message == f"视觉评分失败: {error_message}"
        assert submission.graded_at is None
        assert grade_result is None


def test_manual_review_grading_preserves_per_question_result_structure(
    api,
    teacher_account,
    student_auth,
    assignment,
    stub_successful_grading,
    db_session_factory,
    qwen_upload_calls,
):
    grading_stub = stub_successful_grading(manual_review=True)

    solution_response = api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )
    submit_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
    )
    submission_id = submit_response.json()["id"]

    grade_response = api.grade_submission(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )
    result_response = api.get_submission_result(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )

    assert grade_response.status_code == 200
    grade_body = grade_response.json()
    assert len(grading_stub["calls"]) == 1
    assert qwen_upload_calls == [
        str(Path(solution_response.json()["file_path"]).resolve()),
        str(Path(submit_response.json()["file_path"]).resolve()),
    ]
    assert grade_body["submission_id"] == submission_id
    assert grade_body["status"] == "needs_manual_review"
    assert grade_body["total_score"] == 1.0
    assert grade_body["max_total_score"] == 2.0
    assert grade_body["questions"][1] == {
        "number": 2,
        "is_correct": None,
        "score": None,
        "max_score": 1.0,
        "comment": "需要人工复核。",
    }

    assert result_response.status_code == 200
    result_body = result_response.json()
    assert result_body["status"] == "needs_manual_review"
    assert result_body["total_score"] == 1.0
    assert result_body["max_total_score"] == 2.0
    assert len(result_body["questions"]) == 2
    assert result_body["questions"][1]["score"] is None
    assert result_body["questions"][1]["is_correct"] is None
    assert result_body["questions"][1]["comment"] == "[Q2] 需要人工复核。"

    with db_session_factory() as db:
        submission = db.get(Submission, submission_id)
        grade_result = db.query(GradeResult).filter(GradeResult.submission_id == submission_id).one()
        grade_questions = db.query(GradeQuestion).filter(
            GradeQuestion.grade_result_id == grade_result.id
        ).all()
        assert submission is not None
        assert submission.status == "needs_manual_review"
        assert submission.graded_at is not None
        assert grade_result.total_score == 1.0
        assert grade_result.raw_json["normalized"]["summary"]["needs_manual_review"] is True
        assert len(grade_questions) == 1
        assert grade_questions[0].question_number == 1
        assert grade_questions[0].comment == "[Q1] 答案正确。"


def test_grade_all_summarizes_results_and_skips_already_graded_submissions(
    api,
    teacher_account,
    course,
    assignment,
    student_account,
    student_auth,
    stub_successful_grading,
    db_session_factory,
):
    grading_stub = stub_successful_grading()

    second_student_password = "pw123456"
    create_second_student_response = api.create_student(
        teacher_headers=teacher_account["headers"],
        course_id=course["id"],
        name="第二个学生",
        email="student2@example.com",
        password=second_student_password,
    )
    assert create_second_student_response.status_code == 200

    second_student_login = api.student_login(
        email="student2@example.com",
        password=second_student_password,
    )
    assert second_student_login.status_code == 200
    second_student_headers = api.auth_headers(second_student_login.json()["access_token"])

    api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )
    first_upload = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
        filename="first-student.pdf",
    )
    second_upload = api.upload_submission_as_student(
        student_headers=second_student_headers,
        assignment_id=assignment["id"],
        filename="second-student.pdf",
    )

    assert first_upload.status_code == 201
    assert second_upload.status_code == 201

    first_run = api.grade_all(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )
    second_run = api.grade_all(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )

    assert first_run.status_code == 200
    assert first_run.json() == {
        "assignment_id": assignment["id"],
        "total": 2,
        "graded": 2,
        "failed": 0,
        "skipped": 0,
        "failures": [],
    }
    assert len(grading_stub["calls"]) == 2

    assert second_run.status_code == 200
    assert second_run.json() == {
        "assignment_id": assignment["id"],
        "total": 0,
        "graded": 0,
        "failed": 0,
        "skipped": 2,
        "failures": [],
    }
    assert len(grading_stub["calls"]) == 2

    with db_session_factory() as db:
        submissions = db.query(Submission).order_by(Submission.id.asc()).all()
        grade_results = db.query(GradeResult).order_by(GradeResult.submission_id.asc()).all()
        assert len(submissions) == 2
        assert all(item.status == "graded" for item in submissions)
        assert all(item.graded_at is not None for item in submissions)
        assert len(grade_results) == 2
