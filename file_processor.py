"""统一文档处理工具：DOCX/PDF -> 每页 base64 PNG data URL。

独立脚本，不依赖项目其他模块（不 import qwen_service / db.py，避免触发
DATABASE_URL 等环境变量强制要求）。
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import fitz  # PyMuPDF


def find_soffice() -> str:
    """探测 LibreOffice 可执行文件路径。

    优先级: 环境变量 SOFFICE_PATH > shutil.which("libreoffice")
    > shutil.which("soffice") > macOS 默认安装位置。
    """

    env_path = os.environ.get("SOFFICE_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    which_path = shutil.which("libreoffice") or shutil.which("soffice")
    if which_path:
        return which_path

    mac_default = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    if os.path.isfile(mac_default):
        return mac_default

    raise RuntimeError(
        "未找到 LibreOffice (soffice) 可执行文件。\n"
        "macOS 请安装: brew install --cask libreoffice\n"
        "Docker/Linux 请安装: apt-get install libreoffice-core libreoffice-writer\n"
        "也可设置环境变量 SOFFICE_PATH 指向 soffice 可执行文件路径。"
    )


def convert_docx_to_pdf(docx_path: str, output_dir: str) -> str:
    """将 DOCX 转换为 PDF，返回生成的 PDF 路径。"""

    soffice = find_soffice()
    os.makedirs(output_dir, exist_ok=True)

    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", output_dir, docx_path],
        check=True,
        timeout=60,
    )

    pdf_path = os.path.join(output_dir, f"{Path(docx_path).stem}.pdf")
    if not os.path.isfile(pdf_path):
        raise RuntimeError(f"LibreOffice 转换失败，未生成 PDF: {pdf_path}")
    return pdf_path


def pdf_to_images(pdf_path: str, dpi: int = 200) -> list[str]:
    """将 PDF 每一页渲染为 base64 PNG data URL。"""

    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)

    images: list[str] = []
    document = fitz.open(pdf_path)
    try:
        for page in document:
            pixmap = page.get_pixmap(matrix=matrix)
            encoded = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
            images.append(f"data:image/png;base64,{encoded}")
    finally:
        document.close()
    return images


def process_document(file_path: str, output_dir: str | None = None) -> list[str]:
    """统一入口: .doc/.docx 先转 PDF 再拆页; .pdf 直接拆页。"""

    if output_dir is None:
        output_dir = tempfile.mkdtemp()

    suffix = Path(file_path).suffix.lower()
    if suffix in (".doc", ".docx"):
        pdf_path = convert_docx_to_pdf(file_path, output_dir)
        return pdf_to_images(pdf_path)
    if suffix == ".pdf":
        return pdf_to_images(file_path)

    raise ValueError(f"不支持的文件格式: {suffix}")
