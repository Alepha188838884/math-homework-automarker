from __future__ import annotations

from pathlib import Path

import main
from models import AnswerFile, Course, Student, Submission


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def fixture_path(name: str) -> Path:
    return FIXTURES_DIR / name


def _has_any_file(root: Path) -> bool:
    if not root.exists():
        return False
    return any(path.is_file() for path in root.rglob("*"))


def test_join_link_registration_flow_creates_student_and_rotates_old_token(
    api,
    teacher_account,
    course,
    db_session_factory,
):
    first_link_response = api.generate_join_link(
        teacher_headers=teacher_account["headers"],
        course_id=course["id"],
    )
    assert first_link_response.status_code == 200
    first_link_body = first_link_response.json()
    assert set(first_link_body) == {"course_id", "join_token", "join_url"}
    assert first_link_body["course_id"] == course["id"]
    assert isinstance(first_link_body["join_token"], str)
    assert first_link_body["join_token"]
    assert first_link_body["join_url"] == f"http://testserver/student/join/{first_link_body['join_token']}"

    first_info_response = api.get_join_info(join_token=first_link_body["join_token"])
    assert first_info_response.status_code == 200
    assert first_info_response.json() == {
        "course_id": course["id"],
        "course_name": course["name"],
        "teacher_name": teacher_account["teacher"]["name"],
    }

    second_link_response = api.generate_join_link(
        teacher_headers=teacher_account["headers"],
        course_id=course["id"],
    )
    assert second_link_response.status_code == 200
    second_link_body = second_link_response.json()
    assert second_link_body["course_id"] == course["id"]
    assert second_link_body["join_token"] != first_link_body["join_token"]
    assert second_link_body["join_url"] == f"http://testserver/student/join/{second_link_body['join_token']}"

    stale_info_response = api.get_join_info(join_token=first_link_body["join_token"])
    assert stale_info_response.status_code == 404
    assert stale_info_response.json() == {"detail": "链接无效或班级不存在。"}

    register_response = api.register_via_join_link(
        join_token=second_link_body["join_token"],
        name="Join Student",
        email="join-student@example.com",
        password="pw123456",
    )
    assert register_response.status_code == 201
    register_body = register_response.json()
    assert set(register_body) == {"student_id", "course_id", "email", "access_token", "token_type"}
    assert register_body["course_id"] == course["id"]
    assert register_body["email"] == "join-student@example.com"
    assert register_body["access_token"] is None
    assert register_body["token_type"] is None

    login_response = api.student_login(email="join-student@example.com", password="pw123456")
    assert login_response.status_code == 200
    assert login_response.json()["student"]["id"] == register_body["student_id"]

    with db_session_factory() as db:
        saved_course = db.get(Course, course["id"])
        student = db.get(Student, register_body["student_id"])
        assert saved_course is not None
        assert saved_course.join_token == second_link_body["join_token"]
        assert student is not None
        assert student.course_id == course["id"]
        assert student.email == "join-student@example.com"


def test_join_link_generation_and_registration_fail_without_side_effects(
    api,
    teacher_account,
    second_teacher_account,
    student_auth,
    course,
    db_session_factory,
):
    unauthorized_response = api.client.post(
        f"/courses/{course['id']}/join-link",
        headers=student_auth["headers"],
    )
    assert unauthorized_response.status_code == 401
    assert unauthorized_response.json() == {"detail": "教师认证失败。"}

    forbidden_response = api.generate_join_link(
        teacher_headers=second_teacher_account["headers"],
        course_id=course["id"],
    )
    assert forbidden_response.status_code == 403
    assert forbidden_response.json() == {"detail": "该课程不属于当前老师。"}

    invalid_info_response = api.get_join_info(join_token="invalid-token")
    assert invalid_info_response.status_code == 404
    assert invalid_info_response.json() == {"detail": "链接无效或班级不存在。"}

    invalid_register_response = api.register_via_join_link(
        join_token="invalid-token",
        name="Ghost Student",
        email="ghost@example.com",
        password="pw123456",
    )
    assert invalid_register_response.status_code == 404
    assert invalid_register_response.json() == {"detail": "链接无效或班级不存在。"}

    join_link_response = api.generate_join_link(
        teacher_headers=teacher_account["headers"],
        course_id=course["id"],
    )
    join_token = join_link_response.json()["join_token"]
    first_register_response = api.register_via_join_link(
        join_token=join_token,
        name="First Join Student",
        email="duplicate-join@example.com",
        password="pw123456",
    )
    duplicate_register_response = api.register_via_join_link(
        join_token=join_token,
        name="Duplicate Join Student",
        email="duplicate-join@example.com",
        password="pw123456",
    )

    assert first_register_response.status_code == 201
    assert duplicate_register_response.status_code == 400
    assert duplicate_register_response.json() == {"detail": "学生邮箱已存在。"}

    with db_session_factory() as db:
        students = db.query(Student).filter(Student.email == "duplicate-join@example.com").all()
        assert len(students) == 1
        assert db.query(Student).filter(Student.email == "ghost@example.com").count() == 0


