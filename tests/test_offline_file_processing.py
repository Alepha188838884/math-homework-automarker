from __future__ import annotations

from pathlib import Path

import pytest
import qwen_service
import student_images
import teacher_images
from models import AnswerFile, GradeQuestion, GradeResult, Submission
from PIL import Image


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def fixture_path(name: str) -> Path:
    return FIXTURES_DIR / name


@pytest.fixture
def local_processing_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    teacher_root = tmp_path / "teacher_cache"
    student_root = tmp_path / "student_tmp"
    monkeypatch.setattr(teacher_images, "TEACHER_CACHE_ROOT", teacher_root)
    monkeypatch.setattr(student_images, "STUDENT_TMP_ROOT", student_root)
    return {
        "teacher_root": teacher_root,
        "student_root": student_root,
    }


def test_valid_docx_upload_with_real_fixture_persists_bytes(
    api,
    teacher_account,
    assignment,
    db_session_factory,
):
    source_path = fixture_path("valid_solution.docx")
    source_bytes = source_path.read_bytes()

    response = api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
        filename=source_path.name,
        content=source_bytes,
    )

    assert response.status_code == 200
    body = response.json()
    saved_path = Path(body["file_path"])
    assert saved_path.exists()
    assert saved_path.read_bytes() == source_bytes
    assert body["original_filename"] == "valid_solution.docx"
    assert body["qwen_file_id"] == "stub-qwen-file-1"

    with db_session_factory() as db:
        answer_file = db.get(AnswerFile, body["id"])
        assert answer_file is not None
        assert answer_file.assignment_id == assignment["id"]
        assert Path(answer_file.file_path).read_bytes() == source_bytes


def test_valid_pdf_upload_with_real_fixture_persists_bytes(
    api,
    student_auth,
    assignment,
    db_session_factory,
):
    source_path = fixture_path("valid_submission.pdf")
    source_bytes = source_path.read_bytes()

    response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
        filename=source_path.name,
        content=source_bytes,
    )

    assert response.status_code == 201
    body = response.json()
    saved_path = Path(body["file_path"])
    assert saved_path.exists()
    assert saved_path.read_bytes() == source_bytes
    assert body["original_filename"] == "valid_submission.pdf"
    assert body["status"] == "uploaded"
    assert body["error_message"] is None

    with db_session_factory() as db:
        submission = db.get(Submission, body["id"])
        assert submission is not None
        assert submission.status == "uploaded"
        assert Path(submission.file_path).read_bytes() == source_bytes


def test_unsupported_fixture_file_types_are_rejected_by_upload_routes(
    api,
    teacher_account,
    student_auth,
    assignment,
    db_session_factory,
):
    notes_bytes = fixture_path("notes.txt").read_bytes()

    solution_response = api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
        filename="notes.txt",
        content=notes_bytes,
        content_type="text/plain",
    )
    submission_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
        filename="notes.txt",
        content=notes_bytes,
        content_type="text/plain",
    )

    assert solution_response.status_code == 400
    assert solution_response.json() == {"detail": "官方答案必须是 .docx 文件。"}
    assert submission_response.status_code == 400
    assert submission_response.json() == {"detail": "学生作业必须是 .pdf 文件。"}

    with db_session_factory() as db:
        assert db.query(AnswerFile).count() == 0
        assert db.query(Submission).count() == 0


