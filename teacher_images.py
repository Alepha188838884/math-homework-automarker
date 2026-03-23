from __future__ import annotations

import io
import json
import shutil
from pathlib import Path
from zipfile import BadZipFile

from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from docx.oxml.ns import qn
from PIL import Image

from runtime_config import get_app_data_dir


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
TEACHER_CACHE_ROOT = get_app_data_dir() / "teacher"
CACHE_META_FILENAME = "source_meta.json"
CACHE_META_VERSION = "paragraph-run-image-v2"


def _list_image_paths(folder: Path) -> list[str]:
    if not folder.exists():
        return []
    image_paths = [
        path.resolve()
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]
    return [str(path) for path in sorted(image_paths)]


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
    extractor_version = raw.get("extractor_version")
    if (
        not isinstance(source_path, str)
        or not isinstance(source_fingerprint, str)
        or not isinstance(extractor_version, str)
    ):
        return None
    return {
        "source_path": source_path,
        "source_fingerprint": source_fingerprint,
        "extractor_version": extractor_version,
    }


def _write_cache_meta(meta_path: Path, source_path: Path, source_fingerprint: str) -> None:
    payload = {
        "source_path": str(source_path),
        "source_fingerprint": source_fingerprint,
        "extractor_version": CACHE_META_VERSION,
    }
    meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _iter_run_images(document: Document, paragraph: object):
    for run in getattr(paragraph, "runs", []):
        drawings = run.element.xpath(".//w:drawing")
        if not drawings:
            continue
        for drawing in drawings:
            blips = drawing.xpath(".//a:blip")
            for blip in blips:
                rel_id = blip.get(qn("r:embed"))
                if not rel_id:
                    continue
                image_part = document.part.related_parts.get(rel_id)
                if image_part is None:
                    continue
                image_bytes = getattr(image_part, "blob", None)
                if not isinstance(image_bytes, (bytes, bytearray)):
                    continue
                yield bytes(image_bytes)


def _save_grayscale_png(image_bytes: bytes, target_path: Path) -> None:
    with Image.open(io.BytesIO(image_bytes)) as image:
        grayscale = image.convert("L")
        grayscale.save(target_path, format="PNG")
        grayscale.close()


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
        and cache_meta.get("extractor_version") == CACHE_META_VERSION
    ):
        return cached_questions, cached_solutions

    _reset_cache_dirs(question_dir, solution_dir)

    try:
        document = Document(str(source_path))
    except (PackageNotFoundError, BadZipFile, ValueError) as exc:
        shutil.rmtree(teacher_dir, ignore_errors=True)
        raise RuntimeError("老师答案 Word 文件无效，请检查文件是否为有效且非空的 .docx。") from exc

    try:
        seen_solution_divider = False
        divider_found = False
        question_index = 0
        solution_index = 0

        for paragraph in document.paragraphs:
            paragraph_text = paragraph.text.strip().lower()
            if not seen_solution_divider and "solution" in paragraph_text:
                seen_solution_divider = True
                divider_found = True
                continue

            for image_bytes in _iter_run_images(document, paragraph):
                if not seen_solution_divider:
                    question_index += 1
                    target_path = question_dir / f"q_{question_index}.png"
                else:
                    solution_index += 1
                    target_path = solution_dir / f"s_{solution_index}.png"
                _save_grayscale_png(image_bytes, target_path)

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
    except Exception:
        shutil.rmtree(teacher_dir, ignore_errors=True)
        raise
