"""多视觉模型供应商验证脚本（豆包 / 通义千问对比批改效果）。

独立 CLI 脚本，不接入主项目，不 import qwen_service.py（import 它会因为
db.py 的 DATABASE_URL 强制要求而在没有配置数据库环境变量时报错）。

批改指令文本改写自 qwen_service.py 中 `_build_vision_messages` 函数内的
system_prompt (约第 185-196 行) 与 user_prompt 的 JSON 结构说明
(约第 198-241 行)：核心的“先匹配题目、再评分、严格 JSON 输出”逻辑与
JSON 字段保持一致；因为本脚本只有“教师答案文件”和“学生作业文件”两组图片
（不像 qwen_service 那样把老师题目图和标准解答图拆成两组、按图片序号区间
定位），所以把三组图片 + 序号区间的描述精简为两组图片 + 页码文字标签
（【教师答案第N页】/【学生作业第N页】），其余批改要求原样保留。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from typing import Any

from openai import AsyncOpenAI

from file_processor import process_document

GRADING_PROMPT = """
你是严格的数学作业视觉批改助手。
你会按顺序接收两组图片：1) 教师答案图（可能包含题目与解答）；2) 学生作答图。

你必须先做“题目内容匹配”，再做评分：
- 匹配依据是题目内容本身，不依赖纸面题号。
- 只有在确认匹配成功后，才允许自动评分。
- 若无法确认匹配或证据不足，必须标记为人工复核。

请执行：
1. 依据教师答案图，识别所有题块，生成内部题号 Q1, Q2, ...。
2. 对每个 Qi，在学生图中找同题内容并评估 question_match。
3. 若 question_match=false 或信心不足，必须设置：
   auto_graded=false, score=null, is_correct=null。
4. 仅当 question_match=true 时，结合教师答案图进行评分。

请只输出以下 JSON 结构，不要 Markdown，不要额外文字：
{
  "questions": [
    {
      "question_id": "Q1",
      "question_brief": "...",
      "question_match": true,
      "question_match_confidence": 0.95,
      "auto_graded": true,
      "score": 1,
      "max_score": 1,
      "is_correct": true,
      "student_final_answer": "...",
      "comment": "..."
    }
  ],
  "summary": {
    "total_score": 1,
    "max_total_score": 1,
    "auto_graded_count": 1,
    "manual_review_count": 0
  }
}

