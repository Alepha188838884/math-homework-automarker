from __future__ import annotations

from auth import decode_token


def test_valid_teacher_login_succeeds(api, teacher_account, course):
    response = api.teacher_login(
        email=teacher_account["email"],
        password=teacher_account["password"],
    )

    assert response.status_code == 200
    body = response.json()
    payload = decode_token(body["access_token"])
    protected_response = api.list_my_courses(
        teacher_headers=api.auth_headers(body["access_token"]),
    )

    assert body["teacher"]["id"] == teacher_account["teacher"]["id"]
    assert body["teacher"]["name"] == teacher_account["teacher"]["name"]
    assert body["teacher"]["email"] == teacher_account["email"]
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert payload["role"] == "teacher"
    assert payload["sub"] == str(body["teacher"]["id"])
    assert protected_response.status_code == 200
    assert protected_response.json()[0]["id"] == course["id"]


def test_valid_student_login_succeeds(api, student_account, assignment):
    response = api.student_login(
        email=student_account["email"],
        password=student_account["password"],
    )

    assert response.status_code == 200
    body = response.json()
    payload = decode_token(body["access_token"])
    protected_response = api.list_student_overview(
        student_headers=api.auth_headers(body["access_token"]),
    )

    assert body["student"]["id"] == student_account["id"]
    assert body["student"]["name"] == student_account["name"]
    assert body["student"]["email"] == student_account["email"]
    assert body["student"]["course_id"] == student_account["course_id"]
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert payload["role"] == "student"
    assert payload["sub"] == str(body["student"]["id"])
    assert protected_response.status_code == 200
    assert protected_response.json()[0]["assignment_id"] == assignment["id"]


def test_invalid_login_fails_correctly(api, student_account):
    response = api.student_login(
        email=student_account["email"],
        password="wrong-password",
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "邮箱或密码错误。"}


def test_invalid_or_expired_token_returns_exact_message(client):
    response = client.get(
        "/teachers/me/courses",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Token 无效或已过期。"}