def test_empty_pdf_upload_is_saved_but_fails_during_local_preprocessing(
    api,
    teacher_account,
    student_auth,
    assignment,
    local_processing_roots,
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
):
    def fail_if_external_called(*args, **kwargs):
        raise AssertionError("grade_with_qwen_vision should not be called for an empty PDF")

    monkeypatch.setattr(qwen_service, "grade_with_qwen_vision", fail_if_external_called)

    solution_bytes = fixture_path("valid_solution.docx").read_bytes()
    empty_pdf_bytes = fixture_path("empty_upload.pdf").read_bytes()

    solution_response = api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
        filename="valid_solution.docx",
        content=solution_bytes,
    )
    upload_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
        filename="empty_upload.pdf",
        content=empty_pdf_bytes,
    )
    submission_id = upload_response.json()["id"]
    grade_response = api.grade_submission(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )

    assert solution_response.status_code == 200
    assert upload_response.status_code == 201
    assert Path(upload_response.json()["file_path"]).stat().st_size == 0
    assert grade_response.status_code == 502
    assert grade_response.json() == {
        "detail": "视觉评分失败: 学生提交 PDF 文件无效，请检查文件是否为有效且非空的 PDF。"
    }

    with db_session_factory() as db:
        submission = db.get(Submission, submission_id)
        grade_result = db.query(GradeResult).filter(GradeResult.submission_id == submission_id).one_or_none()
        grade_question_count = db.query(GradeQuestion).count()
        assert submission is not None
        assert submission.status == "failed_grading"
        assert submission.error_message == "视觉评分失败: 学生提交 PDF 文件无效，请检查文件是否为有效且非空的 PDF。"
        assert submission.graded_at is None
        assert grade_result is None
        assert grade_question_count == 0
    assert not (local_processing_roots["student_root"] / str(submission_id)).exists()


def test_corrupted_pdf_upload_fails_with_standardized_http_error(
    api,
    teacher_account,
    student_auth,
    assignment,
    local_processing_roots,
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
):
    corrupted_pdf_bytes = fixture_path("corrupted_submission.pdf").read_bytes()

    upload_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
        filename="corrupted_submission.pdf",
        content=corrupted_pdf_bytes,
    )

    assert upload_response.status_code == 400
    assert upload_response.json() == {
        "detail": "文件内容与扩展名 .pdf 不匹配，请上传正确格式的文件。"
    }

    with db_session_factory() as db:
        assert db.query(Submission).count() == 0


def test_empty_docx_upload_fails_with_standardized_http_error(
    api,
    teacher_account,
    student_auth,
    assignment,
    local_processing_roots,
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
):
    def fail_if_external_called(*args, **kwargs):
        raise AssertionError("grade_with_qwen_vision should not be called for an empty DOCX")

    monkeypatch.setattr(qwen_service, "grade_with_qwen_vision", fail_if_external_called)

    empty_docx_bytes = fixture_path("empty_upload.docx").read_bytes()
    pdf_bytes = fixture_path("valid_submission.pdf").read_bytes()

    solution_response = api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
        filename="empty_upload.docx",
        content=empty_docx_bytes,
    )
    upload_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
        filename="valid_submission.pdf",
        content=pdf_bytes,
    )
    submission_id = upload_response.json()["id"]
    answer_file_id = solution_response.json()["id"]
    grade_response = api.grade_submission(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )

    assert solution_response.status_code == 200
    assert upload_response.status_code == 201
    assert grade_response.status_code == 502
    assert grade_response.json() == {
        "detail": "视觉评分失败: 老师答案 Word 文件无效，请检查文件是否为有效且非空的 .docx。"
    }

    with db_session_factory() as db:
        submission = db.get(Submission, submission_id)
        assert submission is not None
        assert submission.status == "failed_grading"
        assert submission.error_message == "视觉评分失败: 老师答案 Word 文件无效，请检查文件是否为有效且非空的 .docx。"
        assert submission.graded_at is None
        assert db.query(GradeResult).count() == 0
        assert db.query(GradeQuestion).count() == 0
    assert not (local_processing_roots["teacher_root"] / str(answer_file_id)).exists()
    assert not (local_processing_roots["student_root"] / str(submission_id)).exists()


def test_corrupted_docx_upload_fails_with_standardized_http_error(
    api,
    teacher_account,
    assignment,
    db_session_factory,
):
    corrupted_docx_bytes = fixture_path("corrupted_solution.docx").read_bytes()

    solution_response = api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
        filename="corrupted_solution.docx",
        content=corrupted_docx_bytes,
    )

    assert solution_response.status_code == 400
    assert solution_response.json() == {
        "detail": "文件内容与扩展名 .docx 不匹配，请上传正确格式的文件。"
    }

    with db_session_factory() as db:
        assert db.query(AnswerFile).count() == 0


