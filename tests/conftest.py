from __future__ import annotations

import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import close_all_sessions


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTEST_RUNTIME_DIR = REPO_ROOT / ".pytest_runtime"
PYTEST_RUNTIME_DIR.mkdir(exist_ok=True)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ["DATABASE_URL"] = f"sqlite:///{(PYTEST_RUNTIME_DIR / 'backend_test.sqlite3').as_posix()}"
os.environ["AUTH_SECRET_KEY"] = "pytest-auth-secret"
os.environ.setdefault("FRONTEND_BASE_URL", "http://testserver")

import grading_service
import main
import student_images
from db import Base, SessionLocal, engine


engine.echo = False


def _make_minimal_pdf() -> bytes:
    """Generate a minimal valid single-page PDF in memory."""
    import fitz
    import io
    doc = fitz.open()
    doc.new_page()
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _make_minimal_docx() -> bytes:
    """Generate a minimal valid DOCX in memory."""
    from docx import Document
    import io
    doc = Document()
    doc.add_paragraph("Solution")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


MINIMAL_PDF_BYTES = _make_minimal_pdf()
MINIMAL_DOCX_BYTES = _make_minimal_docx()


def _build_grading_payload(*, manual_review: bool = False) -> dict[str, Any]:
    second_question = {
        "question_id": "Q2",
        "question_number": 2,
        "question_match": True,
        "question_match_confidence": 0.98,
        "auto_graded": True,
        "score": 0.5,
        "max_score": 1.0,
        "is_correct": False,
        "comment": "部分正确。",
    }
    if manual_review:
        second_question = {
            "question_id": "Q2",
            "question_number": 2,
            "question_match": False,
            "question_match_confidence": 0.45,
            "auto_graded": False,
            "score": None,
            "max_score": 1.0,
            "is_correct": None,
            "comment": "需要人工复核。",
        }

    return {
        "raw_model_json": {
            "questions": [
                {"question_id": "Q1"},
                {"question_id": "Q2"},
            ]
        },
        "normalized": {
            "questions": [
                {
                    "question_id": "Q1",
                    "question_number": 1,
                    "question_match": True,
                    "question_match_confidence": 0.99,
                    "auto_graded": True,
                    "score": 1.0,
                    "max_score": 1.0,
                    "is_correct": True,
                    "comment": "答案正确。",
                },
                second_question,
            ],
            "summary": {
                "total_score": 1.0 if manual_review else 1.5,
                "max_total_score": 2.0,
                "needs_manual_review": manual_review,
            },
        },
        "model_meta": {"model_name": "stub-vision-model", "provider": "stub"},
    }


@pytest.fixture(autouse=True)
def reset_database() -> None:
    close_all_sessions()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    close_all_sessions()


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> None:
    main._auth_limiter._hits.clear()


@pytest.fixture(autouse=True)
def isolate_runtime_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app_data_dir = tmp_path / "app_data"
    monkeypatch.setattr(main, "APP_DATA_DIR", app_data_dir)
    monkeypatch.setattr(main, "SOLUTIONS_DIR", app_data_dir / "solutions")
    monkeypatch.setattr(main, "SUBMISSIONS_DIR", app_data_dir / "submissions")
    monkeypatch.setattr(main, "TEACHER_CACHE_DIR", app_data_dir / "teacher")
    monkeypatch.setattr(main, "STUDENT_TMP_DIR", app_data_dir / "tmp" / "submissions")
    monkeypatch.setattr(grading_service, "TEACHER_CACHE_ROOT", app_data_dir / "teacher")
    monkeypatch.setattr(student_images, "STUDENT_TMP_ROOT", app_data_dir / "tmp" / "submissions")
    main.initialize_app()
    yield


@pytest.fixture
def stub_successful_grading(monkeypatch: pytest.MonkeyPatch):
    def apply(*, manual_review: bool = False) -> dict[str, Any]:
        payload = _build_grading_payload(manual_review=manual_review)
        calls: list[dict[str, Any]] = []

        def fake_auto_grade_homework(**_: Any) -> dict[str, Any]:
            calls.append(deepcopy(_))
            return deepcopy(payload)

        monkeypatch.setattr(grading_service, "auto_grade_homework", fake_auto_grade_homework)
        return {"payload": payload, "calls": calls}

    return apply


