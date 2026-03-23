from __future__ import annotations

# DEPRECATED: legacy text/spec pipeline retained only for rollback; qwen_service now uses vision pipeline.

import json
import re
from pathlib import Path
from typing import Any

import pdfplumber
import fitz

from qwen_client import parse_json_object


def pdf_to_pages_text(pdf_path: str) -> list[dict[str, Any]]:
    """Convert student PDF to page texts.

    Returns:
        [{"page": 1, "text": "..."}, ...]
    """

    path = Path(pdf_path).expanduser().resolve()
    pages: list[dict[str, Any]] = []

    pdfplumber_pages: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pdfplumber_pages.append(text.strip())

    fitz_doc = fitz.open(str(path))
    fitz_pages: list[str] = []
    for page in fitz_doc:
        text = page.get_text("text") or ""
        fitz_pages.append(text.strip())
    fitz_doc.close()

    total_pages = max(len(pdfplumber_pages), len(fitz_pages))
    for i in range(total_pages):
        text_pdfplumber = pdfplumber_pages[i] if i < len(pdfplumber_pages) else ""
        text_fitz = fitz_pages[i] if i < len(fitz_pages) else ""
        chosen = text_pdfplumber if len(text_pdfplumber) >= len(text_fitz) else text_fitz
        pages.append({"page": i + 1, "text": chosen})

    if not pages:
        pages = [{"page": 1, "text": ""}]

    return pages


def _local_candidate_search(label: str, pages: list[dict[str, Any]]) -> dict[str, Any]:
    label_compact = re.sub(r"\s+", "", label).lower()
    for page in pages:
        page_no = int(page.get("page", 1))
        text = str(page.get("text") or "")
        if not text:
            continue

        lines = text.splitlines()
        for line_index, line in enumerate(lines):
            compact_line = re.sub(r"\s+", "", line).lower()
            if label_compact and label_compact in compact_line:
                start = max(0, line_index - 2)
                end = min(len(lines), line_index + 3)
                context = "\n".join(lines[start:end]).strip()
                return {
                    "label": label,
                    "found": True,
                    "candidate_answers": [
                        {
                            "page": page_no,
                            "text": line.strip(),
                            "context": context,
                            "bbox_hint": None,
                        }
                    ],
                }

    return {"label": label, "found": False, "candidate_answers": []}


def _ask_qwen_for_label_answer(
    *,
    label: str,
    question_text: str,
    pages: list[dict[str, Any]],
) -> dict[str, Any]:
    # Legacy model-assisted retrieval is disabled; caller falls back to local candidate search.
    _ = question_text, pages, parse_json_object, json
    return {"label": label, "found": False, "candidate_answers": []}


def locate_answers_legacy(teacher_spec: dict[str, Any], pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Locate student answer snippets by teacher labels using the retired text pipeline.

    Output schema:
    [
      {
        "label": "1.a",
        "found": true,
        "candidate_answers": [
          {"page": 1, "text": "...", "context": "...", "bbox_hint": null}
        ]
      }
    ]
    """

    questions = teacher_spec.get("questions")
    if not isinstance(questions, list):
        raise RuntimeError("teacher_spec.questions must be a list.")

    answers_raw: list[dict[str, Any]] = []
    for question in questions:
        if not isinstance(question, dict):
            continue
        label = str(question.get("label") or "").strip()
        if not label:
            continue

        question_text = str(question.get("question_text") or "")

        try:
            result = _ask_qwen_for_label_answer(label=label, question_text=question_text, pages=pages)
            if not result.get("found"):
                result = _local_candidate_search(label, pages)
        except Exception:
            result = _local_candidate_search(label, pages)

        answers_raw.append(result)

    return answers_raw