def test_missing_solution_divider_docx_fails_during_local_preprocessing(
    api,
    teacher_account,
    student_auth,
    assignment,
    local_processing_roots,
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
):
    def fail_if_external_called(*args, **kwargs):
        raise AssertionError("grade_with_qwen_vision should not be called when DOCX preprocessing fails")

    monkeypatch.setattr(qwen_service, "grade_with_qwen_vision", fail_if_external_called)

    solution_bytes = fixture_path("missing_solution_divider.docx").read_bytes()
    pdf_bytes = fixture_path("valid_submission.pdf").read_bytes()

    solution_response = api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
        filename="missing_solution_divider.docx",
        content=solution_bytes,
    )
    upload_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
        filename="valid_submission.pdf",
        content=pdf_bytes,
    )
    submission_id = upload_response.json()["id"]
    grade_response = api.grade_submission(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )

    assert grade_response.status_code == 502
    assert grade_response.json() == {"detail": "视觉评分失败: 老师答案 Word 中未找到 'Solution' 分隔行。"}

    with db_session_factory() as db:
        submission = db.get(Submission, submission_id)
        grade_result = db.query(GradeResult).filter(GradeResult.submission_id == submission_id).one_or_none()
        grade_question_count = db.query(GradeQuestion).count()
        assert submission is not None
        assert submission.status == "failed_grading"
        assert submission.error_message == "视觉评分失败: 老师答案 Word 中未找到 'Solution' 分隔行。"
        assert submission.graded_at is None
        assert grade_result is None
        assert grade_question_count == 0
    assert not (local_processing_roots["teacher_root"] / str(solution_response.json()["id"])).exists()
    assert not (local_processing_roots["student_root"] / str(submission_id)).exists()


def test_offline_grade_route_runs_real_local_preprocessing_before_model_stub(
    api,
    teacher_account,
    student_auth,
    assignment,
    local_processing_roots,
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
):
    recorded_calls: list[dict[str, list[str]]] = []

    def fake_grade_with_qwen_vision(
        teacher_question_images: list[str],
        teacher_solution_images: list[str],
        student_images: list[str],
    ) -> dict:
        recorded_calls.append(
            {
                "teacher_question_images": teacher_question_images,
                "teacher_solution_images": teacher_solution_images,
                "student_images": student_images,
            }
        )
        return {
            "questions": [
                {
                    "question_id": "Q1",
                    "question_match": True,
                    "question_match_confidence": 0.99,
                    "auto_graded": True,
                    "score": 1.0,
                    "max_score": 1.0,
                    "is_correct": True,
                    "comment": "本地预处理成功。",
                }
            ]
        }

    monkeypatch.setattr(qwen_service, "grade_with_qwen_vision", fake_grade_with_qwen_vision)

    solution_bytes = fixture_path("valid_solution.docx").read_bytes()
    pdf_bytes = fixture_path("valid_submission.pdf").read_bytes()

    solution_response = api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
        filename="valid_solution.docx",
        content=solution_bytes,
    )
    upload_response = api.upload_submission_as_student(
        student_headers=student_auth["headers"],
        assignment_id=assignment["id"],
        filename="valid_submission.pdf",
        content=pdf_bytes,
    )
    submission_id = upload_response.json()["id"]
    answer_file_id = solution_response.json()["id"]

    grade_response = api.grade_submission(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )
    result_response = api.get_submission_result(
        teacher_headers=teacher_account["headers"],
        submission_id=submission_id,
    )

    assert grade_response.status_code == 200
    assert result_response.status_code == 200
    assert len(recorded_calls) == 1
    recorded = recorded_calls[0]
    assert len(recorded["teacher_question_images"]) == 1
    assert len(recorded["teacher_solution_images"]) == 1
    assert len(recorded["student_images"]) == 1
    assert all(Path(path).exists() for path in recorded["teacher_question_images"])
    assert all(Path(path).exists() for path in recorded["teacher_solution_images"])
    assert all(path.endswith(".png") for path in recorded["student_images"])

    teacher_cache_root = local_processing_roots["teacher_root"] / str(answer_file_id)
    assert (teacher_cache_root / "questions" / "q_1.png").exists()
    assert (teacher_cache_root / "solutions" / "s_1.png").exists()
    assert (teacher_cache_root / "source_meta.json").exists()
    assert not (local_processing_roots["student_root"] / str(submission_id)).exists()

    result_body = result_response.json()
    assert result_body["status"] == "graded"
    assert len(result_body["questions"]) == 1
    assert result_body["questions"][0]["comment"] == "[Q1] 本地预处理成功。"

    with db_session_factory() as db:
        submission = db.get(Submission, submission_id)
        grade_result = db.query(GradeResult).filter(GradeResult.submission_id == submission_id).one_or_none()
        assert submission is not None
        assert submission.status == "graded"
        assert grade_result is not None
        assert grade_result.raw_json["model_meta"]["teacher_question_image_count"] == 1
        assert grade_result.raw_json["model_meta"]["teacher_solution_image_count"] == 1
        assert grade_result.raw_json["model_meta"]["student_image_count"] == 1