硬约束：
- 每个教师题块必须有且仅有一条 questions 记录。
- 不要输出 JSON 之外的任何内容。
"""

PROVIDER_CONFIGS: dict[str, dict[str, Any]] = {
    "doubao": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "api_key_env": "ARK_API_KEY",
        "model_env": "DOUBAO_VISION_MODEL",
        "default_model": None,
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key_env": "DASHSCOPE_API_KEY",
        "model_env": "QWEN_VISION_MODEL",
        "default_model": "qwen-vl-max",
    },
}


def extract_json_object(text: str) -> tuple[Any, str | None]:
    """从模型返回文本中提取第一个完整 JSON 对象。

    返回 (parsed, error_message)：解析成功时 error_message 为 None；
    失败时 parsed 为 None，error_message 为中文错误说明。
    """

    stripped = (text or "").strip()
    if not stripped:
        return None, "返回文本为空"

    try:
        return json.loads(stripped), None
    except json.JSONDecodeError:
        pass

    brace_index = stripped.find("{")
    if brace_index == -1:
        return None, "未在返回文本中找到 JSON 内容"

    try:
        parsed, _ = json.JSONDecoder().raw_decode(stripped[brace_index:])
        return parsed, None
    except json.JSONDecodeError as exc:
        return None, f"JSON 解析失败: {exc}"


def build_messages(answer_images: list[str], student_images: list[str]) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "text", "text": GRADING_PROMPT.strip()}]

    for index, image_url in enumerate(answer_images, start=1):
        content.append({"type": "text", "text": f"【教师答案第{index}页】"})
        content.append({"type": "image_url", "image_url": {"url": image_url}})

    for index, image_url in enumerate(student_images, start=1):
        content.append({"type": "text", "text": f"【学生作业第{index}页】"})
        content.append({"type": "image_url", "image_url": {"url": image_url}})

    return [{"role": "user", "content": content}]


async def call_provider(
    name: str, config: dict[str, Any], messages: list[dict[str, Any]]
) -> dict[str, Any]:
    api_key = os.environ.get(config["api_key_env"])
    if not api_key:
        print(f"[{name}] 缺少环境变量 {config['api_key_env']}，已跳过该模型。")
        return {
            "provider": name,
            "skipped": True,
            "reason": f"缺少环境变量 {config['api_key_env']}",
        }

    model = os.environ.get(config["model_env"], config["default_model"])
    if not model:
        print(
            f"[{name}] 缺少环境变量 {config['model_env']}，"
            "请到方舟控制台确认最新视觉模型 Model ID 后设置该环境变量。已跳过该模型。"
        )
        return {
            "provider": name,
            "skipped": True,
            "reason": f"缺少环境变量 {config['model_env']}",
        }

    client = AsyncOpenAI(
        base_url=config["base_url"],
        api_key=api_key,
        timeout=120.0,
        max_retries=1,
    )

    extra_kwargs: dict[str, Any] = {}
    if name == "doubao":
        extra_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

    result: dict[str, Any] = {"provider": name, "model": model, "skipped": False}
    start = time.monotonic()
    try:
        completion = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            **extra_kwargs,
        )
        result["elapsed_seconds"] = round(time.monotonic() - start, 2)

        raw_text = completion.choices[0].message.content
        if isinstance(raw_text, list):
            raw_text = "".join(
                (part.get("text", "") if isinstance(part, dict) else str(getattr(part, "text", "")))
                for part in raw_text
            )

        result["success"] = True
        result["raw_text"] = raw_text

        parsed, parse_error_message = extract_json_object(raw_text or "")
        result["parsed"] = parsed
        result["parse_error"] = parse_error_message is not None
        if parse_error_message is not None:
            result["parse_error_message"] = parse_error_message
    except Exception as exc:  # noqa: BLE001 - 记录任意 provider 调用异常，不中断其他 provider
        result["elapsed_seconds"] = round(time.monotonic() - start, 2)
        result["success"] = False
        result["error"] = str(exc)

    return result


async def run(args: argparse.Namespace) -> list[dict[str, Any]]:
    answer_images = process_document(args.answer_file)
    print(f"教师答案文件共 {len(answer_images)} 页")
    if not answer_images:
        print("错误：教师答案文件未生成任何页面图片，无法进行批改。")
        sys.exit(1)

    student_images = process_document(args.student_file)
    print(f"学生作业文件共 {len(student_images)} 页")
    if not student_images:
        print("错误：学生作业文件未生成任何页面图片，无法进行批改。")
        sys.exit(1)

    messages = build_messages(answer_images, student_images)

    provider_names = [name.strip() for name in args.providers.split(",") if name.strip()]

    tasks = []
    task_providers = []
    for name in provider_names:
        config = PROVIDER_CONFIGS.get(name)
        if not config:
            print(f"未知的 provider: {name}，已跳过。")
            continue
        tasks.append(call_provider(name, config, messages))
        task_providers.append(name)

    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[dict[str, Any]] = []
    for name, raw in zip(task_providers, raw_results):
        if isinstance(raw, BaseException):
            results.append(
                {
                    "provider": name,
                    "skipped": False,
                    "success": False,
                    "error": str(raw),
                }
            )
        else:
            results.append(raw)
    return results


def print_summary(results: list[dict[str, Any]]) -> None:
    print("\n=== 对比摘要 ===")
    for result in results:
        provider = result.get("provider")
        if result.get("skipped"):
            print(f"{provider}: 已跳过 ({result.get('reason')})")
            continue

        if result.get("success"):
            question_count = "未知"
            parsed = result.get("parsed")
            if isinstance(parsed, dict) and isinstance(parsed.get("questions"), list):
                question_count = len(parsed["questions"])
            print(
                f"{provider} (model={result.get('model')}): 成功, "
                f"耗时 {result.get('elapsed_seconds')}s, "
                f"题目数量={question_count}, "
                f"parse_error={result.get('parse_error')}"
            )
        else:
            print(
                f"{provider} (model={result.get('model')}): 失败, "
                f"耗时 {result.get('elapsed_seconds')}s, "
                f"错误={result.get('error')}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="多视觉模型供应商批改效果对比验证脚本")
    parser.add_argument("--answer-file", required=True, help="教师答案文件路径（.docx 或 .pdf）")
    parser.add_argument("--student-file", required=True, help="学生作业文件路径（.pdf）")
    parser.add_argument(
        "--providers", default="doubao,qwen", help="逗号分隔的 provider 列表，默认 doubao,qwen"
    )
    parser.add_argument("--output", default="validate_results.json", help="结果 JSON 保存路径")
    args = parser.parse_args()

    results = asyncio.run(run(args))
    print_summary(results)

    with open(args.output, "w", encoding="utf-8") as output_file:
        json.dump(results, output_file, ensure_ascii=False, indent=2)
    print(f"\n完整结果已写入 {args.output}")


if __name__ == "__main__":
    main()
