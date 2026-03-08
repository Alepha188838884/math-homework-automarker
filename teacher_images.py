from __future__ import annotations

import json
import mimetypes
import shutil
from pathlib import Path
from typing import Iterator

from docx import Document
from docx.oxml.ns import nsmap, qn


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
BASE_DIR = Path(__file__).resolve().parent
TEACHER_CACHE_ROOT = BASE_DIR / "data" / "teacher"
CACHE_META_FILENAME = "source_meta.json"


def _list_image_paths(folder: Path) -> list[str]:
    if not folder.exists():
        return []
    image_paths = [
        path.resolve()
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]
    return [str(path) for path in sorted(image_paths)]


def _guess_extension(content_type: str | None, fallback_name: str | None) -> str:
    ext = mimetypes.guess_extension(content_type or "")
    if not ext and fallback_name:
        ext = Path(fallback_name).suffix.lower()

    if not ext:
        return ".png"

    ext = ext.lower()
    if ext in {".jpe", ".jfif"}:
        return ".jpg"
    if ext not in IMAGE_SUFFIXES:
        return ".png"
    return ext


def _extract_embedded_images(document: Document, element: object) -> Iterator[tuple[bytes, str]]:
    blips = element.xpath(".//a:blip[@r:embed]", namespaces=nsmap)
    for blip in blips:
        rel_id = blip.get(qn("r:embed"))
        if not rel_id:
            continue
        image_part = document.part.related_parts.get(rel_id)
        if image_part is None:
            continue
        ext = _guess_extension(
            getattr(image_part, "content_type", None),
            str(getattr(image_part, "partname", "")),
        )
        blob = getattr(image_part, "blob", None)
        if not isinstance(blob, (bytes, bytearray)):
            continue
        yield bytes(blob), ext


def _reset_cache_dirs(question_dir: Path, solution_dir: Path) -> None:
    if question_dir.exists():
        shutil.rmtree(question_dir)
    if solution_dir.exists():
        shutil.rmtree(solution_dir)
    question_dir.mkdir(parents=True, exist_ok=True)
    solution_dir.mkdir(parents=True, exist_ok=True)


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
    if not isinstance(source_path, str) or not isinstance(source_fingerprint, str):
        return None
    return {
        "source_path": source_path,
        "source_fingerprint": source_fingerprint,
    }


def _write_cache_meta(meta_path: Path, source_path: Path, source_fingerprint: str) -> None:
    payload = {
        "source_path": str(source_path),
        "source_fingerprint": source_fingerprint,
    }
    meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_teacher_images(answer_file_id: int, docx_path: str) -> tuple[list[str], list[str]]:
    """
    Ensure question/solution images are extracted from teacher docx into cache folders.

    Cache paths:
      data/teacher/<answer_file_id>/questions/
      data/teacher/<answer_file_id>/solutions/
    """

    if answer_file_id <= 0:
        raise RuntimeError("answer_file_id 无效，无法建立老师图片缓存。")

    source_path = Path(docx_path).expanduser().resolve()
    if not source_path.exists():
        raise RuntimeError(f"老师答案文件不存在: {source_path}")
    source_fingerprint = _build_source_fingerprint(source_path)

    teacher_dir = TEACHER_CACHE_ROOT / str(answer_file_id)
    question_dir = teacher_dir / "questions"
    solution_dir = teacher_dir / "solutions"
    meta_path = teacher_dir / CACHE_META_FILENAME

    cached_questions = _list_image_paths(question_dir)
    cached_solutions = _list_image_paths(solution_dir)
    cache_meta = _read_cache_meta(meta_path)
    if (
        cached_questions
        and cached_solutions
        and cache_meta is not None
        and cache_meta.get("source_path") == str(source_path)
        and cache_meta.get("source_fingerprint") == source_fingerprint
    ):
        return cached_questions, cached_solutions

    _reset_cache_dirs(question_dir, solution_dir)

    document = Document(str(source_path))

    seen_solution_divider = False
    divider_found = False
    question_index = 0
    solution_index = 0

    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            paragraph_text = "".join(node.text or "" for node in child.xpath(".//w:t", namespaces=nsmap)).strip()
            if paragraph_text.lower() == "solution":
                seen_solution_divider = True
                divider_found = True
                continue

        for image_blob, image_ext in _extract_embedded_images(document, child):
            if not seen_solution_divider:
                question_index += 1
                target_path = question_dir / f"q_{question_index}{image_ext}"
            else:
                solution_index += 1
                target_path = solution_dir / f"s_{solution_index}{image_ext}"
            target_path.write_bytes(image_blob)

    if not divider_found:
        raise RuntimeError("老师答案 Word 中未找到 'Solution' 分隔行。")
    if question_index == 0:
        raise RuntimeError("老师答案 Word 在 Solution 之前未找到题目图片。")
    if solution_index == 0:
        raise RuntimeError("老师答案 Word 在 Solution 之后未找到解答图片。")

    questions = _list_image_paths(question_dir)
    solutions = _list_image_paths(solution_dir)
    if not questions or not solutions:
        raise RuntimeError("老师图片提取失败，请检查 Word 文件内容。")

    _write_cache_meta(meta_path, source_path, source_fingerprint)

    return questions, solutions