def test_ensure_teacher_images_extracts_and_caches_valid_docx(local_processing_roots):
    questions, solutions = teacher_images.ensure_teacher_images(
        11,
        str(fixture_path("valid_solution.docx")),
    )
    cached_questions, cached_solutions = teacher_images.ensure_teacher_images(
        11,
        str(fixture_path("valid_solution.docx")),
    )

    assert len(questions) == 1
    assert len(solutions) == 1
    assert questions == cached_questions
    assert solutions == cached_solutions
    assert Path(questions[0]).exists()
    assert Path(solutions[0]).exists()
    assert (local_processing_roots["teacher_root"] / "11" / "source_meta.json").exists()

    with Image.open(questions[0]) as question_image:
        question_bbox = question_image.point(lambda px: 0 if px > 250 else 255).getbbox()
        assert question_image.size[0] >= 1000
        assert question_image.size[1] >= 300
        assert question_bbox is not None

    with Image.open(solutions[0]) as solution_image:
        solution_bbox = solution_image.point(lambda px: 0 if px > 250 else 255).getbbox()
        assert solution_image.size[0] >= 1000
        assert solution_image.size[1] >= 300
        assert solution_bbox is not None


def test_ensure_teacher_images_reports_missing_solution_divider(local_processing_roots):
    with pytest.raises(RuntimeError, match="老师答案 Word 中未找到 'Solution' 分隔行。"):
        teacher_images.ensure_teacher_images(
            12,
            str(fixture_path("missing_solution_divider.docx")),
        )


def test_ensure_teacher_images_rejects_corrupted_docx_package(local_processing_roots):
    with pytest.raises(RuntimeError, match="老师答案 Word 文件无效，请检查文件是否为有效且非空的 \\.docx。"):
        teacher_images.ensure_teacher_images(
            13,
            str(fixture_path("corrupted_solution.docx")),
        )


def test_export_student_pdf_to_images_generates_pngs_for_valid_pdf(local_processing_roots):
    image_paths = student_images.export_student_pdf_to_images(
        21,
        str(fixture_path("valid_submission.pdf")),
    )

    assert len(image_paths) == 1
    assert Path(image_paths[0]).exists()
    assert image_paths[0].endswith(".png")

    with Image.open(image_paths[0]) as student_image:
        nonwhite_bbox = student_image.point(lambda px: 0 if px > 250 else 255).getbbox()
        assert student_image.size[0] >= 500
        assert student_image.size[1] >= 500
        assert nonwhite_bbox is not None


def test_export_student_pdf_to_images_rejects_corrupted_pdf(local_processing_roots):
    with pytest.raises(RuntimeError, match="学生提交 PDF 文件无效，请检查文件是否为有效且非空的 PDF。"):
        student_images.export_student_pdf_to_images(
            22,
            str(fixture_path("corrupted_submission.pdf")),
        )


def test_export_student_pdf_to_images_rejects_empty_pdf(local_processing_roots):
    with pytest.raises(RuntimeError, match="学生提交 PDF 文件无效，请检查文件是否为有效且非空的 PDF。"):
        student_images.export_student_pdf_to_images(
            23,
            str(fixture_path("empty_upload.pdf")),
        )
