from __future__ import annotations

import json
import os
import time
from json import JSONDecodeError
from typing import Any

from openai import OpenAI


DASHSCOPE_BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_PLUS_MODEL = os.getenv("QWEN_PLUS_MODEL", "qwen3.5-plus")


def _normalize_api_key(raw_value: str) -> str:
    key = raw_value.strip()
    if len(key) >= 2 and key[0] == key[-1] and key[0] in {"'", '"'}:
        key = key[1:-1].strip()
    return key


def _is_placeholder_key(key: str) -> bool:
    lowered = key.lower()
    placeholders = {
        "your_dashscope_api_key",
        "your_dasscope_api_key",
        "your_api_key",
        "your_key",
        "replace_me",
        "changeme",
    }
    if lowered in placeholders:
        return True

    prefix_markers = ("your", "replace", "changeme", "change_me")
    if lowered.startswith(prefix_markers):
        return True
    if "dashscope" in lowered and "api" in lowered and "key" in lowered and "your" in lowered:
        return True
    return False


def get_dashscope_api_key() -> str:
    """Read DashScope key from environment variables.

    Configure your API key via environment variable. Supported names:
    - DASHSCOPE_API_KEY
    - DASSCOPE_API_KEY
    - DASHSCOPE_APIKEY
    - QWEN_API_KEY
    - OPENAI_API_KEY
    """

    candidates = (
        "DASHSCOPE_API_KEY",
        "DASSCOPE_API_KEY",
        "DASHSCOPE_APIKEY",
        "QWEN_API_KEY",
        "OPENAI_API_KEY",
    )
    placeholder_sources: list[str] = []
    for name in candidates:
        raw = os.getenv(name)
        if raw is None:
            continue
        key = _normalize_api_key(raw)
        if not key:
            continue
        if _is_placeholder_key(key):
            placeholder_sources.append(name)
            continue
        return key

    if placeholder_sources:
        joined = ", ".join(placeholder_sources)
        raise RuntimeError(f"Detected placeholder API key in {joined}. Please set a real DashScope key.")

    raise RuntimeError(
        "Missing DashScope API key. Set DASHSCOPE_API_KEY "
        "(or DASSCOPE_API_KEY / DASHSCOPE_APIKEY / QWEN_API_KEY / OPENAI_API_KEY)."
    )


def get_openai_client() -> OpenAI:
    return OpenAI(api_key=get_dashscope_api_key(), base_url=DASHSCOPE_BASE_URL)


def _extract_text_from_completion(completion: Any) -> str:
    choices = getattr(completion, "choices", None)
    if not choices:
        raise RuntimeError("Qwen returned empty choices.")

    message = choices[0].message
    content = message.content

    if isinstance(content, str):
        text = content.strip()
        if not text:
            raise RuntimeError("Qwen returned empty text.")
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

    raise RuntimeError("Unsupported response content format from Qwen.")


def _build_messages(system_prompt: str, user_prompt: str, system_file_refs: str | None = None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt.strip()}]
    if system_file_refs:
        messages.append({"role": "system", "content": system_file_refs.strip()})
    messages.append({"role": "user", "content": user_prompt.strip()})
    return messages


def _call_model(
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    *,
    system_file_refs: str | None = None,
    temperature: float = 0,
    max_retries: int = 2,
) -> str:
    """Call one Qwen model with simple retry.

    max_retries=2 means total at most 3 attempts (1 initial + 2 retries).
    """

    messages = _build_messages(system_prompt=system_prompt, user_prompt=user_prompt, system_file_refs=system_file_refs)

    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            client = get_openai_client()
            completion = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
            )
            return _extract_text_from_completion(completion)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= max_retries:
                break
            backoff_seconds = 2**attempt
            time.sleep(backoff_seconds)

    raise RuntimeError(f"Qwen call failed after retries: {last_exc}")


def call_qwen_plus(system_prompt: str, user_prompt: str) -> str:
    """Call qwen3.5-plus for per-question analysis/reasoning tasks."""

    return _call_model(model_name=QWEN_PLUS_MODEL, system_prompt=system_prompt, user_prompt=user_prompt)


def call_qwen_plus_with_files(system_prompt: str, user_prompt: str, system_file_refs: str) -> str:
    """Internal helper for qwen3.5-plus with file references via fileid://..."""

    return _call_model(
        model_name=QWEN_PLUS_MODEL,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        system_file_refs=system_file_refs,
    )


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse first JSON object from model output."""

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        raise RuntimeError("Top-level JSON is not an object.")
    except JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[index:])
            if isinstance(obj, dict):
                return obj
        except JSONDecodeError:
            continue

    raise RuntimeError("Unable to parse JSON object from model output.")
