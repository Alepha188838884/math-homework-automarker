from __future__ import annotations

"""
Frontend-facing acceptance contracts inferred from the real UI code in:
- frontend/src/api.ts
- frontend/src/auth/TeacherAuthContext.tsx
- frontend/src/auth/StudentAuthContext.tsx
- frontend/src/components/GradeResultModal.tsx
- frontend/src/components/StudentJoinPage.tsx
- frontend/src/components/StudentUploadPage.tsx
- frontend/src/teacher/TeacherWorkspaceContext.tsx
- frontend/src/teacher/pages/TeacherAssignmentsPage.tsx
- frontend/src/teacher/pages/TeacherSubmissionStatusPage.tsx
"""

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


def assert_grade_question_shape(question: dict, *, nullable_result: bool) -> None:
    assert_exact_keys(question, {"number", "is_correct", "score", "max_score", "comment"})
    assert isinstance(question["number"], int)
    if nullable_result:
        assert question["is_correct"] is None
        assert question["score"] is None
    else:
        assert isinstance(question["is_correct"], bool)
        assert_number(question["score"])
    assert_number(question["max_score"])
    assert question["comment"] is None or isinstance(question["comment"], str)


def test_frontend_auth_entry_and_login_contracts_match_real_auth_contexts(
    api,
    teacher_account,
    student_account,
):
    teacher_entry_response = api.teacher_entry(
        name="",
        email=teacher_account["email"],
        password=teacher_account["password"],
    )
    student_login_response = api.student_login(
        email=student_account["email"],
        password=student_account["password"],
    )

    assert teacher_entry_response.status_code == 200
    teacher_body = teacher_entry_response.json()
    assert_exact_keys(teacher_body, {"access_token", "token_type", "teacher"})
    assert isinstance(teacher_body["access_token"], str)
    assert teacher_body["token_type"] == "bearer"
    assert_exact_keys(teacher_body["teacher"], {"id", "name", "email"})
    assert isinstance(teacher_body["teacher"]["id"], int)
    assert isinstance(teacher_body["teacher"]["name"], str)
    assert isinstance(teacher_body["teacher"]["email"], str)

    assert student_login_response.status_code == 200
    student_body = student_login_response.json()
    assert_exact_keys(student_body, {"access_token", "token_type", "student"})
    assert isinstance(student_body["access_token"], str)
    assert student_body["token_type"] == "bearer"
    assert_exact_keys(student_body["student"], {"id", "name", "email", "course_id"})
    assert isinstance(student_body["student"]["id"], int)
    assert isinstance(student_body["student"]["name"], str)
    assert isinstance(student_body["student"]["email"], str)
    assert isinstance(student_body["student"]["course_id"], int)


def test_frontend_join_link_contract_matches_student_join_page(
    api,
    teacher_account,
    course,
):
    link_response = api.generate_join_link(
        teacher_headers=teacher_account["headers"],
        course_id=course["id"],
    )
    assert link_response.status_code == 200
    link_body = link_response.json()
    assert_exact_keys(link_body, {"course_id", "join_token", "join_url"})
    assert link_body["course_id"] == course["id"]
    assert isinstance(link_body["join_token"], str)
    assert link_body["join_url"] == f"http://testserver/student/join/{link_body['join_token']}"

    info_response = api.get_join_info(join_token=link_body["join_token"])
    assert info_response.status_code == 200
    info_body = info_response.json()
    assert_exact_keys(info_body, {"course_id", "course_name", "teacher_name"})
    assert info_body["course_id"] == course["id"]
    assert isinstance(info_body["course_name"], str)
    assert isinstance(info_body["teacher_name"], str)

    register_response = api.register_via_join_link(
        join_token=link_body["join_token"],
        name="Join UI Student",
        email="join-ui-student@example.com",
        password="pw123456",
    )
    assert register_response.status_code == 201
    register_body = register_response.json()
    assert_exact_keys(register_body, {"student_id", "course_id", "email", "access_token", "token_type"})
    assert isinstance(register_body["student_id"], int)
    assert register_body["course_id"] == course["id"]
    assert register_body["email"] == "join-ui-student@example.com"
    assert register_body["access_token"] is None
    assert register_body["token_type"] is None