def test_teacher_can_upload_submission_for_student_and_students_status_tracks_progress(
    api,
    teacher_account,
    assignment,
    course,
    student_account,
    stub_successful_grading,
    db_session_factory,
):
    extra_student_response = api.create_student(
        teacher_headers=teacher_account["headers"],
        course_id=course["id"],
        name="Second Student",
        email="second-student@example.com",
        password="pw123456",
    )
    assert extra_student_response.status_code == 200
    extra_student = extra_student_response.json()

    solution_bytes = fixture_path("valid_solution.docx").read_bytes()
    pdf_bytes = fixture_path("valid_submission.pdf").read_bytes()

    solution_response = api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
        filename="valid_solution.docx",
        content=solution_bytes,
    )
    assert solution_response.status_code == 200

    upload_response = api.upload_submission_as_teacher(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
        student_id=student_account["id"],
        filename="teacher-uploaded.pdf",
        content=pdf_bytes,
    )
    assert upload_response.status_code == 201
    upload_body = upload_response.json()
    assert set(upload_body) == {
        "id",
        "assignment_id",
        "student_id",
        "original_filename",
        "file_path",
        "qwen_file_id",
        "status",
        "error_message",
        "created_at",
        "updated_at",
        "graded_at",
    }
    assert upload_body["assignment_id"] == assignment["id"]
    assert upload_body["student_id"] == student_account["id"]
    assert upload_body["original_filename"] == "teacher-uploaded.pdf"
    assert upload_body["status"] == "uploaded"
    assert upload_body["error_message"] is None
    assert upload_body["graded_at"] is None
    assert upload_body["qwen_file_id"] is None
    assert Path(upload_body["file_path"]).read_bytes() == pdf_bytes

    status_response = api.list_assignment_student_status(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )
    assert status_response.status_code == 200
    status_items = {item["student_id"]: item for item in status_response.json()}
    assert set(status_items) == {student_account["id"], extra_student["id"]}

    uploaded_status = status_items[student_account["id"]]
    assert uploaded_status == {
        "student_id": student_account["id"],
        "student_name": student_account["name"],
        "student_email": student_account["email"],
        "has_submitted": True,
        "submission_id": upload_body["id"],
        "submission_status": "uploaded",
        "total_score": None,
        "max_total_score": None,
    }
    missing_status = status_items[extra_student["id"]]
    assert missing_status == {
        "student_id": extra_student["id"],
        "student_name": extra_student["name"],
        "student_email": extra_student["email"],
        "has_submitted": False,
        "submission_id": None,
        "submission_status": None,
        "total_score": None,
        "max_total_score": None,
    }

    stub_successful_grading()
    grade_response = api.grade_submission(
        teacher_headers=teacher_account["headers"],
        submission_id=upload_body["id"],
    )
    assert grade_response.status_code == 200

    graded_status_response = api.list_assignment_student_status(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )
    assert graded_status_response.status_code == 200
    graded_status = {item["student_id"]: item for item in graded_status_response.json()}[student_account["id"]]
    assert graded_status["submission_status"] == "graded"
    assert graded_status["total_score"] == 1.5
    assert graded_status["max_total_score"] == 2.0

    with db_session_factory() as db:
        submission = db.get(Submission, upload_body["id"])
        assert submission is not None
        assert submission.assignment_id == assignment["id"]
        assert submission.student_id == student_account["id"]
        assert submission.status == "graded"
        assert submission.error_message is None