@pytest.fixture
def stub_failed_grading(monkeypatch: pytest.MonkeyPatch):
    def apply(message: str = "mock grade failure") -> dict[str, Any]:
        calls: list[dict[str, Any]] = []

        def fake_auto_grade_homework(**_: Any) -> dict[str, Any]:
            calls.append(deepcopy(_))
            raise RuntimeError(message)

        monkeypatch.setattr(grading_service, "auto_grade_homework", fake_auto_grade_homework)
        return {"message": message, "calls": calls}

    return apply


@pytest.fixture
def client() -> TestClient:
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture
def db_session_factory():
    return SessionLocal


class ApiHelper:
    def __init__(self, client: TestClient):
        self.client = client

    @staticmethod
    def auth_headers(access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}

    def bootstrap_teacher(
        self,
        *,
        name: str = "Test Teacher",
        email: str = "teacher@example.com",
        password: str = "pw123456",
    ):
        return self.client.post(
            "/auth/bootstrap-teacher",
            json={"name": name, "email": email, "password": password},
        )

    def teacher_entry(
        self,
        *,
        name: str,
        email: str,
        password: str = "pw123456",
    ):
        return self.client.post(
            "/auth/teacher/entry",
            json={"name": name, "email": email, "password": password},
        )

    def teacher_login(self, *, email: str, password: str):
        return self.client.post(
            "/auth/teacher/login",
            json={"email": email, "password": password},
        )

    def student_login(self, *, email: str, password: str):
        return self.client.post(
            "/auth/student/login",
            json={"email": email, "password": password},
        )

    def create_course(self, *, teacher_headers: dict[str, str], name: str = "七年级数学"):
        return self.client.post(
            "/teachers/me/courses",
            headers=teacher_headers,
            json={"name": name, "description": "测试班级"},
        )

    def list_my_courses(self, *, teacher_headers: dict[str, str]):
        return self.client.get("/teachers/me/courses", headers=teacher_headers)

    def generate_join_link(self, *, teacher_headers: dict[str, str], course_id: int):
        return self.client.post(
            f"/courses/{course_id}/join-link",
            headers=teacher_headers,
        )

    def get_join_info(self, *, join_token: str):
        return self.client.get(f"/courses/join/{join_token}")

    def register_via_join_link(
        self,
        *,
        join_token: str,
        name: str,
        email: str,
        password: str = "pw123456",
    ):
        return self.client.post(
            f"/courses/join/{join_token}/register",
            json={"name": name, "email": email, "password": password},
        )

    def create_student(
        self,
        *,
        teacher_headers: dict[str, str],
        course_id: int,
        name: str,
        email: str,
        password: str = "pw123456",
    ):
        return self.client.post(
            f"/courses/{course_id}/students",
            headers=teacher_headers,
            json={"name": name, "email": email, "password": password},
        )

    def create_assignment(
        self,
        *,
        teacher_headers: dict[str, str],
        course_id: int,
        title: str = "第一次作业",
    ):
        return self.client.post(
            f"/courses/{course_id}/assignments",
            headers=teacher_headers,
            json={"title": title, "description": "测试作业", "max_score": 100},
        )

    def list_assignments(self, *, teacher_headers: dict[str, str]):
        return self.client.get("/assignments", headers=teacher_headers)

    def list_assignments_for_course(self, *, teacher_headers: dict[str, str], course_id: int):
        return self.client.get(f"/courses/{course_id}/assignments", headers=teacher_headers)

    def upload_solution(
        self,
        *,
        teacher_headers: dict[str, str],
        assignment_id: int,
        filename: str = "solution.docx",
        content: bytes = MINIMAL_DOCX_BYTES,
        content_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ):
        return self.client.post(
            f"/assignments/{assignment_id}/solution",
            headers=teacher_headers,
            files={"file": (filename, content, content_type)},
        )

    def upload_solution_legacy(
        self,
        *,
        teacher_headers: dict[str, str],
        teacher_id: int,
        assignment_id: int,
        filename: str = "solution.docx",
        content: bytes = MINIMAL_DOCX_BYTES,
        content_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ):
        return self.client.post(
            f"/teachers/{teacher_id}/assignments/{assignment_id}/solution",
            headers=teacher_headers,
            files={"file": (filename, content, content_type)},
        )

    def upload_submission_as_student(
        self,
        *,
        student_headers: dict[str, str],
        assignment_id: int,
        filename: str = "submission.pdf",
        content: bytes = MINIMAL_PDF_BYTES,
        content_type: str = "application/pdf",
    ):
        return self.client.post(
            f"/assignments/{assignment_id}/submissions/me",
            headers=student_headers,
            files={"file": (filename, content, content_type)},
        )

    def upload_submission_as_teacher(
        self,
        *,
        teacher_headers: dict[str, str],
        assignment_id: int,
        student_id: int,
        filename: str = "submission.pdf",
        content: bytes = MINIMAL_PDF_BYTES,
        content_type: str = "application/pdf",
    ):
        return self.client.post(
            f"/assignments/{assignment_id}/submissions",
            headers=teacher_headers,
            data={"student_id": str(student_id)},
            files={"file": (filename, content, content_type)},
        )

    def list_assignment_submissions(self, *, teacher_headers: dict[str, str], assignment_id: int):
        return self.client.get(
            f"/assignments/{assignment_id}/submissions",
            headers=teacher_headers,
        )

    def list_student_overview(self, *, student_headers: dict[str, str]):
        return self.client.get("/students/me/assignments", headers=student_headers)

    def list_assignment_student_status(self, *, teacher_headers: dict[str, str], assignment_id: int):
        return self.client.get(
            f"/assignments/{assignment_id}/students-status",
            headers=teacher_headers,
        )

    def grade_submission(self, *, teacher_headers: dict[str, str], submission_id: int):
        return self.client.post(f"/submissions/{submission_id}/grade", headers=teacher_headers)

    def grade_all(self, *, teacher_headers: dict[str, str], assignment_id: int):
        return self.client.post(
            f"/assignments/{assignment_id}/grade-all",
            headers=teacher_headers,
        )

    def get_submission_result(self, *, teacher_headers: dict[str, str], submission_id: int):
        return self.client.get(
            f"/submissions/{submission_id}/result",
            headers=teacher_headers,
        )