def test_frontend_course_assignment_list_contract_matches_teacher_assignments_page(
    api,
    teacher_account,
    course,
):
    first_response = api.client.post(
        f"/courses/{course['id']}/assignments",
        headers=teacher_account["headers"],
        json={
            "title": "较早作业",
            "description": "带截止日期",
            "due_date": "2026-03-20T12:00:00Z",
            "max_score": 120,
        },
    )
    second_response = api.client.post(
        f"/courses/{course['id']}/assignments",
        headers=teacher_account["headers"],
        json={
            "title": "最新作业",
            "description": None,
            "max_score": 100,
        },
    )
    response = api.list_assignments_for_course(
        teacher_headers=teacher_account["headers"],
        course_id=course["id"],
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert response.status_code == 200

    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 2
    assert [item["title"] for item in body] == ["最新作业", "较早作业"]

    newest_item = body[0]
    older_item = body[1]
    for item in body:
        assert_exact_keys(
            item,
            {"id", "teacher_id", "course_id", "title", "description", "due_date", "max_score", "created_at"},
        )
        assert isinstance(item["id"], int)
        assert isinstance(item["teacher_id"], int)
        assert isinstance(item["course_id"], int)
        assert isinstance(item["title"], str)
        assert item["description"] is None or isinstance(item["description"], str)
        assert item["due_date"] is None or isinstance(item["due_date"], str)
        assert item["max_score"] is None or isinstance(item["max_score"], (int, float))
        assert_iso_datetime(item["created_at"])

    assert newest_item["description"] is None
    assert newest_item["due_date"] is None
    assert_number(newest_item["max_score"])
    assert older_item["description"] == "带截止日期"
    assert older_item["due_date"] == "2026-03-20T12:00:00Z"
    assert older_item["max_score"] == 120.0


def test_frontend_teacher_submission_views_see_uploaded_then_graded_state(
    api,
    teacher_account,
    assignment,
    course,
    student_account,
    stub_successful_grading,
):
    second_student_response = api.create_student(
        teacher_headers=teacher_account["headers"],
        course_id=course["id"],
        name="No Submission Student",
        email="no-submission@example.com",
        password="pw123456",
    )
    assert second_student_response.status_code == 200
    second_student = second_student_response.json()

    api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )
    upload_response = api.upload_submission_as_student(
        student_headers={"Authorization": f"Bearer {api.student_login(email=student_account['email'], password=student_account['password']).json()['access_token']}"},
        assignment_id=assignment["id"],
    )
    assert upload_response.status_code == 201
    submission_id = upload_response.json()["id"]

    before_list_response = api.list_assignment_submissions(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )
    before_status_response = api.list_assignment_student_status(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )

    assert before_list_response.status_code == 200
    before_list = before_list_response.json()
    assert len(before_list) == 1
    submission_item = before_list[0]
    assert_exact_keys(
        submission_item,
        {"id", "assignment_id", "student_id", "original_filename", "status", "created_at", "graded_at"},
    )
    assert submission_item["id"] == submission_id
    assert submission_item["status"] == "uploaded"
    assert submission_item["graded_at"] is None
    assert_iso_datetime(submission_item["created_at"])

    assert before_status_response.status_code == 200
    before_status_items = {item["student_id"]: item for item in before_status_response.json()}
    assert before_status_items[student_account["id"]] == {
        "student_id": student_account["id"],
        "student_name": student_account["name"],
        "student_email": student_account["email"],
        "has_submitted": True,
        "submission_id": submission_id,
        "submission_status": "uploaded",
        "total_score": None,
        "max_total_score": None,
    }
    assert before_status_items[second_student["id"]] == {
        "student_id": second_student["id"],
        "student_name": second_student["name"],
        "student_email": second_student["email"],
        "has_submitted": False,
        "submission_id": None,
        "submission_status": None,
        "total_score": None,
        "max_total_score": None,
    }

    stub_successful_grading()
    grade_response = api.grade_submission(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )
    assert grade_response.status_code == 202

    after_list_response = api.list_assignment_submissions(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )
    after_status_response = api.list_assignment_student_status(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )

    assert after_list_response.status_code == 200
    after_submission_item = after_list_response.json()[0]
    assert after_submission_item["status"] == "graded"
    assert_iso_datetime(after_submission_item["graded_at"])

    assert after_status_response.status_code == 200
    after_status = {item["student_id"]: item for item in after_status_response.json()}[student_account["id"]]
    assert after_status["has_submitted"] is True
    assert after_status["submission_id"] == submission_id
    assert after_status["submission_status"] == "graded"
    assert after_status["total_score"] == 1.5
    assert after_status["max_total_score"] == 2.0


