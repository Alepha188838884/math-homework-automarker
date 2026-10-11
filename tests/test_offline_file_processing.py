from __future__ import annotations

import subprocess
import threading
from pathlib import Path

import fitz
import file_processor
import grading_provider
import grading_service
import pytest
import student_images
from models import AnswerFile, GradeQuestion, GradeResult, Submission
from PIL import Image


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def fixture_path(name: str) -> Path:
    return FIXTURES_DIR / name


@pytest.fixture
def local_processing_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    teacher_root = tmp_path / "teacher_cache"
    student_root = tmp_path / "student_tmp"
    monkeypatch.setattr(grading_service, "TEACHER_CACHE_ROOT", teacher_root)
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
    assert body["qwen_file_id"] is None

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
    assert solution_response.json() == {"detail": "官方答案必须是 .docx 或 .pdf 文件。"}
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
        raise AssertionError("call_grading_model should not be called for an empty student PDF")

    monkeypatch.setattr(grading_provider, "call_grading_model", fail_if_external_called)

    # Use a PDF as the official answer here so this test never shells out to
    # LibreOffice (not available in CI) — it only exercises the student-side
    # failure path, which must be reached before the model is ever called.
    solution_bytes = fixture_path("valid_submission.pdf").read_bytes()
    empty_pdf_bytes = fixture_path("empty_upload.pdf").read_bytes()

    solution_response = api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
        filename="valid_solution.pdf",
        content=solution_bytes,
        content_type="application/pdf",
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
    # TestClient runs BackgroundTasks to completion before .post() returns, so
    # the request itself only reports that grading was started; the failure
    # is written back to the submission row by the background job.
    assert grade_response.status_code == 202
    assert grade_response.json() == {"submission_id": submission_id, "status": "grading"}

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
        raise AssertionError("call_grading_model should not be called for an empty DOCX")

    monkeypatch.setattr(grading_provider, "call_grading_model", fail_if_external_called)

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
    assert grade_response.status_code == 202
    assert grade_response.json() == {"submission_id": submission_id, "status": "grading"}

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

    def fake_call_grading_model(
        answer_images: list[str],
        student_images: list[str],
    ) -> tuple[dict, str]:
        recorded_calls.append({"answer_images": answer_images, "student_images": student_images})
        return (
            {
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
            },
            "stub-vision-model",
        )

    monkeypatch.setattr(grading_provider, "call_grading_model", fake_call_grading_model)

    # The official answer is a PDF here so this test exercises real local
    # preprocessing (PyMuPDF page rendering) without ever shelling out to
    # LibreOffice, which is not available in CI.
    solution_bytes = fixture_path("valid_submission.pdf").read_bytes()
    pdf_bytes = fixture_path("valid_submission.pdf").read_bytes()

    solution_response = api.upload_solution(
        teacher_headers=teacher_account["headers"],
        assignment_id=assignment["id"],
        filename="valid_solution.pdf",
        content=solution_bytes,
        content_type="application/pdf",
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

    assert grade_response.status_code == 202
    assert result_response.status_code == 200
    assert len(recorded_calls) == 1
    recorded = recorded_calls[0]
    assert len(recorded["answer_images"]) == 1
    assert len(recorded["student_images"]) == 1
    assert all(url.startswith("data:image/png;base64,") for url in recorded["answer_images"])
    assert all(url.startswith("data:image/png;base64,") for url in recorded["student_images"])

    teacher_cache_root = local_processing_roots["teacher_root"] / str(answer_file_id)
    assert (teacher_cache_root / "pages" / "page_1.png").exists()
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
        assert grade_result.raw_json["model_meta"]["answer_image_count"] == 1
        assert grade_result.raw_json["model_meta"]["student_image_count"] == 1


def test_ensure_answer_page_images_renders_and_caches_valid_pdf(local_processing_roots, monkeypatch):
    original_render = grading_service._render_pdf_pages
    call_count = {"n": 0}

    def counting_render(pdf_path: str, pages_dir: Path) -> None:
        call_count["n"] += 1
        original_render(pdf_path, pages_dir)

    monkeypatch.setattr(grading_service, "_render_pdf_pages", counting_render)

    pages = grading_service.ensure_answer_page_images(
        41,
        str(fixture_path("valid_submission.pdf")),
    )
    cached_pages = grading_service.ensure_answer_page_images(
        41,
        str(fixture_path("valid_submission.pdf")),
    )

    assert len(pages) == 1
    assert pages == cached_pages
    assert call_count["n"] == 1
    assert Path(pages[0]).exists()
    assert (local_processing_roots["teacher_root"] / "41" / "source_meta.json").exists()

    with Image.open(pages[0]) as page_image:
        nonwhite_bbox = page_image.point(lambda px: 0 if px > 250 else 255).getbbox()
        assert page_image.size[0] >= 500
        assert page_image.size[1] >= 500
        assert nonwhite_bbox is not None


def test_ensure_answer_page_images_concurrent_calls_for_same_answer_file_are_safe(
    local_processing_roots,
):
    # Simulates concurrent batch grading hitting a cold cache for the same
    # answer_file_id at once: every thread should succeed and agree on the
    # same rendered page list, instead of racing on shutil.rmtree.
    results: list[list[str]] = []
    errors: list[BaseException] = []
    results_lock = threading.Lock()

    def worker() -> None:
        try:
            pages = grading_service.ensure_answer_page_images(
                46,
                str(fixture_path("valid_submission.pdf")),
            )
        except BaseException as exc:  # noqa: BLE001
            with results_lock:
                errors.append(exc)
            return
        with results_lock:
            results.append(pages)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(results) == 5
    assert all(pages == results[0] for pages in results)
    assert Path(results[0][0]).exists()


def test_ensure_answer_page_images_recovers_from_mid_rebuild_cache_read_error(
    local_processing_roots,
    monkeypatch,
):
    # Reproduces the race where the unlocked fast-path cache check reads the
    # pages directory while another thread is mid-rebuild (post-rmtree,
    # pre-rewrite) and gets a FileNotFoundError instead of a clean miss. The
    # unlocked check must swallow that and fall through to the locked path
    # instead of letting the exception escape to the caller.
    pages = grading_service.ensure_answer_page_images(
        47,
        str(fixture_path("valid_submission.pdf")),
    )

    original_check = grading_service._check_cached_answer_pages
    call_count = {"n": 0}

    def flaky_check(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise FileNotFoundError("cache dir disappeared mid-rebuild")
        return original_check(*args, **kwargs)

    monkeypatch.setattr(grading_service, "_check_cached_answer_pages", flaky_check)

    recovered_pages = grading_service.ensure_answer_page_images(
        47,
        str(fixture_path("valid_submission.pdf")),
    )

    assert call_count["n"] == 2
    assert recovered_pages == pages


def test_ensure_answer_page_images_docx_answer_uses_convert_docx_to_pdf(
    local_processing_roots,
    monkeypatch,
):
    conversion_calls: list[tuple[str, str]] = []

    def fake_convert_docx_to_pdf(docx_path: str, output_dir: str) -> str:
        conversion_calls.append((docx_path, output_dir))
        pdf_path = Path(output_dir) / "stub.pdf"
        document = fitz.open()
        document.new_page()
        document.save(str(pdf_path))
        document.close()
        return str(pdf_path)

    monkeypatch.setattr(grading_service, "convert_docx_to_pdf", fake_convert_docx_to_pdf)

    pages = grading_service.ensure_answer_page_images(
        42,
        str(fixture_path("valid_solution.docx")),
    )

    assert len(conversion_calls) == 1
    assert len(pages) == 1
    assert Path(pages[0]).exists()


def test_ensure_answer_page_images_rejects_corrupted_docx(local_processing_roots):
    with pytest.raises(RuntimeError, match="老师答案 Word 文件无效，请检查文件是否为有效且非空的 \\.docx。"):
        grading_service.ensure_answer_page_images(
            43,
            str(fixture_path("corrupted_solution.docx")),
        )


def test_ensure_answer_page_images_rejects_corrupted_pdf(local_processing_roots):
    with pytest.raises(RuntimeError, match="老师答案 PDF 文件无效，请检查文件是否为有效且非空的 \\.pdf。"):
        grading_service.ensure_answer_page_images(
            44,
            str(fixture_path("corrupted_submission.pdf")),
        )


def test_ensure_answer_page_images_rejects_empty_pdf(local_processing_roots):
    with pytest.raises(RuntimeError, match="老师答案 PDF 文件无效，请检查文件是否为有效且非空的 \\.pdf。"):
        grading_service.ensure_answer_page_images(
            45,
            str(fixture_path("empty_upload.pdf")),
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


def test_convert_docx_to_pdf_uses_isolated_user_profile_per_call(tmp_path, monkeypatch):
    recorded_calls: list[list[str]] = []

    def fake_run(cmd, check, timeout):
        recorded_calls.append(cmd)
        docx_path = Path(cmd[-1])
        output_dir = Path(cmd[cmd.index("--outdir") + 1])
        (output_dir / f"{docx_path.stem}.pdf").write_bytes(b"%PDF-1.4 stub")

    monkeypatch.setattr(file_processor, "find_soffice", lambda: "/usr/bin/soffice")
    monkeypatch.setattr(file_processor.subprocess, "run", fake_run)

    docx_path = tmp_path / "answer.docx"
    docx_path.write_bytes(b"stub docx")
    output_dir = tmp_path / "out"

    pdf_path = file_processor.convert_docx_to_pdf(str(docx_path), str(output_dir))

    assert Path(pdf_path).exists()
    assert len(recorded_calls) == 1
    assert any(arg.startswith("-env:UserInstallation=") for arg in recorded_calls[0])


def test_convert_docx_to_pdf_wraps_called_process_error_as_runtime_error(tmp_path, monkeypatch):
    def fake_run(cmd, check, timeout):
        raise subprocess.CalledProcessError(returncode=1, cmd=cmd)

    monkeypatch.setattr(file_processor, "find_soffice", lambda: "/usr/bin/soffice")
    monkeypatch.setattr(file_processor.subprocess, "run", fake_run)

    docx_path = tmp_path / "answer.docx"
    docx_path.write_bytes(b"stub docx")

    with pytest.raises(RuntimeError, match="LibreOffice 转换失败"):
        file_processor.convert_docx_to_pdf(str(docx_path), str(tmp_path / "out"))


def test_convert_docx_to_pdf_wraps_timeout_expired_as_runtime_error(tmp_path, monkeypatch):
    def fake_run(cmd, check, timeout):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)

    monkeypatch.setattr(file_processor, "find_soffice", lambda: "/usr/bin/soffice")
    monkeypatch.setattr(file_processor.subprocess, "run", fake_run)

    docx_path = tmp_path / "answer.docx"
    docx_path.write_bytes(b"stub docx")

    with pytest.raises(RuntimeError, match="LibreOffice 转换超时"):
        file_processor.convert_docx_to_pdf(str(docx_path), str(tmp_path / "out"))
