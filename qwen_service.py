from __future__ import annotations

import base64
import hashlib
import mimetypes
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from fastapi import HTTPException
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAIError,
    RateLimitError,
)
from openai.types.chat import (
    ChatCompletionContentPartImageParam,
    ChatCompletionContentPartParam,
    ChatCompletionContentPartTextParam,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models import GradeQuestion, GradeResult, Submission
from qwen_client import QWEN_PLUS_MODEL, get_openai_client, parse_json_object
from schemas import GradeQuestionItem, GradeSubmissionResponse
from student_images import cleanup_student_tmp_images, export_student_pdf_to_images
from teacher_images import ensure_teacher_images


QWEN_VISION_MODEL = os.getenv("QWEN_VISION_MODEL", QWEN_PLUS_MODEL)
QWEN_MODEL_NAME = QWEN_VISION_MODEL
PIPELINE_MODEL_NAME = f"vision:{QWEN_VISION_MODEL}"


def upload_file_to_qwen(local_path: str) -> str:
    """Upload one local file to DashScope and return file_id."""

    file_path = Path(local_path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {local_path}")

    client = get_openai_client()
    with file_path.open("rb") as file_obj:
        try:
            response = client.files.create(file=file_obj, purpose=cast(Any, "file-extract"))
        except AuthenticationError as exc:
            raise RuntimeError("DashScope 鉴权失败（401），请检查 DASHSCOPE_API_KEY。") from exc

    file_id = getattr(response, "id", None)
    if not file_id:
        raise RuntimeError("Qwen 文件上传成功但未返回 file_id。")
    return file_id


def _extract_text_from_completion(completion: Any) -> str:
    choices = getattr(completion, "choices", None)
    if not choices:
        raise RuntimeError("Qwen 返回为空。")

    message = choices[0].message
    content = message.content

    if isinstance(content, str):
        text = content.strip()
        if not text:
            raise RuntimeError("Qwen 返回文本为空。")
        return text

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                item_text = item.get("text")
            else:
                item_text = getattr(item, "text", None)
            if item_text:
                parts.append(str(item_text))
        merged = "\n".join(parts).strip()
        if merged:
            return merged

    raise RuntimeError("Qwen 返回内容格式不支持。")


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


def _build_vision_messages(
    teacher_question_images: list[str],
    teacher_solution_images: list[str],
    student_images: list[str],
) -> list[ChatCompletionMessageParam]:
    question_count = len(teacher_question_images)
    solution_count = len(teacher_solution_images)
    student_count = len(student_images)

    q_start, q_end = 1, question_count
    s_start, s_end = q_end + 1, q_end + solution_count
    st_start, st_end = s_end + 1, s_end + student_count

    system_prompt = """
你是严格的数学作业视觉批改助手。
你会按固定顺序接收三组图片：
1) 老师题目图；2) 老师标准解答图；3) 学生作答图。

你必须先做“题目内容匹配”，再做评分：
- 匹配依据是题目内容本身，不依赖纸面题号。
- 只有在确认匹配成功后，才允许自动评分。
- 若无法确认匹配或证据不足，必须标记为人工复核。

输出必须是严格 JSON，不要 Markdown，不要额外文字。
"""

    user_prompt = f"""
图片索引范围如下：
- 老师题目图: {q_start}..{q_end}
- 老师解答图: {s_start}..{s_end}
- 学生作答图: {st_start}..{st_end}

请执行：
1. 依据老师题目图，识别所有题块，生成内部题号 Q1, Q2, ...。
2. 对每个 Qi，在学生图中找同题内容并评估 question_match。
3. 若 question_match=false 或信心不足，必须设置：
   auto_graded=false, score=null, is_correct=null。
4. 仅当 question_match=true 时，结合老师解答图进行评分。

请只输出以下 JSON 结构：
{{
  "questions": [
    {{
      "question_id": "Q1",
      "question_brief": "...",
      "teacher_question_image_indices": [1],
      "teacher_solution_image_indices": [3],
      "student_answer_image_indices": [8],
      "question_match": true,
      "question_match_confidence": 0.95,
      "auto_graded": true,
      "score": 1,
      "max_score": 1,
      "is_correct": true,
      "student_final_answer": "...",
      "comment": "..."
    }}
  ],
  "summary": {{
    "total_score": 1,
    "max_total_score": 1,
    "auto_graded_count": 1,
    "manual_review_count": 0
  }}
}}

硬约束：
- 每个老师题块必须有且仅有一条 questions 记录。
- 不要输出 JSON 之外的任何内容。
"""

    text_part: ChatCompletionContentPartTextParam = {"type": "text", "text": user_prompt.strip()}
    content: list[ChatCompletionContentPartParam] = [text_part]
    ordered_images = teacher_question_images + teacher_solution_images + student_images
    for image_path in ordered_images:
        image_part: ChatCompletionContentPartImageParam = {
            "type": "image_url",
            "image_url": {"url": _image_path_to_data_url(image_path)},
        }
        content.append(image_part)

    system_message: ChatCompletionSystemMessageParam = {
        "role": "system",
        "content": system_prompt.strip(),
    }
    user_message: ChatCompletionUserMessageParam = {"role": "user", "content": content}
    return [system_message, user_message]


def _parse_qwen_vision_json(raw_text: str) -> dict[str, Any]:
    parsed = parse_json_object(raw_text)
    if not isinstance(parsed, dict):
        raise RuntimeError("视觉评分输出不是 JSON 对象。")
    questions = parsed.get("questions")
    if not isinstance(questions, list):
        raise RuntimeError("视觉评分输出缺少 questions 数组。")
    return parsed


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


def _rows_to_response_questions(question_rows: list[dict[str, Any]]) -> list[GradeQuestionItem]:
    response_questions: list[GradeQuestionItem] = []
    for row in question_rows:
        index, score, max_score, is_correct, comment = _row_common_fields(row)
        response_questions.append(
            GradeQuestionItem(
                number=index,
                is_correct=is_correct,
                score=score,
                max_score=max_score,
                comment=comment,
            )
        )
    return response_questions


def _row_common_fields(row: dict[str, Any]) -> tuple[int, float | None, float, bool | None, str]:
    return (
        int(row["index"]),
        float(row["score"]) if row["score"] is not None else None,
        float(row["max_score"]),
        bool(row["is_correct"]) if row["is_correct"] is not None else None,
        str(row["comment"]),
    )


def grade_with_qwen_vision(
    teacher_question_images: list[str],
    teacher_solution_images: list[str],
    student_images: list[str],
) -> dict[str, Any]:
    if not teacher_question_images:
        raise RuntimeError("老师题目图片为空，无法评分。")
    if not teacher_solution_images:
        raise RuntimeError("老师解答图片为空，无法评分。")
    if not student_images:
        raise RuntimeError("学生作业图片为空，无法评分。")

    messages = _build_vision_messages(
        teacher_question_images=teacher_question_images,
        teacher_solution_images=teacher_solution_images,
        student_images=student_images,
    )

    retriable_errors = (
        APIConnectionError,
        APITimeoutError,
        APIStatusError,
        RateLimitError,
        BadRequestError,
        OpenAIError,
        RuntimeError,
    )
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            client = get_openai_client()
            completion = client.chat.completions.create(
                model=QWEN_VISION_MODEL,
                messages=messages,
                temperature=0,
            )
            raw_text = _extract_text_from_completion(completion)
            return _parse_qwen_vision_json(raw_text)
        except retriable_errors as exc:
            last_exc = exc
            if attempt < 2:
                time.sleep(2**attempt)

    raise RuntimeError(f"Qwen 视觉评分调用失败: {last_exc}")


def _stable_positive_id(seed: str) -> int:
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    return (int(digest[:12], 16) % 2_000_000_000) + 1


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

    teacher_question_images, teacher_solution_images = ensure_teacher_images(answer_file_id, teacher_docx)
    student_images = export_student_pdf_to_images(submission_id, student_pdf)

    raw_model_json = grade_with_qwen_vision(
        teacher_question_images=teacher_question_images,
        teacher_solution_images=teacher_solution_images,
        student_images=student_images,
    )
    normalized = _normalize_vision_result(raw_model_json)

    q_count = len(teacher_question_images)
    s_count = len(teacher_solution_images)
    st_count = len(student_images)

    return {
        "raw_model_json": raw_model_json,
        "normalized": normalized,
        "model_meta": {
            "model_name": QWEN_VISION_MODEL,
            "teacher_question_image_count": q_count,
            "teacher_solution_image_count": s_count,
            "student_image_count": st_count,
        },
        "image_order_meta": {
            "teacher_question_range": [1, q_count],
            "teacher_solution_range": [q_count + 1, q_count + s_count],
            "student_answer_range": [q_count + s_count + 1, q_count + s_count + st_count],
        },
        "artifacts": {
            "teacher_question_images": teacher_question_images,
            "teacher_solution_images": teacher_solution_images,
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


def grade_one_submission(db: Session, submission_id: int) -> GradeSubmissionResponse:
    submission_record = db.get(Submission, submission_id)
    if submission_record is None:
        raise HTTPException(status_code=404, detail=f"Submission {submission_id} 不存在。")
    submission_obj = _ensure_submission_instance(submission_record, "submission_record")
    submission_id_value = _require_int(submission_obj.id, "submission.id")

    assignment = submission_obj.assignment
    if assignment is None:
        raise HTTPException(status_code=400, detail="Submission 未关联到有效的 assignment。")

    answer_file = assignment.answer_file
    if answer_file is None:
        raise HTTPException(status_code=400, detail="该 assignment 尚未上传官方答案文件。")

    answer_file_id = _require_int(answer_file.id, "answer_file.id")
    answer_docx_path = _require_str(answer_file.file_path, "answer_file.file_path")
    submission_file_path = _require_str(submission_obj.file_path, "submission.file_path")

    submission_obj.status = "grading"
    submission_obj.error_message = None
    db.commit()
    db.refresh(submission_obj)

    try:
        audit_payload = auto_grade_homework(
            teacher_docx=answer_docx_path,
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
        _set_submission_failed(db, submission_obj, "failed_grading", f"视觉评分失败: {exc}")
        raise HTTPException(status_code=502, detail=f"视觉评分失败: {exc}") from exc
    finally:
        try:
            cleanup_student_tmp_images(submission_id_value)
        except OSError:
            pass

    grade_result = submission_obj.grade_result
    if grade_result is None:
        grade_result = GradeResult(submission_id=submission_id_value)
        db.add(grade_result)

    total_score = _float_or_default(summary.get("total_score"), 0.0)
    max_total_score = _float_or_default(summary.get("max_total_score"), 0.0)
    needs_manual_review = bool(summary.get("needs_manual_review")) or any(
        not bool(question.get("auto_graded", False)) for question in normalized_questions
    )

    grade_result.model_name = PIPELINE_MODEL_NAME
    grade_result.raw_json = audit_payload
    grade_result.total_score = total_score
    grade_result.max_total_score = max_total_score

    response_questions: list[GradeQuestionItem] | None = None
    try:
        db.flush()
        grade_result_id = _require_int(grade_result.id, "grade_result.id")
        db.execute(delete(GradeQuestion).where(GradeQuestion.grade_result_id == grade_result_id))

        question_rows = _build_question_rows(normalized_questions)
        response_questions = _rows_to_response_questions(question_rows)
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

        submission_obj.status = "needs_manual_review" if needs_manual_review else "graded"
        submission_obj.error_message = None
        submission_obj.graded_at = datetime.now(timezone.utc)
        db.commit()
    except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as exc:
        _set_submission_failed(db, submission_obj, "failed_grading", f"评分结果入库失败: {exc}")
        raise HTTPException(status_code=500, detail=f"评分结果入库失败: {exc}") from exc

    if response_questions is None:
        raise HTTPException(status_code=500, detail="评分结果缺失，无法生成响应。")

    return GradeSubmissionResponse(
        submission_id=submission_id_value,
        status=_require_str(submission_obj.status, "submission.status"),
        questions=response_questions,
        total_score=total_score,
        max_total_score=max_total_score,
    )