@pytest.fixture
def api(client: TestClient) -> ApiHelper:
    return ApiHelper(client)


@pytest.fixture
def teacher_account(api: ApiHelper) -> dict[str, Any]:
    email = "teacher@example.com"
    password = "pw123456"
    response = api.bootstrap_teacher(email=email, password=password)
    assert response.status_code == 200
    payload = response.json()
    payload["email"] = email
    payload["password"] = password
    payload["headers"] = api.auth_headers(payload["access_token"])
    return payload


@pytest.fixture
def second_teacher_account(api: ApiHelper, teacher_account: dict[str, Any]) -> dict[str, Any]:
    email = "teacher2@example.com"
    password = "pw123456"
    response = api.teacher_entry(name="Second Teacher", email=email, password=password)
    assert response.status_code == 200
    payload = response.json()
    payload["email"] = email
    payload["password"] = password
    payload["headers"] = api.auth_headers(payload["access_token"])
    return payload


@pytest.fixture
def course(api: ApiHelper, teacher_account: dict[str, Any]) -> dict[str, Any]:
    response = api.create_course(teacher_headers=teacher_account["headers"])
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def assignment(api: ApiHelper, teacher_account: dict[str, Any], course: dict[str, Any]) -> dict[str, Any]:
    response = api.create_assignment(
        teacher_headers=teacher_account["headers"],
        course_id=course["id"],
    )
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def student_account(
    api: ApiHelper,
    teacher_account: dict[str, Any],
    course: dict[str, Any],
) -> dict[str, Any]:
    email = "student@example.com"
    password = "pw123456"
    response = api.create_student(
        teacher_headers=teacher_account["headers"],
        course_id=course["id"],
        name="测试学生",
        email=email,
        password=password,
    )
    assert response.status_code == 200
    payload = response.json()
    payload["email"] = email
    payload["password"] = password
    return payload


@pytest.fixture
def student_auth(api: ApiHelper, student_account: dict[str, Any]) -> dict[str, Any]:
    response = api.student_login(
        email=student_account["email"],
        password=student_account["password"],
    )
    assert response.status_code == 200
    payload = response.json()
    payload["headers"] = api.auth_headers(payload["access_token"])
    return payload
