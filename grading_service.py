from __future__ import annotations

import base64
import hashlib
import json
import logging
import mimetypes
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

import fitz
from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from fastapi import HTTPException
from openai import OpenAIError
from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import grading_provider
from file_processor import convert_docx_to_pdf
from models import GradeQuestion, GradeResult, Submission, SubmissionStatus
from runtime_config import get_app_data_dir
from student_images import cleanup_student_tmp_images, export_student_pdf_to_images

logger = logging.getLogger(__name__)


TEACHER_CACHE_ROOT = get_app_data_dir() / "teacher"
CACHE_META_FILENAME = "source_meta.json"
CACHE_META_VERSION = "answer-page-image-v1"
ANSWER_PAGE_DPI = 200


def _bool_from_any(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "y", "1", "correct", "matched"}:
            return True
        if lowered in {"false", "no", "n", "0", "incorrect", "unmatched"}:
            return False
    return False


def _float_or_default(value: Any, default: float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default


def _as_int_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []

    results: list[int] = []
    for item in value:
        if isinstance(item, int):
            results.append(item)
            continue
        if isinstance(item, str) and item.strip().isdigit():
            results.append(int(item.strip()))
    return results


def _require_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise RuntimeError(f"{field_name} 类型错误: bool")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped and stripped.lstrip("+-").isdigit():
            return int(stripped)
    raise RuntimeError(f"{field_name} 不是有效整数。")


def _require_str(value: Any, field_name: str) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        raise RuntimeError(f"{field_name} 不能为空。")
    return str(value)


def _ensure_submission_instance(value: object, field_name: str) -> Submission:
    if isinstance(value, Submission):
        return value
    raise RuntimeError(f"{field_name} 不是有效 Submission 实例。")


def _image_path_to_data_url(image_path: str) -> str:
    path = Path(image_path)
    suffix = path.suffix.lower()
    mime_type = mimetypes.types_map.get(suffix) or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _normalize_vision_result(result: dict[str, Any]) -> dict[str, Any]:
    questions_data = result.get("questions")
    if not isinstance(questions_data, list):
        raise RuntimeError("结果缺少 questions 列表。")

    normalized_questions: list[dict[str, Any]] = []
    for index, question in enumerate(questions_data, start=1):
        if not isinstance(question, dict):
            question = {}

        question_id_raw = question.get("question_id")
        question_id = str(question_id_raw).strip() if question_id_raw is not None else f"Q{index}"
        if not question_id:
            question_id = f"Q{index}"

        question_brief_raw = question.get("question_brief")
        question_brief = str(question_brief_raw).strip() if question_brief_raw is not None else ""

        teacher_question_indices = _as_int_list(question.get("teacher_question_image_indices"))
        teacher_solution_indices = _as_int_list(question.get("teacher_solution_image_indices"))
        student_answer_indices = _as_int_list(question.get("student_answer_image_indices"))

        question_match = _bool_from_any(question.get("question_match"))
        confidence = _float_or_default(question.get("question_match_confidence"), 0.0)
        confidence = max(0.0, min(1.0, confidence))

        auto_graded_raw = question.get("auto_graded")
        auto_graded = _bool_from_any(auto_graded_raw) if auto_graded_raw is not None else question_match
        if not question_match:
            auto_graded = False

        scored = _coerce_question_for_storage({**question, "auto_graded": auto_graded})

        student_final_answer_raw = question.get("student_final_answer")
        student_final_answer = (
            str(student_final_answer_raw).strip() if student_final_answer_raw is not None else None
        )
        if student_final_answer == "":
            student_final_answer = None

        normalized_questions.append(
            {
                "question_number": index,
                "question_id": question_id,
                "question_brief": question_brief,
                "teacher_question_image_indices": teacher_question_indices,
                "teacher_solution_image_indices": teacher_solution_indices,
                "student_answer_image_indices": student_answer_indices,
                "question_match": question_match,
                "question_match_confidence": confidence,
                "auto_graded": auto_graded,
                "score": float(scored["score"]) if scored["score"] is not None else None,
                "max_score": float(scored["max_score"]),
                "is_correct": bool(scored["is_correct"]) if scored["is_correct"] is not None else None,
                "student_final_answer": student_final_answer,
                "comment": str(scored["comment"]),
            }
        )

    total_score = round(
        sum(float(item["score"]) for item in normalized_questions if isinstance(item.get("score"), (int, float))),
        2,
    )
    max_total_score = round(sum(item["max_score"] for item in normalized_questions), 2)
    auto_graded_count = sum(1 for item in normalized_questions if item["auto_graded"])
    manual_review_count = len(normalized_questions) - auto_graded_count

    return {
        "questions": normalized_questions,
        "summary": {
            "total_score": float(total_score),
            "max_total_score": float(max_total_score),
            "auto_graded_count": int(auto_graded_count),
            "manual_review_count": int(manual_review_count),
            "needs_manual_review": manual_review_count > 0,
        },
    }


def _coerce_question_for_storage(question: dict[str, Any]) -> dict[str, Any]:
    auto_graded = bool(question.get("auto_graded", False))
    score: float | None = _float_or_default(question.get("score"), 0.0)
    max_score = _float_or_default(question.get("max_score"), 1.0)
    if max_score <= 0:
        max_score = 1.0

    if auto_graded:
        score = max(0.0, min(max_score, score))
        is_correct_raw = question.get("is_correct")
        if is_correct_raw is None:
            is_correct = score >= (max_score * 0.999)
        else:
            is_correct = _bool_from_any(is_correct_raw)
    else:
        score = None
        is_correct = None

    comment_raw = question.get("comment")
    comment = str(comment_raw).strip() if comment_raw is not None else ""
    if not comment:
        comment = "需要人工复核。" if not auto_graded else "自动评分完成。"

    return {
        "auto_graded": auto_graded,
        "score": score,
        "max_score": max_score,
        "is_correct": is_correct,
        "comment": comment,
    }


def _build_question_rows(normalized_questions: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, question in enumerate(normalized_questions, start=1):
        if not isinstance(question, dict):
            continue

        question_id = str(question.get("question_id") or f"Q{index}").strip() or f"Q{index}"
        stored = _coerce_question_for_storage(question)
        auto_graded = bool(stored["auto_graded"])
        score = float(stored["score"]) if stored["score"] is not None else None
        max_score = float(stored["max_score"])
        is_correct = bool(stored["is_correct"]) if stored["is_correct"] is not None else None
        comment = str(stored["comment"])
        if not auto_graded and "人工复核" not in comment:
            comment = f"{comment}（需人工复核）"

        rows.append(
            {
                "index": index,
                "question_id": question_id,
                "auto_graded": auto_graded,
                "score": score,
                "max_score": max_score,
                "is_correct": is_correct,
                "comment": comment,
            }
        )
    return rows


def _row_common_fields(row: dict[str, Any]) -> tuple[int, float | None, float, bool | None, str]:
    return (
        int(row["index"]),
        float(row["score"]) if row["score"] is not None else None,
        float(row["max_score"]),
        bool(row["is_correct"]) if row["is_correct"] is not None else None,
        str(row["comment"]),
    )


def _stable_positive_id(seed: str) -> int:
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    return (int(digest[:12], 16) % 2_000_000_000) + 1


def _build_source_fingerprint(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_mtime_ns}-{stat.st_size}"


def _read_cache_meta(meta_path: Path) -> dict[str, str] | None:
    if not meta_path.exists():
        return None
    try:
        raw = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(raw, dict):
        return None
    source_path = raw.get("source_path")
    source_fingerprint = raw.get("source_fingerprint")
    version = raw.get("version")
    if (
        not isinstance(source_path, str)
        or not isinstance(source_fingerprint, str)
        or not isinstance(version, str)
    ):
        return None
    return {
        "source_path": source_path,
        "source_fingerprint": source_fingerprint,
        "version": version,
    }


def _write_cache_meta(meta_path: Path, source_path: Path, source_fingerprint: str) -> None:
    payload = {
        "source_path": str(source_path),
        "source_fingerprint": source_fingerprint,
        "version": CACHE_META_VERSION,
    }
    meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _list_page_image_paths(folder: Path) -> list[str]:
    if not folder.exists():
        return []

    def _page_num(path: Path) -> int:
        try:
            return int(path.stem.split("_")[-1])
        except ValueError:
            return 0

    image_paths = [
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() == ".png" and path.stem.startswith("page_")
    ]
    image_paths.sort(key=_page_num)
    return [str(path.resolve()) for path in image_paths]


def _render_pdf_pages(pdf_path: str, pages_dir: Path) -> None:
    try:
        document = fitz.open(pdf_path)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("老师答案 PDF 文件无效，请检查文件是否为有效且非空的 .pdf。") from exc

    try:
        zoom = ANSWER_PAGE_DPI / 72
        matrix = fitz.Matrix(zoom, zoom)
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            page_path = pages_dir / f"page_{page_index + 1}.png"
            pixmap.save(str(page_path))
    finally:
        document.close()


def ensure_answer_page_images(answer_file_id: int, answer_path: str) -> list[str]:
    """Ensure the teacher answer file (docx or pdf) is rendered to cached page PNGs.

    Cache path: data/teacher/<answer_file_id>/pages/
    """

    if answer_file_id <= 0:
        raise RuntimeError("answer_file_id 无效，无法建立老师答案图片缓存。")

    source_path = Path(answer_path).expanduser().resolve()
    if not source_path.exists():
        raise RuntimeError(f"老师答案文件不存在: {source_path}")
    source_fingerprint = _build_source_fingerprint(source_path)

    answer_dir = TEACHER_CACHE_ROOT / str(answer_file_id)
    pages_dir = answer_dir / "pages"
    meta_path = answer_dir / CACHE_META_FILENAME

    cached_pages = _list_page_image_paths(pages_dir)
    cache_meta = _read_cache_meta(meta_path)
    if (
        cached_pages
        and cache_meta is not None
        and cache_meta.get("source_path") == str(source_path)
        and cache_meta.get("source_fingerprint") == source_fingerprint
        and cache_meta.get("version") == CACHE_META_VERSION
    ):
        return cached_pages

    if pages_dir.exists():
        shutil.rmtree(pages_dir)
    pages_dir.mkdir(parents=True, exist_ok=True)

    try:
        suffix = source_path.suffix.lower()
        if suffix == ".docx":
            try:
                document = Document(str(source_path))
                _ = document.paragraphs
            except (PackageNotFoundError, BadZipFile, ValueError) as exc:
                raise RuntimeError("老师答案 Word 文件无效，请检查文件是否为有效且非空的 .docx。") from exc

            with tempfile.TemporaryDirectory() as tmp_dir:
                pdf_path = convert_docx_to_pdf(str(source_path), tmp_dir)
                _render_pdf_pages(pdf_path, pages_dir)
        elif suffix == ".pdf":
            _render_pdf_pages(str(source_path), pages_dir)
        else:
            raise RuntimeError(f"不支持的官方答案文件格式: {suffix}")

        pages = _list_page_image_paths(pages_dir)
        if not pages:
            raise RuntimeError("老师答案文件未生成任何页面图片。")

        _write_cache_meta(meta_path, source_path, source_fingerprint)
        return pages
    except Exception:
        shutil.rmtree(answer_dir, ignore_errors=True)
        raise


def auto_grade_homework(
    teacher_docx: str,
    student_pdf: str,
    *,
    answer_file_id: int | None,
    submission_id: int | None,
    cache_prefix: str | None = None,
) -> dict[str, Any]:
    if answer_file_id is None or answer_file_id <= 0:
        if not cache_prefix:
            raise RuntimeError("answer_file_id 无效，且未提供 cache_prefix。")
        answer_file_id = _stable_positive_id(f"teacher:{cache_prefix}:{Path(teacher_docx).name}")

    if submission_id is None or submission_id <= 0:
        if not cache_prefix:
            raise RuntimeError("submission_id 无效，且未提供 cache_prefix。")
        submission_id = _stable_positive_id(f"submission:{cache_prefix}:{Path(student_pdf).name}")

    answer_images = ensure_answer_page_images(answer_file_id, teacher_docx)
    student_images = export_student_pdf_to_images(submission_id, student_pdf)

    answer_data_urls = [_image_path_to_data_url(path) for path in answer_images]
    student_data_urls = [_image_path_to_data_url(path) for path in student_images]

    raw_model_json, model_id = grading_provider.call_grading_model(answer_data_urls, student_data_urls)
    normalized = _normalize_vision_result(raw_model_json)

    provider = grading_provider.get_active_provider_name()

    return {
        "raw_model_json": raw_model_json,
        "normalized": normalized,
        "model_meta": {
            "model_name": model_id,
            "provider": provider,
            "answer_image_count": len(answer_images),
            "student_image_count": len(student_images),
        },
        "artifacts": {
            "answer_images": answer_images,
            "student_images": student_images,
        },
        "runtime_ids": {
            "answer_file_id": answer_file_id,
            "submission_id": submission_id,
        },
    }


def _set_submission_failed(db: Session, submission: Submission, status: str, error_message: str) -> None:
    db.rollback()
    submission.status = status
    submission.error_message = error_message[:2000]
    db.commit()


GRADABLE_STATUSES = {
    SubmissionStatus.UPLOADED,
    SubmissionStatus.FAILED_GRADING,
    SubmissionStatus.FAILED_UPLOAD,
    SubmissionStatus.NEEDS_MANUAL_REVIEW,
}


def claim_for_grading(db: Session, submission_id: int) -> Submission:
    """Atomically transition a submission to GRADING status.

    Uses SELECT ... FOR UPDATE to prevent concurrent grade requests from
    racing on the same submission.  Returns the locked submission row if
    the transition succeeds; raises 409 otherwise.
    """
    from sqlalchemy import select as sa_select

    stmt = (
        sa_select(Submission)
        .where(Submission.id == submission_id)
        .with_for_update()
    )
    submission = db.execute(stmt).scalar_one_or_none()
    if submission is None:
        raise HTTPException(status_code=404, detail=f"Submission {submission_id} 不存在。")

    if submission.status not in GRADABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"该提交当前状态为「{submission.status}」，无法发起批改。",
        )

    submission.status = SubmissionStatus.GRADING
    submission.error_message = None
    db.commit()
    db.refresh(submission)
    return submission


def grade_claimed_submission(db: Session, submission_id: int) -> None:
    """Run grading for a submission that has already been claimed (status == GRADING).

    Meant to be called from a background task with its own DB session, so
    unlike the old synchronous flow it never raises HTTPException — all
    failures are logged and written back to the submission row instead.
    """
    submission_record = db.get(Submission, submission_id)
    if submission_record is None:
        logger.error("grading_missing_submission submission_id=%s", submission_id)
        return
    submission_obj = _ensure_submission_instance(submission_record, "submission_record")

    assignment = submission_obj.assignment
    if assignment is None:
        logger.error("grading_missing_assignment submission_id=%s", submission_id)
        _set_submission_failed(db, submission_obj, SubmissionStatus.FAILED_GRADING, "Submission 未关联到有效的 assignment。")
        return
    answer_file = assignment.answer_file
    if answer_file is None:
        logger.error("grading_missing_answer_file submission_id=%s", submission_id)
        _set_submission_failed(db, submission_obj, SubmissionStatus.FAILED_GRADING, "该 assignment 尚未上传官方答案文件。")
        return

    submission_id_value = _require_int(submission_obj.id, "submission.id")
    answer_file_id = _require_int(answer_file.id, "answer_file.id")
    answer_file_path = _require_str(answer_file.file_path, "answer_file.file_path")
    submission_file_path = _require_str(submission_obj.file_path, "submission.file_path")
    logger.info("grading_started submission_id=%s", submission_id_value)

    try:
        audit_payload = auto_grade_homework(
            teacher_docx=answer_file_path,
            student_pdf=submission_file_path,
            answer_file_id=answer_file_id,
            submission_id=submission_id_value,
        )
        normalized = audit_payload.get("normalized")
        if not isinstance(normalized, dict):
            raise RuntimeError("评分结果归一化失败。")
        normalized_questions = normalized.get("questions")
        summary = normalized.get("summary")
        if not isinstance(normalized_questions, list) or not isinstance(summary, dict):
            raise RuntimeError("评分结果结构无效。")
    except (RuntimeError, OpenAIError, ValueError, TypeError, OSError) as exc:
        logger.error("grading_failed submission_id=%s error=%s", submission_id_value, exc)
        _set_submission_failed(db, submission_obj, SubmissionStatus.FAILED_GRADING, f"视觉评分失败: {exc}")
        return
    finally:
        try:
            cleanup_student_tmp_images(submission_id_value)
        except OSError:
            logger.warning("cleanup_failed submission_id=%s", submission_id_value, exc_info=True)

    grade_result = submission_obj.grade_result
    if grade_result is None:
        grade_result = GradeResult(submission_id=submission_id_value)
        db.add(grade_result)

    total_score = _float_or_default(summary.get("total_score"), 0.0)
    max_total_score = _float_or_default(summary.get("max_total_score"), 0.0)
    needs_manual_review = bool(summary.get("needs_manual_review")) or any(
        not bool(question.get("auto_graded", False)) for question in normalized_questions
    )

    model_meta = audit_payload.get("model_meta")
    provider = model_meta.get("provider") if isinstance(model_meta, dict) else None
    model_id = model_meta.get("model_name") if isinstance(model_meta, dict) else None
    grade_result.model_name = f"vision:{provider}:{model_id}"
    grade_result.raw_json = audit_payload
    grade_result.total_score = total_score
    grade_result.max_total_score = max_total_score

    try:
        db.flush()
        grade_result_id = _require_int(grade_result.id, "grade_result.id")
        db.execute(delete(GradeQuestion).where(GradeQuestion.grade_result_id == grade_result_id))

        question_rows = _build_question_rows(normalized_questions)
        for row in question_rows:
            index, score, max_score, is_correct, comment = _row_common_fields(row)
            if score is None or is_correct is None:
                continue
            comment = f"[{row['question_id']}] {comment}"

            db.add(
                GradeQuestion(
                    grade_result_id=grade_result_id,
                    question_number=index,
                    is_correct=is_correct,
                    score=score,
                    max_score=max_score,
                    comment=comment,
                )
            )

        submission_obj.status = SubmissionStatus.NEEDS_MANUAL_REVIEW if needs_manual_review else SubmissionStatus.GRADED
        submission_obj.error_message = None
        submission_obj.graded_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(
            "grading_completed submission_id=%s status=%s score=%.1f/%.1f",
            submission_id_value, submission_obj.status, total_score, max_total_score,
        )
    except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as exc:
        _set_submission_failed(db, submission_obj, SubmissionStatus.FAILED_GRADING, f"评分结果入库失败: {exc}")
        return


def _default_session_factory() -> Session:
    # Resolved lazily (not bound at import time) so tests that monkeypatch
    # the DB wiring in `database` before a background task runs are honored.
    from database import SessionLocal

    return SessionLocal()


_session_factory: Any = _default_session_factory


def run_grading_job(submission_id: int) -> None:
    """Background-task entry point: grade a single already-claimed submission.

    Never raises. Expected failure modes are logged and written back to the
    DB by grade_claimed_submission itself; this is a last-resort safety net
    for anything unexpected that escapes it, so a submission never gets
    stuck in GRADING forever with no error surfaced to the teacher.
    """
    db = _session_factory()
    try:
        grade_claimed_submission(db, submission_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("background_grading_job_failed submission_id=%s", submission_id)
        try:
            db.rollback()
            submission = db.get(Submission, submission_id)
            if submission is not None:
                _set_submission_failed(db, submission, SubmissionStatus.FAILED_GRADING, f"批改任务异常: {exc}")
        except Exception:  # noqa: BLE001
            logger.exception("background_grading_job_failed_to_record_failure submission_id=%s", submission_id)
    finally:
        db.close()


def run_grading_batch(submission_ids: list[int]) -> None:
    """Background-task entry point: grade multiple already-claimed submissions in order."""
    for submission_id in submission_ids:
        run_grading_job(submission_id)


def reset_stuck_grading_submissions(db: Session) -> int:
    """Reset any submission stuck in GRADING (e.g. after a server restart) to FAILED_GRADING."""
    from sqlalchemy import select as sa_select

    stuck = (
        db.execute(sa_select(Submission).where(Submission.status == SubmissionStatus.GRADING))
        .scalars()
        .all()
    )
    for submission in stuck:
        submission.status = SubmissionStatus.FAILED_GRADING
        submission.error_message = "服务重启导致批改中断，请重新发起批改。"
    if stuck:
        db.commit()
        logger.info("reset_stuck_grading_submissions count=%d", len(stuck))
    return len(stuck)
