from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from qwen_service import PIPELINE_MODEL_NAME, auto_grade_homework
from student_images import cleanup_student_tmp_images


def _validate_input_file(path: Path, expected_suffix: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    if path.suffix.lower() != expected_suffix:
        raise ValueError(f"文件后缀必须是 {expected_suffix}: {path}")


def _file_fingerprint(path: Path) -> str:
    stat = path.stat()
    return f"{path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}"


def _build_cache_prefix(answer_docx: Path, student_pdf: Path) -> str:
    seed = f"{_file_fingerprint(answer_docx)}|{_file_fingerprint(student_pdf)}"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]
    return f"quick_{digest}"


def grade_files(answer_docx: Path, student_pdf: Path) -> dict[str, Any]:
    _validate_input_file(answer_docx, ".docx")
    _validate_input_file(student_pdf, ".pdf")

    print(f"[1/3] 运行视觉批改流水线: {PIPELINE_MODEL_NAME}")
    cache_prefix = _build_cache_prefix(answer_docx, student_pdf)
    payload = auto_grade_homework(
        teacher_docx=str(answer_docx),
        student_pdf=str(student_pdf),
        answer_file_id=None,
        submission_id=None,
        cache_prefix=cache_prefix,
    )

    runtime_ids = payload.get("runtime_ids", {})
    submission_tmp_id = runtime_ids.get("submission_id")
    if isinstance(submission_tmp_id, int):
        cleanup_student_tmp_images(submission_tmp_id)

    print("[2/3] 读取视觉模型输出...")
    print("[3/3] 完成")
    return {
        "pipeline_model": PIPELINE_MODEL_NAME,
        "raw_model_json": payload.get("raw_model_json", {}),
        "normalized": payload.get("normalized", {}),
        "artifacts": payload.get("artifacts", {}),
        "runtime_ids": runtime_ids,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="指定官方答案 DOCX + 学生作业 PDF，运行视觉批改并输出结果。"
    )
    parser.add_argument("--answer-docx", required=True, help="官方答案 DOCX 路径")
    parser.add_argument("--student-pdf", required=True, help="学生作业 PDF 路径")
    parser.add_argument("--output", default="", help="可选：把结果 JSON 保存到文件路径")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    answer_docx = Path(args.answer_docx).expanduser().resolve()
    student_pdf = Path(args.student_pdf).expanduser().resolve()

    try:
        result = grade_files(answer_docx, student_pdf)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1

    result_text = json.dumps(result, ensure_ascii=False, indent=2)
    print("\n批改结果：")
    print(result_text)

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.write_text(result_text, encoding="utf-8")
        print(f"\n结果已保存到: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
