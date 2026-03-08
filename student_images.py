from __future__ import annotations

import shutil
from pathlib import Path

import fitz


BASE_DIR = Path(__file__).resolve().parent
STUDENT_TMP_ROOT = BASE_DIR / "data" / "tmp" / "submissions"


def export_student_pdf_to_images(submission_id: int, pdf_path: str) -> list[str]:
    """
    Export student PDF pages as PNG files to data/tmp/submissions/<submission_id>/.

    Returns image paths in page order.
    """

    if submission_id <= 0:
        raise RuntimeError("submission_id 无效，无法建立学生临时图片目录。")

    source_path = Path(pdf_path).expanduser().resolve()
    if not source_path.exists():
        raise RuntimeError(f"学生提交 PDF 不存在: {source_path}")

    target_dir = STUDENT_TMP_ROOT / str(submission_id)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    image_paths: list[str] = []
    with fitz.open(str(source_path)) as document:
        if document.page_count <= 0:
            raise RuntimeError("学生提交 PDF 没有可导出的页面。")

        for page_index, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
            page_path = target_dir / f"page_{page_index}.png"
            pixmap.save(str(page_path))
            image_paths.append(str(page_path.resolve()))

    if not image_paths:
        raise RuntimeError("学生提交 PDF 导图失败，未生成任何页面图片。")
    return image_paths


def cleanup_student_tmp_images(submission_id: int) -> None:
    target_dir = STUDENT_TMP_ROOT / str(submission_id)
    if target_dir.exists():
        shutil.rmtree(target_dir)
