from __future__ import annotations

from models import AnswerFile, Assignment, GradeResult


def test_student_cannot_access_teacher_only_route(api, student_auth, course, db_session_factory):
    response = api.client.post(
        f"/courses/{course['id']}/assignments",
        headers=student_auth["headers"],
        json={"title": "非法创建"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "教师认证失败。"}

    with db_session_factory() as db:
        assert db.query(Assignment).count() == 0


def test_teacher_cannot_access_student_only_route(api, teacher_account):
    response = api.client.get(
        "/students/me/assignments",
        headers=teacher_account["headers"],
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "学生认证失败。"}


def test_cross_teacher_assignment_access_is_forbidden(
    api,
    teacher_account,
    second_teacher_account,
    assignment,
):
    owner_response = api.list_assignment_submissions(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )
    response = api.list_assignment_submissions(
        teacher_headers=second_teacher_account["headers"],
        assignment_id=assignment["id"],
    )

    assert owner_response.status_code == 200
    assert owner_response.json() == []
    assert response.status_code == 403
    assert response.json() == {"detail": "该作业不属于当前老师。"}


def test_missing_file_and_bad_extension_return_expected_errors(
    api,
    teacher_account,
    student_auth,
    assignment,
    db_session_factory,
):
    bad_solution_response = api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
        filename="bad.txt",
        content_type="text/plain",
    )
    missing_file_response = api.client.post(
        f"/assignments/{assignment['id']}/submissions/me",
        headers=student_auth["headers"],
    )

    assert bad_solution_response.status_code == 400
    assert bad_solution_response.json() == {"detail": "官方答案必须是 .docx 文件。"}

    assert missing_file_response.status_code == 422
    body = missing_file_response.json()
    assert body["detail"][0]["type"] == "missing"
    assert body["detail"][0]["loc"] == ["body", "file"]

    with db_session_factory() as db:
        assert db.query(AnswerFile).count() == 0


def test_missing_resources_and_ungraded_result_paths_return_expected_errors(
    api,
    teacher_account,
    student_auth,
    assignment,
    db_session_factory,
):
    missing_assignment_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=999999,
    )
    upload_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
    )
    submission_id = upload_response.json()["id"]
    ungraded_result_response = api.get_submission_result(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )
    missing_submission_response = api.grade_submission(
        teacher_headers=teacher_account["headers"],
        submission_id=999999,
    )

    assert missing_assignment_response.status_code == 404
    assert missing_assignment_response.json() == {"detail": "Assignment 999999 不存在。"}
    assert upload_response.status_code == 201

    assert ungraded_result_response.status_code == 404
    assert ungraded_result_response.json() == {"detail": "该 submission 尚未完成评分。"}

    assert missing_submission_response.status_code == 404
    assert missing_submission_response.json() == {"detail": "Submission 999999 不存在。"}

    with db_session_factory() as db:
        assert db.query(GradeResult).count() == 0
