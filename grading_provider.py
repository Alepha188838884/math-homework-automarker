"""视觉批改供应商接入层：豆包（方舟 ARK）为主、Qwen 为备选。

Prompt 与 build_messages 原样移植自 validate_providers.py（已通过真实调用验证），
不得 import db.py / models.py 等触发 DATABASE_URL 强制要求的模块。
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from openai import OpenAI


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
        "base_url_env": "ARK_BASE_URL",
        "default_base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "api_key_env": "ARK_API_KEY",
        "model_env": "DOUBAO_VISION_MODEL",
        "default_model": "doubao-seed-2-1-turbo-260628",
        "missing_key_message": "未配置 ARK_API_KEY，无法调用豆包批改。",
    },
    "qwen": {
        "base_url_env": "DASHSCOPE_BASE_URL",
        "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key_env": "DASHSCOPE_API_KEY",
        "model_env": "QWEN_VISION_MODEL",
        "default_model": "qwen-vl-max",
        "missing_key_message": "未配置 DASHSCOPE_API_KEY，无法调用 Qwen 批改。",
    },
}


def get_active_provider_name() -> str:
    name = os.environ.get("GRADING_PROVIDER", "doubao").strip().lower()
    if name not in PROVIDER_CONFIGS:
        raise RuntimeError("GRADING_PROVIDER 仅支持 doubao 或 qwen。")
    return name


def build_messages(answer_images: list[str], student_images: list[str]) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "text", "text": GRADING_PROMPT.strip()}]

    for index, image_url in enumerate(answer_images, start=1):
        content.append({"type": "text", "text": f"【教师答案第{index}页】"})
        content.append({"type": "image_url", "image_url": {"url": image_url}})

    for index, image_url in enumerate(student_images, start=1):
        content.append({"type": "text", "text": f"【学生作业第{index}页】"})
        content.append({"type": "image_url", "image_url": {"url": image_url}})

    return [{"role": "user", "content": content}]


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


def _extract_text_from_completion(completion: Any) -> str:
    choices = getattr(completion, "choices", None)
    if not choices:
        raise RuntimeError("视觉模型返回为空。")

    message = choices[0].message
    content = message.content

    if isinstance(content, str):
        text = content.strip()
        if not text:
            raise RuntimeError("视觉模型返回文本为空。")
        return text

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                item_text = item.get("text")
            else:
                item_text = getattr(item, "text", None)
            if item_text:
                parts.append(str(item_text))
        merged = "\n".join(parts).strip()
        if merged:
            return merged

    raise RuntimeError("视觉模型返回内容格式不支持。")


def call_grading_model(answer_images: list[str], student_images: list[str]) -> tuple[dict[str, Any], str]:
    """调用当前激活的视觉批改供应商，返回 (解析后的 JSON dict, 实际使用的 model id)。"""

    provider = get_active_provider_name()
    config = PROVIDER_CONFIGS[provider]

    api_key = os.environ.get(config["api_key_env"])
    if not api_key:
        raise RuntimeError(config["missing_key_message"])

    base_url = os.environ.get(config["base_url_env"]) or config["default_base_url"]
    model = os.environ.get(config["model_env"]) or config["default_model"]

    client = OpenAI(base_url=base_url, api_key=api_key, timeout=120, max_retries=0)

    extra_kwargs: dict[str, Any] = {}
    if provider == "doubao":
        extra_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

    messages = build_messages(answer_images, student_images)

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                **extra_kwargs,
            )
            raw_text = _extract_text_from_completion(completion)
            parsed, error_message = extract_json_object(raw_text)
            if error_message is not None:
                raise RuntimeError(f"视觉模型输出解析失败: {error_message}")
            if not isinstance(parsed, dict):
                raise RuntimeError("视觉模型输出不是 JSON 对象。")
            questions = parsed.get("questions")
            if not isinstance(questions, list):
                raise RuntimeError("视觉模型输出缺少 questions 数组。")
            return parsed, model
        except Exception as exc:  # noqa: BLE001 - 统一重试, 最终失败时抛出最后一次异常
            last_exc = exc
            if attempt < 2:
                time.sleep(1 if attempt == 0 else 2)

    raise RuntimeError(f"视觉模型调用失败: {last_exc}")
