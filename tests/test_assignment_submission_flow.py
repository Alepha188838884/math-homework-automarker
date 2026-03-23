from __future__ import annotations

from pathlib import Path

from models import AnswerFile, Submission


def test_teacher_can_create_and_list_courses_and_assignments(
    api,
    teacher_account,
    course,
    assignment,
):
    courses_response = api.list_my_courses(teacher_headers=teacher_account["headers"])
    course_assignments_response = api.list_assignments_for_course(
        teacher_headers=teacher_account["headers"],
        course_id=course["id"],
    )
    all_assignments_response = api.list_assignments(
        teacher_headers=teacher_account["headers"],
    )

    assert courses_response.status_code == 200
    courses = courses_response.json()
    assert len(courses) == 1
    assert courses[0]["id"] == course["id"]
    assert courses[0]["teacher_id"] == teacher_account["teacher"]["id"]
    assert courses[0]["name"] == "七年级数学"
    assert courses[0]["description"] == "测试班级"
    assert courses[0]["created_at"]

    assert course_assignments_response.status_code == 200
    course_assignments = course_assignments_response.json()
    assert len(course_assignments) == 1
    assert course_assignments[0]["id"] == assignment["id"]
    assert course_assignments[0]["teacher_id"] == teacher_account["teacher"]["id"]
    assert course_assignments[0]["course_id"] == course["id"]
    assert course_assignments[0]["title"] == "第一次作业"
    assert course_assignments[0]["description"] == "测试作业"
    assert course_assignments[0]["max_score"] == 100
    assert course_assignments[0]["created_at"]

    assert all_assignments_response.status_code == 200
    all_assignments = all_assignments_response.json()
    assert len(all_assignments) == 1
    assert all_assignments[0]["id"] == assignment["id"]
    assert all_assignments[0]["course_id"] == course["id"]


def test_teacher_can_upload_official_answer_file_and_persist_record(
    api,
    teacher_account,
    assignment,
    db_session_factory,
    qwen_upload_calls,
):
    response = api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] > 0
    assert body["assignment_id"] == assignment["id"]
    assert body["original_filename"] == "solution.docx"
    assert body["qwen_file_id"] == "stub-qwen-file-1"
    assert body["uploaded_at"]
    assert body["updated_at"]
    assert Path(body["file_path"]).exists()
    assert qwen_upload_calls == [str(Path(body["file_path"]).resolve())]

    with db_session_factory() as db:
        answer_file = db.get(AnswerFile, body["id"])
        assert answer_file is not None
        assert answer_file.assignment_id == assignment["id"]
        assert answer_file.original_filename == "solution.docx"
        assert answer_file.qwen_file_id == "stub-qwen-file-1"
        assert Path(answer_file.file_path).exists()


def test_student_submission_appears_in_teacher_list_and_student_overview(
    api,
    teacher_account,
    student_auth,
    assignment,
    db_session_factory,
    qwen_upload_calls,
):
    submit_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
    )
    submissions_response = api.list_assignment_submissions(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )
    overview_response = api.list_student_overview(
        student_headers=student_auth["headers"],
    )

    assert submit_response.status_code == 201
    submit_body = submit_response.json()
    assert submit_body["assignment_id"] == assignment["id"]
    assert submit_body["student_id"] == student_auth["student"]["id"]
    assert submit_body["original_filename"] == "submission.pdf"
    assert submit_body["qwen_file_id"] == "stub-qwen-file-1"
    assert submit_body["status"] == "uploaded"
    assert submit_body["error_message"] is None
    assert submit_body["graded_at"] is None
    assert Path(submit_body["file_path"]).exists()
    assert qwen_upload_calls == [str(Path(submit_body["file_path"]).resolve())]

    assert submissions_response.status_code == 200
    submissions = submissions_response.json()
    assert len(submissions) == 1
    assert submissions[0]["id"] == submit_body["id"]
    assert submissions[0]["original_filename"] == "submission.pdf"
    assert submissions[0]["status"] == "uploaded"

    assert overview_response.status_code == 200
    overview_items = overview_response.json()
    assert len(overview_items) == 1
    assert overview_items[0]["assignment_id"] == assignment["id"]
    assert overview_items[0]["has_submitted"] is True
    assert overview_items[0]["submission_id"] == submit_body["id"]
    assert overview_items[0]["submission_status"] == "uploaded"
    assert overview_items[0]["total_score"] is None
    assert overview_items[0]["max_total_score"] is None

    with db_session_factory() as db:
        submission = db.get(Submission, submit_body["id"])
        assert submission is not None
        assert submission.assignment_id == assignment["id"]
        assert submission.student_id == student_auth["student"]["id"]
        assert submission.status == "uploaded"
        assert submission.qwen_file_id == "stub-qwen-file-1"
        assert submission.error_message is None
        assert Path(submission.file_path).exists()


def test_repeated_submission_overwrites_existing_record(
    api,
    teacher_account,
    student_auth,
    assignment,
    db_session_factory,
    qwen_upload_calls,
):
    first_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
        filename="first.pdf",
        content=b"%PDF first version",
    )
    second_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
        filename="second.pdf",
        content=b"%PDF second version",
    )
    submissions_response = api.list_assignment_submissions(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    first_submission = first_response.json()
    second_submission = second_response.json()
    first_path = Path(first_submission["file_path"])
    second_path = Path(second_submission["file_path"])
    assert second_submission["id"] == first_submission["id"]
    assert second_submission["original_filename"] == "second.pdf"
    assert second_submission["status"] == "uploaded"
    assert second_submission["qwen_file_id"] == "stub-qwen-file-2"
    assert first_submission["qwen_file_id"] == "stub-qwen-file-1"
    assert not first_path.exists()
    assert second_path.exists()
    assert qwen_upload_calls == [str(first_path.resolve()), str(second_path.resolve())]

    submissions = submissions_response.json()
    assert len(submissions) == 1
    assert submissions[0]["id"] == first_submission["id"]
    assert submissions[0]["original_filename"] == "second.pdf"
    assert submissions[0]["status"] == "uploaded"

    with db_session_factory() as db:
        persisted = db.get(Submission, second_submission["id"])
        submission_count = db.query(Submission).count()
        assert persisted is not None
        assert submission_count == 1
        assert persisted.original_filename == "second.pdf"
        assert persisted.file_path == second_submission["file_path"]
        assert persisted.qwen_file_id == "stub-qwen-file-2"
        assert persisted.status == "uploaded"
        assert persisted.graded_at is None