def test_teacher_submission_upload_and_students_status_enforce_permissions_and_validation(
    api,
    teacher_account,
    second_teacher_account,
    student_auth,
    assignment,
    course,
    db_session_factory,
):
    other_course_response = api.create_course(
        teacher_headers=teacher_account["headers"],
        name="其他班级",
    )
    assert other_course_response.status_code == 200
    other_course = other_course_response.json()

    outsider_student_response = api.create_student(
        teacher_headers=teacher_account["headers"],
        course_id=other_course["id"],
        name="Outsider Student",
        email="outsider@example.com",
        password="pw123456",
    )
    assert outsider_student_response.status_code == 200
    outsider_student = outsider_student_response.json()

    pdf_bytes = fixture_path("valid_submission.pdf").read_bytes()

    unauthorized_upload_response = api.client.post(
        f"/assignments/{assignment['id']}/submissions",
        headers=student_auth["headers"],
        data={"student_id": str(outsider_student["id"])},
        files={"file": ("teacher-uploaded.pdf", pdf_bytes, "application/pdf")},
    )
    assert unauthorized_upload_response.status_code == 401
    assert unauthorized_upload_response.json() == {"detail": "教师认证失败。"}

    forbidden_upload_response = api.upload_submission_as_teacher(
        teacher_headers=second_teacher_account["headers"],
        assignment_id=assignment["id"],
        student_id=outsider_student["id"],
        filename="teacher-uploaded.pdf",
        content=pdf_bytes,
    )
    assert forbidden_upload_response.status_code == 403
    assert forbidden_upload_response.json() == {"detail": "该作业不属于当前老师。"}

    missing_student_response = api.upload_submission_as_teacher(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
        student_id=999999,
        filename="teacher-uploaded.pdf",
        content=pdf_bytes,
    )
    assert missing_student_response.status_code == 404
    assert missing_student_response.json() == {"detail": "Student 999999 不存在。"}

    wrong_course_response = api.upload_submission_as_teacher(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
        student_id=outsider_student["id"],
        filename="teacher-uploaded.pdf",
        content=pdf_bytes,
    )
    assert wrong_course_response.status_code == 400
    assert wrong_course_response.json() == {"detail": "student 与 assignment 不属于同一课程。"}

    invalid_type_response = api.upload_submission_as_teacher(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
        student_id=outsider_student["id"],
        filename="notes.txt",
        content=b"notes",
        content_type="text/plain",
    )
    assert invalid_type_response.status_code == 400
    assert invalid_type_response.json() == {"detail": "学生作业必须是 .pdf 文件。"}

    unauthorized_status_response = api.client.get(
        f"/assignments/{assignment['id']}/students-status",
        headers=student_auth["headers"],
    )
    assert unauthorized_status_response.status_code == 401
    assert unauthorized_status_response.json() == {"detail": "教师认证失败。"}

    forbidden_status_response = api.list_assignment_student_status(
        teacher_headers=second_teacher_account["headers"],
        assignment_id=assignment["id"],
    )
    assert forbidden_status_response.status_code == 403
    assert forbidden_status_response.json() == {"detail": "该作业不属于当前老师。"}

    with db_session_factory() as db:
        assert db.query(Submission).count() == 0
    assert not _has_any_file(main.SUBMISSIONS_DIR)


def test_legacy_solution_upload_path_persists_answer_file_and_bytes(
    api,
    teacher_account,
    assignment,
    db_session_factory,
):
    solution_bytes = fixture_path("valid_solution.docx").read_bytes()

    response = api.upload_solution_legacy(
        teacher_headers=teacher_account["headers"],
        teacher_id=teacher_account["teacher"]["id"],
        assignment_id=assignment["id"],
        filename="legacy-solution.docx",
        content=solution_bytes,
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "id",
        "assignment_id",
        "original_filename",
        "file_path",
        "qwen_file_id",
        "uploaded_at",
        "updated_at",
    }
    assert body["assignment_id"] == assignment["id"]
    assert body["original_filename"] == "legacy-solution.docx"
    assert body["qwen_file_id"] is None
    assert Path(body["file_path"]).read_bytes() == solution_bytes

    with db_session_factory() as db:
        answer_files = db.query(AnswerFile).all()
        assert len(answer_files) == 1
        answer_file = answer_files[0]
        assert answer_file.id == body["id"]
        assert answer_file.assignment_id == assignment["id"]
        assert answer_file.qwen_file_id is None
        assert Path(answer_file.file_path).read_bytes() == solution_bytes


def test_legacy_solution_upload_enforces_teacher_identity_and_validation_without_side_effects(
    api,
    teacher_account,
    second_teacher_account,
    student_auth,
    assignment,
    db_session_factory,
):
    solution_bytes = fixture_path("valid_solution.docx").read_bytes()

    mismatched_teacher_response = api.upload_solution_legacy(
        teacher_headers=teacher_account["headers"],
        teacher_id=second_teacher_account["teacher"]["id"],
        assignment_id=assignment["id"],
        filename="legacy-solution.docx",
        content=solution_bytes,
    )
    assert mismatched_teacher_response.status_code == 403
    assert mismatched_teacher_response.json() == {"detail": "teacher_id 与当前登录老师不一致。"}

    forbidden_assignment_response = api.upload_solution_legacy(
        teacher_headers=second_teacher_account["headers"],
        teacher_id=second_teacher_account["teacher"]["id"],
        assignment_id=assignment["id"],
        filename="legacy-solution.docx",
        content=solution_bytes,
    )
    assert forbidden_assignment_response.status_code == 403
    assert forbidden_assignment_response.json() == {"detail": "该作业不属于当前老师。"}

    unauthorized_response = api.client.post(
        f"/teachers/{teacher_account['teacher']['id']}/assignments/{assignment['id']}/solution",
        headers=student_auth["headers"],
        files={"file": ("legacy-solution.docx", solution_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert unauthorized_response.status_code == 401
    assert unauthorized_response.json() == {"detail": "教师认证失败。"}

    invalid_type_response = api.upload_solution_legacy(
        teacher_headers=teacher_account["headers"],
        teacher_id=teacher_account["teacher"]["id"],
        assignment_id=assignment["id"],
        filename="notes.txt",
        content=b"notes",
        content_type="text/plain",
    )
    assert invalid_type_response.status_code == 400
    assert invalid_type_response.json() == {"detail": "官方答案必须是 .docx 或 .pdf 文件。"}

    with db_session_factory() as db:
        assert db.query(AnswerFile).count() == 0
    assert not _has_any_file(main.SOLUTIONS_DIR)
