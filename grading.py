from __future__ import annotations

# DEPRECATED: text/spec pipeline retained for rollback; qwen_service now uses vision pipeline.

import json
from typing import Any

from qwen_client import call_qwen_plus, parse_json_object


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "correct", "right", "1"}:
            return True
        if lowered in {"false", "no", "incorrect", "wrong", "0"}:
            return False
    return False


def _coerce_float(value: Any, default: float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default


def _get_max_score(q_spec: dict[str, Any]) -> float:
    max_score_raw = q_spec.get("max_score", 1)
    max_score = _coerce_float(max_score_raw, 1.0)
    return max_score if max_score > 0 else 1.0


def _extract_best_student_text(student_answer: dict[str, Any] | None) -> tuple[bool, str, dict[str, Any] | None]:
    if not isinstance(student_answer, dict):
        return False, "", None

    found = bool(student_answer.get("found"))
    candidates = student_answer.get("candidate_answers")
    if not isinstance(candidates, list) or not candidates:
        return found, "", None

    first = candidates[0] if isinstance(candidates[0], dict) else None
    if not isinstance(first, dict):
        return found, "", None

    text = str(first.get("text") or "").strip()
    context = str(first.get("context") or "").strip()
    merged = "\n".join(part for part in [text, context] if part).strip()
    return found, merged, first


def grade_numeric_or_expression(q_spec: dict[str, Any], student_answer: dict[str, Any] | None) -> dict[str, Any]:
    label = str(q_spec.get("label") or "")
    question_type = str(q_spec.get("question_type") or "mixed")
    max_score = _get_max_score(q_spec)

    found, student_text, _ = _extract_best_student_text(student_answer)
    if not student_text:
        return {
            "label": label,
            "found": found,
            "question_type": question_type,
            "student_final_answer": "",
            "is_correct": False,
            "score": 0.0,
            "max_score": max_score,
            "comment": "未检索到有效学生答案片段。",
            "auto_graded": True,
        }

    system_prompt = """
You are a strict math grader for one single question.
Return STRICT JSON only.
"""
    user_prompt = (
        "Compare student answer with teacher solution for one question.\n"
        f"label: {label}\n"
        f"question_text: {q_spec.get('question_text', '')}\n"
        f"teacher_solution: {q_spec.get('solution_text', '')}\n"
        f"student_text: {student_text}\n\n"
        "Output JSON:\n"
        "{\n"
        '  "student_final_answer": "...",\n'
        '  "is_correct": true/false,\n'
        '  "comment": "..."\n'
        "}\n"
        "Rules: only compare with teacher solution; do not invent new solution."
    )

    is_correct = False
    comment = "模型未返回有效结论，按错题处理。"
    student_final_answer = student_text[:300]

    try:
        response_text = call_qwen_plus(system_prompt=system_prompt, user_prompt=user_prompt)
        parsed = parse_json_object(response_text)
        is_correct = _coerce_bool(parsed.get("is_correct"))
        comment_raw = parsed.get("comment")
        if comment_raw is not None:
            comment = str(comment_raw).strip() or comment
        student_final_raw = parsed.get("student_final_answer")
        if student_final_raw is not None and str(student_final_raw).strip():
            student_final_answer = str(student_final_raw).strip()
    except Exception as exc:  # noqa: BLE001
        comment = f"自动评分调用失败，按错题处理：{exc}"

    score = max_score if is_correct else 0.0
    return {
        "label": label,
        "found": found,
        "question_type": question_type,
        "student_final_answer": student_final_answer,
        "is_correct": is_correct,
        "score": score,
        "max_score": max_score,
        "comment": comment,
        "auto_graded": True,
    }


def _build_explanation_rubric_if_missing(q_spec: dict[str, Any]) -> list[dict[str, Any]]:
    existing = q_spec.get("explanation_rubric")
    if isinstance(existing, list) and existing:
        normalized: list[dict[str, Any]] = []
        for idx, item in enumerate(existing, start=1):
            text = str(item).strip()
            if text:
                normalized.append({"point": text, "weight": 1.0, "index": idx})
        if normalized:
            return normalized

    system_prompt = """
You extract explanation rubric points from teacher solution.
Return STRICT JSON only.
"""
    user_prompt = (
        f"question_text: {q_spec.get('question_text', '')}\n"
        f"teacher_solution: {q_spec.get('solution_text', '')}\n\n"
        "Return JSON:\n"
        "{\n"
        '  "rubric_points": ["point1", "point2", "point3"]\n'
        "}\n"
        "Keep 2-6 concise key points."
    )

    try:
        response = call_qwen_plus(system_prompt=system_prompt, user_prompt=user_prompt)
        parsed = parse_json_object(response)
        points = parsed.get("rubric_points")
        if isinstance(points, list):
            result: list[dict[str, Any]] = []
            for idx, point in enumerate(points, start=1):
                text = str(point).strip()
                if text:
                    result.append({"point": text, "weight": 1.0, "index": idx})
            if result:
                return result
    except Exception:
        pass

    return [{"point": "关键解释点是否覆盖", "weight": 1.0, "index": 1}]


def grade_explanation(q_spec: dict[str, Any], student_answer: dict[str, Any] | None) -> dict[str, Any]:
    label = str(q_spec.get("label") or "")
    question_type = str(q_spec.get("question_type") or "explanation")
    max_score = _get_max_score(q_spec)

    found, student_text, _ = _extract_best_student_text(student_answer)
    if not student_text:
        return {
            "label": label,
            "found": found,
            "question_type": question_type,
            "student_final_answer": "",
            "is_correct": False,
            "score": 0.0,
            "max_score": max_score,
            "comment": "未检索到有效学生解释文本。",
            "auto_graded": True,
        }

    rubric = _build_explanation_rubric_if_missing(q_spec)

    system_prompt = """
You grade one explanation question using a rubric.
Return STRICT JSON only.
"""
    user_prompt = (
        f"label: {label}\n"
        f"question_text: {q_spec.get('question_text', '')}\n"
        f"teacher_solution: {q_spec.get('solution_text', '')}\n"
        f"student_text: {student_text}\n"
        f"rubric: {json.dumps(rubric, ensure_ascii=False)}\n\n"
        "For each rubric point, assign point_score in {0, 0.5, 1}.\n"
        "Return JSON:\n"
        "{\n"
        '  "point_scores": [\n'
        "    {\"index\": 1, \"point_score\": 1, \"comment\": \"...\"}\n"
        "  ],\n"
        '  "overall_feedback": "..."\n'
        "}"
    )

    point_scores: list[float] = []
    detailed_comments: list[str] = []
    overall_feedback = ""

    try:
        response = call_qwen_plus(system_prompt=system_prompt, user_prompt=user_prompt)
        parsed = parse_json_object(response)
        score_items = parsed.get("point_scores")
        if isinstance(score_items, list):
            for item in score_items:
                if not isinstance(item, dict):
                    continue
                ps = _coerce_float(item.get("point_score"), 0.0)
                if ps < 0:
                    ps = 0.0
                if ps > 1:
                    ps = 1.0
                # Keep half-step scoring for explanation rubric.
                ps = round(ps * 2) / 2
                point_scores.append(ps)
                cmt = item.get("comment")
                if cmt is not None and str(cmt).strip():
                    detailed_comments.append(str(cmt).strip())
        feedback_raw = parsed.get("overall_feedback")
        if feedback_raw is not None and str(feedback_raw).strip():
            overall_feedback = str(feedback_raw).strip()
    except Exception as exc:  # noqa: BLE001
        overall_feedback = f"解释题自动评分失败：{exc}"

    if not point_scores:
        point_scores = [0.0 for _ in rubric]

    ratio = sum(point_scores) / len(point_scores)
    score = round(max_score * ratio, 2)
    is_correct = score >= max_score * 0.999

    comment_parts = detailed_comments[:3]
    if overall_feedback:
        comment_parts.append(overall_feedback)
    comment = " | ".join(part for part in comment_parts if part) or "已按解释题 rubric 自动评分。"

    return {
        "label": label,
        "found": found,
        "question_type": question_type,
        "student_final_answer": student_text[:500],
        "is_correct": is_correct,
        "score": score,
        "max_score": max_score,
        "comment": comment,
        "auto_graded": True,
    }


def grade_graph_stub(q_spec: dict[str, Any], student_answer: dict[str, Any] | None) -> dict[str, Any]:
    label = str(q_spec.get("label") or "")
    question_type = str(q_spec.get("question_type") or "graph")
    max_score = _get_max_score(q_spec)
    found, student_text, _ = _extract_best_student_text(student_answer)

    return {
        "label": label,
        "found": found,
        "question_type": question_type,
        "student_final_answer": student_text[:500],
        "is_correct": False,
        "score": None,
        "max_score": max_score,
        "comment": "TODO: 图形/混合题暂不自动精评分，请人工复核。",
        "auto_graded": False,
    }


def grade_one_question(q_spec: dict[str, Any], student_answer: dict[str, Any] | None) -> dict[str, Any]:
    """Dispatch grading by question_type.

    Returned per-question schema:
    {
      "label": "1.a",
      "found": true,
      "question_type": "numeric|expression|graph|explanation|mixed",
      "student_final_answer": "...",
      "is_correct": true/false,
      "score": number | null,
      "max_score": number,
      "comment": "...",
      "auto_graded": true/false
    }
    """

    question_type = str(q_spec.get("question_type") or "mixed").strip().lower()

    if question_type in {"numeric", "expression"}:
        return grade_numeric_or_expression(q_spec, student_answer)
    if question_type == "explanation":
        return grade_explanation(q_spec, student_answer)
    if question_type in {"graph", "mixed"}:
        return grade_graph_stub(q_spec, student_answer)

    fallback = dict(q_spec)
    fallback["question_type"] = "mixed"
    return grade_graph_stub(fallback, student_answer)
