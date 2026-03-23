from __future__ import annotations

import io
import shutil
from pathlib import Path

import fitz
from PIL import Image

from runtime_config import get_app_data_dir


STUDENT_TMP_ROOT = get_app_data_dir() / "tmp" / "submissions"


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

    try:
        document = fitz.open(str(source_path))
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(target_dir, ignore_errors=True)
        raise RuntimeError("学生提交 PDF 文件无效，请检查文件是否为有效且非空的 PDF。") from exc

    image_paths: list[str] = []
    try:
        if document.page_count == 0:
            raise RuntimeError("学生提交 PDF 文件无效，请检查文件是否为有效且非空的 PDF。")

        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
            page_path = target_dir / f"page_{page_index + 1}.png"
            image_bytes = pixmap.tobytes("png")
            with Image.open(io.BytesIO(image_bytes)) as image:
                grayscale = image.convert("L")
                grayscale.save(page_path, format="PNG")
                grayscale.close()
            image_paths.append(str(page_path.resolve()))
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(target_dir, ignore_errors=True)
        raise RuntimeError("学生提交 PDF 导图失败，请检查文件内容是否完整。") from exc
    finally:
        document.close()

    if not image_paths:
        shutil.rmtree(target_dir, ignore_errors=True)
        raise RuntimeError("学生提交 PDF 导图失败，未生成任何页面图片。")
    return image_paths


def cleanup_student_tmp_images(submission_id: int) -> None:
    target_dir = STUDENT_TMP_ROOT / str(submission_id)
    if target_dir.exists():
        shutil.rmtree(target_dir)
