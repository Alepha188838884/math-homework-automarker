from __future__ import annotations

# DEPRECATED: text/spec pipeline retained for rollback; qwen_service now uses vision pipeline.

import json
import re
from pathlib import Path
from typing import Any

from docx import Document

from qwen_client import call_qwen_plus, parse_json_object


QUESTION_TYPES = {"numeric", "expression", "graph", "explanation", "mixed"}


def _file_fingerprint(path: Path) -> str:
    stat = path.stat()
    return f"{int(stat.st_mtime)}-{stat.st_size}"


def _guess_label_from_text(text: str, index: int) -> str:
    patterns = [
        r"^\s*(\d+\s*[\.]\s*[a-zA-Z])",
        r"^\s*(\d+\s*\([a-zA-Z]+\))",
        r"^\s*(\d+\s*[\.]\s*\d+)",
        r"^\s*(\d+[a-zA-Z])",
        r"^\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            label = re.sub(r"\s+", "", match.group(1))
            label = label.replace("(", ".").replace(")", "")
            return label
    return str(index)


def _ensure_unique_labels(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, int] = {}
    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(items, start=1):
        raw_label = str(item.get("label") or idx).strip() or str(idx)
        label = raw_label
        if label in seen:
            seen[label] += 1
            label = f"{label}.{seen[label]}"
        else:
            seen[label] = 1
        cloned = dict(item)
        cloned["label"] = label
        normalized.append(cloned)
    return normalized


def extract_raw_blocks_from_docx(path: str) -> list[dict[str, Any]]:
    """Read docx and merge contiguous non-empty paragraphs into raw blocks.

    Returns:
        [{"raw_block": "...", "page_hint": 1}, ...]
    """

    docx_path = Path(path).expanduser().resolve()
    document = Document(str(docx_path))

    blocks: list[dict[str, Any]] = []
    bucket: list[str] = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            if bucket:
                blocks.append({"raw_block": "\n".join(bucket).strip(), "page_hint": 1})
                bucket = []
            continue
        bucket.append(text)

    if bucket:
        blocks.append({"raw_block": "\n".join(bucket).strip(), "page_hint": 1})

    if not blocks:
        blocks = [{"raw_block": "", "page_hint": 1}]

    return blocks


def infer_question_structure_with_qwen_long(raw_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compatibility wrapper for the old qwen-long structure step.

    Returns:
        [{"label": "1.a", "raw_block": "...", "page_hint": 1}, ...]
    """

    inferred_items: list[dict[str, Any]] = []
    # qwen-long path disabled; keep local label guessing fallback only.

    by_index = {item["index"]: item["label"] for item in inferred_items}
    structured: list[dict[str, Any]] = []
    for idx, block in enumerate(raw_blocks, start=1):
        raw_block = str(block.get("raw_block", ""))
        label = by_index.get(idx) or _guess_label_from_text(raw_block, idx)
        structured.append(
            {
                "label": label,
                "raw_block": raw_block,
                "page_hint": block.get("page_hint", 1),
            }
        )

    return _ensure_unique_labels(structured)


def enrich_question_with_qwen_plus(block: dict[str, Any]) -> dict[str, Any]:
    """Extract question details from one raw block using qwen-3.5-plus.

    Returns:
        {
          "label": "1.a",
          "question_text": "...",
          "solution_text": "...",
          "question_type": "numeric|expression|graph|explanation|mixed",
          "max_score": 1.0,
          "explanation_rubric": ["..."] | None
        }
    """

    label = str(block.get("label") or "").strip()
    raw_block = str(block.get("raw_block") or "")

    system_prompt = """
You convert one teacher solution block into structured question data.
Return STRICT JSON only.
"""
    user_prompt = (
        f"label: {label}\n"
        f"raw_block:\n{raw_block}\n\n"
        "Return JSON fields:\n"
        "question_text: string\n"
        "solution_text: string\n"
        "question_type: one of numeric/expression/graph/explanation/mixed\n"
        "max_score: number\n"
        "explanation_rubric: array of key points (only for explanation/mixed, else empty array)"
    )

    question_text = raw_block
    solution_text = raw_block
    question_type = "mixed"
    max_score = 1.0
    explanation_rubric: list[str] = []

    try:
        response_text = call_qwen_plus(system_prompt=system_prompt, user_prompt=user_prompt)
        parsed = parse_json_object(response_text)

        q_text = parsed.get("question_text")
        s_text = parsed.get("solution_text")
        q_type = parsed.get("question_type")
        q_max = parsed.get("max_score")
        rubric = parsed.get("explanation_rubric")

        if isinstance(q_text, str) and q_text.strip():
            question_text = q_text.strip()
        if isinstance(s_text, str) and s_text.strip():
            solution_text = s_text.strip()
        if isinstance(q_type, str) and q_type.strip() in QUESTION_TYPES:
            question_type = q_type.strip()
        if isinstance(q_max, (int, float)) and float(q_max) > 0:
            max_score = float(q_max)
        if isinstance(rubric, list):
            explanation_rubric = [str(item).strip() for item in rubric if str(item).strip()]
    except Exception:
        pass

    if question_type not in QUESTION_TYPES:
        question_type = "mixed"

    return {
        "label": label,
        "question_text": question_text,
        "solution_text": solution_text,
        "question_type": question_type,
        "max_score": max_score,
        "explanation_rubric": explanation_rubric or None,
    }


def generate_teacher_spec(docx_path: str, output_path: str) -> None:
    """Generate teacher_spec.json from docx.

    teacher_spec JSON schema:
    {
      "meta": {"docx_path": "...", "source_fingerprint": "..."},
      "questions": [
        {
          "label": "1.a",
          "question_text": "...",
          "solution_text": "...",
          "question_type": "numeric|expression|graph|explanation|mixed",
          "max_score": 1.0,
          "explanation_rubric": ["..."] | null
        }
      ]
    }
    """

    docx_file = Path(docx_path).expanduser().resolve()
    output_file = Path(output_path).expanduser().resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    fingerprint = _file_fingerprint(docx_file)

    if output_file.exists():
        try:
            existing = json.loads(output_file.read_text(encoding="utf-8"))
            existing_meta = existing.get("meta", {}) if isinstance(existing, dict) else {}
            if existing_meta.get("source_fingerprint") == fingerprint:
                return
        except Exception:
            pass

    raw_blocks = extract_raw_blocks_from_docx(str(docx_file))
    structured_blocks = infer_question_structure_with_qwen_long(raw_blocks)

    questions: list[dict[str, Any]] = []
    for block in structured_blocks:
        questions.append(enrich_question_with_qwen_plus(block))

    questions = _ensure_unique_labels(questions)

    teacher_spec = {
        "meta": {
            "docx_path": str(docx_file),
            "source_fingerprint": fingerprint,
        },
        "questions": questions,
    }
    output_file.write_text(json.dumps(teacher_spec, ensure_ascii=False, indent=2), encoding="utf-8")
