from __future__ import annotations


def test_due_date_is_normalized_to_utc_z_across_live_assignment_endpoints(
    api,
    teacher_account,
    course,
    student_auth,
):
    create_response = api.client.post(
        f"/courses/{course['id']}/assignments",
        headers=teacher_account["headers"],
        json={
            "title": "带时区作业",
            "description": "due_date should be normalized to UTC",
            "due_date": "2026-03-20T20:30:00+08:00",
            "max_score": 100,
        },
    )
    assert create_response.status_code == 200
    create_body = create_response.json()
    assignment_id = create_body["id"]
    expected_due_date = "2026-03-20T12:30:00Z"

    assert create_body["due_date"] == expected_due_date

    course_list_response = api.list_assignments_for_course(
        teacher_headers=teacher_account["headers"],
        course_id=course["id"],
    )
    assert course_list_response.status_code == 200
    assert course_list_response.json()[0]["id"] == assignment_id
    assert course_list_response.json()[0]["due_date"] == expected_due_date

    teacher_list_response = api.list_assignments(teacher_headers=teacher_account["headers"])
    assert teacher_list_response.status_code == 200
    assert teacher_list_response.json()[0]["id"] == assignment_id
    assert teacher_list_response.json()[0]["due_date"] == expected_due_date

    student_overview_response = api.list_student_overview(student_headers=student_auth["headers"])
    assert student_overview_response.status_code == 200
    overview_item = next(item for item in student_overview_response.json() if item["assignment_id"] == assignment_id)
    assert overview_item["due_date"] == expected_due_date


def test_due_date_null_remains_null_across_live_assignment_endpoints(
    api,
    teacher_account,
    course,
    student_auth,
):
    create_response = api.client.post(
        f"/courses/{course['id']}/assignments",
        headers=teacher_account["headers"],
        json={
            "title": "无截止日期作业",
            "description": None,
            "max_score": 100,
        },
    )
    assert create_response.status_code == 200
    create_body = create_response.json()
    assignment_id = create_body["id"]

    assert create_body["due_date"] is None

    course_list_response = api.list_assignments_for_course(
        teacher_headers=teacher_account["headers"],
        course_id=course["id"],
    )
    assert course_list_response.status_code == 200
    assert course_list_response.json()[0]["id"] == assignment_id
    assert course_list_response.json()[0]["due_date"] is None

    teacher_list_response = api.list_assignments(teacher_headers=teacher_account["headers"])
    assert teacher_list_response.status_code == 200
    assert teacher_list_response.json()[0]["id"] == assignment_id
    assert teacher_list_response.json()[0]["due_date"] is None

    student_overview_response = api.list_student_overview(student_headers=student_auth["headers"])
    assert student_overview_response.status_code == 200
    overview_item = next(item for item in student_overview_response.json() if item["assignment_id"] == assignment_id)
    assert overview_item["due_date"] is None
