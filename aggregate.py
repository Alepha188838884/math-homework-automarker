from __future__ import annotations

# DEPRECATED: text/spec pipeline retained for rollback; qwen_service now uses vision pipeline.

from typing import Any


def _coerce_float(value: Any, default: float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default


def _build_fallback_result(label: str, max_score: float) -> dict[str, Any]:
    return {
        "label": label,
        "found": False,
        "question_type": "mixed",
        "student_final_answer": "",
        "is_correct": False,
        "score": None,
        "max_score": max_score,
        "comment": "AI grading failed. Please grade manually.",
        "auto_graded": False,
    }


def aggregate_results(teacher_spec: dict[str, Any], grading_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-question results and enforce label consistency.

    final_result schema:
    {
      "questions": [...],
      "summary": {
        "total_score": number,
        "max_total_score": number,
        "correct_count": int,
        "total_questions": int,
        "auto_graded_count": int,
        "manual_review_count": int
      },
      "consistency": {
        "expected_labels": [...],
        "returned_labels": [...],
        "missing": [...],
        "extra": [...]
      }
    }
    """

    teacher_questions = teacher_spec.get("questions")
    if not isinstance(teacher_questions, list):
        raise RuntimeError("teacher_spec.questions must be a list.")

    expected_labels: list[str] = []
    max_score_by_label: dict[str, float] = {}
    for index, question in enumerate(teacher_questions, start=1):
        if not isinstance(question, dict):
            continue
        label = str(question.get("label") or index).strip() or str(index)
        expected_labels.append(label)
        max_score = _coerce_float(question.get("max_score"), 1.0)
        max_score_by_label[label] = max_score if max_score > 0 else 1.0

    result_by_label: dict[str, dict[str, Any]] = {}
    returned_labels_ordered: list[str] = []
    for result in grading_results:
        if not isinstance(result, dict):
            continue
        label = str(result.get("label") or "").strip()
        if not label:
            continue
        returned_labels_ordered.append(label)
        if label not in result_by_label:
            result_by_label[label] = result

    expected_set = set(expected_labels)
    returned_set = set(result_by_label.keys())
    missing = sorted(expected_set - returned_set)
    extra = sorted(returned_set - expected_set)

    final_questions: list[dict[str, Any]] = []
    for label in expected_labels:
        max_score = max_score_by_label.get(label, 1.0)
        result = result_by_label.get(label)
        if result is None:
            final_questions.append(_build_fallback_result(label, max_score))
            continue

        normalized_result = {
            "label": label,
            "found": bool(result.get("found", False)),
            "question_type": str(result.get("question_type") or "mixed"),
            "student_final_answer": str(result.get("student_final_answer") or ""),
            "is_correct": bool(result.get("is_correct", False)),
            "score": result.get("score"),
            "max_score": _coerce_float(result.get("max_score"), max_score),
            "comment": str(result.get("comment") or "").strip() or None,
            "auto_graded": bool(result.get("auto_graded", False)),
        }

        if normalized_result["max_score"] <= 0:
            normalized_result["max_score"] = max_score

        final_questions.append(normalized_result)

    total_score = 0.0
    max_total_score = 0.0
    correct_count = 0
    auto_graded_count = 0
    manual_review_count = 0

    for question in final_questions:
        q_max = _coerce_float(question.get("max_score"), 1.0)
        q_score_raw = question.get("score")
        q_score = q_score_raw if isinstance(q_score_raw, (int, float)) else None

        max_total_score += q_max
        if q_score is not None:
            total_score += float(q_score)

        if bool(question.get("is_correct", False)):
            correct_count += 1

        if bool(question.get("auto_graded", False)):
            auto_graded_count += 1
        if not bool(question.get("auto_graded", False)) or q_score is None:
            manual_review_count += 1

    final_result = {
        "questions": final_questions,
        "summary": {
            "total_score": round(total_score, 2),
            "max_total_score": round(max_total_score, 2),
            "correct_count": correct_count,
            "total_questions": len(expected_labels),
            "auto_graded_count": auto_graded_count,
            "manual_review_count": manual_review_count,
        },
        "consistency": {
            "expected_labels": expected_labels,
            "returned_labels": returned_labels_ordered,
            "missing": missing,
            "extra": extra,
        },
    }
    return final_result