def test_frontend_student_assignment_overview_contract_tracks_manual_review_state(
    api,
    teacher_account,
    student_auth,
    assignment,
    stub_successful_grading,
):
    before_response = api.list_student_overview(student_headers=student_auth["headers"])
    assert before_response.status_code == 200
    before_body = before_response.json()
    assert isinstance(before_body, list)
    assert len(before_body) == 1
    before_item = before_body[0]
    assert_exact_keys(
        before_item,
        {
            "assignment_id",
            "title",
            "description",
            "created_at",
            "due_date",
            "max_score",
            "has_submitted",
            "submission_id",
            "submission_status",
            "total_score",
            "max_total_score",
        },
    )
    assert before_item["assignment_id"] == assignment["id"]
    assert before_item["due_date"] is None
    assert before_item["has_submitted"] is False
    assert before_item["submission_id"] is None
    assert before_item["submission_status"] is None
    assert before_item["total_score"] is None
    assert before_item["max_total_score"] is None

    api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )
    upload_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
    )
    submission_id = upload_response.json()["id"]
    stub_successful_grading(manual_review=True)
    grade_response = api.grade_submission(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )
    assert grade_response.status_code == 202

    after_response = api.list_student_overview(student_headers=student_auth["headers"])
    assert after_response.status_code == 200
    after_item = after_response.json()[0]
    assert after_item["due_date"] is None
    assert after_item["has_submitted"] is True
    assert after_item["submission_id"] == submission_id
    assert after_item["submission_status"] == "needs_manual_review"
    assert after_item["total_score"] == 1.0
    assert after_item["max_total_score"] == 2.0


def test_frontend_grade_and_result_contracts_match_modal_and_workspace_usage(
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

    before_result_response = api.get_submission_result(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )
    assert before_result_response.status_code == 404
    assert before_result_response.json() == {"detail": "该 submission 尚未完成评分。"}

    grade_response = api.grade_submission(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )
    # TestClient runs BackgroundTasks to completion before .post() returns,
    # so the background grading job has already finished by the time we
    # fetch the result below.
    result_response = api.get_submission_result(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )

    assert grade_response.status_code == 202
    grade_body = grade_response.json()
    assert_exact_keys(grade_body, {"submission_id", "status"})
    assert grade_body["submission_id"] == submission_id
    assert grade_body["status"] == "grading"

    assert result_response.status_code == 200
    result_body = result_response.json()
    assert_exact_keys(
        result_body,
        {"submission_id", "status", "model_name", "graded_at", "questions", "total_score", "max_total_score"},
    )
    assert result_body["submission_id"] == submission_id
    assert result_body["status"] == "needs_manual_review"
    assert isinstance(result_body["model_name"], str)
    assert result_body["model_name"]
    assert_iso_datetime(result_body["graded_at"])
    assert_number(result_body["total_score"])
    assert_number(result_body["max_total_score"])
    assert isinstance(result_body["questions"], list)
    assert len(result_body["questions"]) == 2
    for index, question in enumerate(result_body["questions"]):
        assert_grade_question_shape(question, nullable_result=index == 1)
        assert isinstance(question["comment"], str)
        assert question["comment"].startswith(f"[Q{index + 1}] ")


def test_frontend_critical_error_contracts_remain_json_detail_strings(
    api,
    teacher_account,
    student_auth,
    assignment,
):
    invalid_teacher_entry_response = api.teacher_entry(
        name="",
        email=teacher_account["email"],
        password="bad-password",
    )
    invalid_student_login_response = api.student_login(
        email=student_auth["student"]["email"],
        password="bad-password",
    )
    invalid_token_response = api.client.get(
        "/teachers/me/courses",
        headers={"Authorization": "Bearer invalid-token"},
    )
    invalid_join_token_response = api.get_join_info(join_token="invalid-token")
    submission_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
    )
    grading_without_solution_response = api.grade_submission(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_response.json()["id"],
    )

    for response, status_code, message in [
        (invalid_teacher_entry_response, 401, "邮箱或密码错误。"),
        (invalid_student_login_response, 401, "邮箱或密码错误。"),
        (invalid_token_response, 401, "Token 无效或已过期。"),
        (invalid_join_token_response, 404, "链接无效或班级不存在。"),
        (grading_without_solution_response, 400, "该 assignment 尚未上传官方答案文件。"),
    ]:
        assert response.status_code == status_code
        assert "application/json" in response.headers["content-type"]
        body = response.json()
        assert_exact_keys(body, {"detail"})
        assert isinstance(body["detail"], str)
        assert body["detail"] == message
