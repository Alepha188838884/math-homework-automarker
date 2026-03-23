from __future__ import annotations

from datetime import datetime


def assert_exact_keys(payload: dict, expected_keys: set[str]) -> None:
    assert set(payload.keys()) == expected_keys


def assert_iso_datetime(value: str | None, *, nullable: bool = False) -> None:
    if nullable:
        assert value is None or isinstance(value, str)
        if value is None:
            return
    else:
        assert isinstance(value, str)
    datetime.fromisoformat(value.replace("Z", "+00:00"))


def assert_number(value) -> None:
    assert isinstance(value, (int, float))
    assert not isinstance(value, bool)


def assert_grade_question_contract(question: dict, *, nullable_result: bool) -> None:
    assert_exact_keys(
        question,
        {"number", "is_correct", "score", "max_score", "comment"},
    )
    assert isinstance(question["number"], int)
    if nullable_result:
        assert question["is_correct"] is None
        assert question["score"] is None
    else:
        assert isinstance(question["is_correct"], bool)
        assert_number(question["score"])
    assert_number(question["max_score"])
    assert isinstance(question["comment"], str)


def test_teacher_login_response_contract(api, teacher_account):
    response = api.teacher_login(
        email=teacher_account["email"],
        password=teacher_account["password"],
    )

    assert response.status_code == 200
    body = response.json()
    assert_exact_keys(body, {"access_token", "token_type", "teacher"})
    assert isinstance(body["access_token"], str)
    assert body["token_type"] == "bearer"
    assert isinstance(body["teacher"], dict)
    assert_exact_keys(body["teacher"], {"id", "name", "email"})
    assert isinstance(body["teacher"]["id"], int)
    assert isinstance(body["teacher"]["name"], str)
    assert isinstance(body["teacher"]["email"], str)


def test_student_login_response_contract(api, student_account):
    response = api.student_login(
        email=student_account["email"],
        password=student_account["password"],
    )

    assert response.status_code == 200
    body = response.json()
    assert_exact_keys(body, {"access_token", "token_type", "student"})
    assert isinstance(body["access_token"], str)
    assert body["token_type"] == "bearer"
    assert isinstance(body["student"], dict)
    assert_exact_keys(body["student"], {"id", "name", "email", "course_id"})
    assert isinstance(body["student"]["id"], int)
    assert isinstance(body["student"]["name"], str)
    assert isinstance(body["student"]["email"], str)
    assert isinstance(body["student"]["course_id"], int)


def test_assignment_list_response_contract(api, teacher_account, assignment):
    response = api.list_assignments(teacher_headers=teacher_account["headers"])

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1

    item = body[0]
    assert_exact_keys(
        item,
        {"id", "teacher_id", "course_id", "title", "description", "due_date", "max_score", "created_at"},
    )
    assert isinstance(item["id"], int)
    assert isinstance(item["teacher_id"], int)
    assert isinstance(item["course_id"], int)
    assert isinstance(item["title"], str)
    assert isinstance(item["description"], str)
    assert item["due_date"] is None
    assert_number(item["max_score"])
    assert_iso_datetime(item["created_at"])
    assert item["id"] == assignment["id"]


def test_submission_list_response_contract(api, teacher_account, student_auth, assignment):
    upload_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
    )
    response = api.list_assignment_submissions(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )

    assert upload_response.status_code == 201
    assert response.status_code == 200

    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1

    item = body[0]
    assert_exact_keys(
        item,
        {"id", "assignment_id", "student_id", "original_filename", "status", "created_at", "graded_at"},
    )
    assert isinstance(item["id"], int)
    assert isinstance(item["assignment_id"], int)
    assert isinstance(item["student_id"], int)
    assert isinstance(item["original_filename"], str)
    assert isinstance(item["status"], str)
    assert_iso_datetime(item["created_at"])
    assert item["graded_at"] is None


def test_submission_result_response_contract(api, teacher_account, student_auth, assignment, stub_successful_grading):
    stub_successful_grading()

    api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )
    upload_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
    )
    submission_id = upload_response.json()["id"]
    api.grade_submission(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )
    response = api.get_submission_result(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )

    assert response.status_code == 200
    body = response.json()
    assert_exact_keys(
        body,
        {"submission_id", "status", "model_name", "graded_at", "questions", "total_score", "max_total_score"},
    )
    assert body["submission_id"] == submission_id
    assert body["status"] == "graded"
    assert isinstance(body["model_name"], str)
    assert_iso_datetime(body["graded_at"])
    assert_number(body["total_score"])
    assert_number(body["max_total_score"])
    assert isinstance(body["questions"], list)
    assert len(body["questions"]) == 2
    assert_grade_question_contract(body["questions"][0], nullable_result=False)
    assert_grade_question_contract(body["questions"][1], nullable_result=False)


def test_manual_review_submission_result_contract(
    api,
    teacher_account,
    student_auth,
    assignment,
    stub_successful_grading,
):
    stub_successful_grading(manual_review=True)

    api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )
    upload_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
    )
    submission_id = upload_response.json()["id"]
    api.grade_submission(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )
    response = api.get_submission_result(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_manual_review"
    assert isinstance(body["questions"], list)
    assert len(body["questions"]) == 2
    assert_grade_question_contract(body["questions"][0], nullable_result=False)
    assert_grade_question_contract(body["questions"][1], nullable_result=True)


def test_critical_chinese_error_response_contracts(
    api,
    teacher_account,
    student_auth,
    assignment,
):
    invalid_login_response = api.student_login(
        email=student_auth["student"]["email"],
        password="bad-password",
    )
    invalid_token_response = api.client.get(
        "/teachers/me/courses",
        headers={"Authorization": "Bearer invalid-token"},
    )
    upload_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
    )
    grading_without_solution_response = api.grade_submission(
        teacher_headers=teacher_account["headers"],
        submission_id=upload_response.json()["id"],
    )

    for response, message in [
        (invalid_login_response, "邮箱或密码错误。"),
        (invalid_token_response, "Token 无效或已过期。"),
        (grading_without_solution_response, "该 assignment 尚未上传官方答案文件。"),
    ]:
        assert "application/json" in response.headers["content-type"]
        body = response.json()
        assert_exact_keys(body, {"detail"})
        assert isinstance(body["detail"], str)
        assert body["detail"] == message
