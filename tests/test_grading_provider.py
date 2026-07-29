from __future__ import annotations

import pytest

import grading_provider


class _FakeCompletions:
    def __init__(self, responder):
        self._responder = responder

    def create(self, **kwargs):
        return self._responder(**kwargs)


class _FakeChat:
    def __init__(self, responder):
        self.completions = _FakeCompletions(responder)


class _FakeClient:
    def __init__(self, responder):
        self.chat = _FakeChat(responder)


def test_call_grading_model_retries_three_times_with_backoff_and_reports_cause(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("GRADING_PROVIDER", "doubao")
    monkeypatch.setenv("ARK_API_KEY", "test-ark-key")

    call_count = {"n": 0}

    def failing_create(**kwargs):
        call_count["n"] += 1
        raise RuntimeError("底层网络异常")

    monkeypatch.setattr(grading_provider, "OpenAI", lambda **kwargs: _FakeClient(failing_create))

    sleep_calls: list[float] = []
    monkeypatch.setattr(grading_provider.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    with pytest.raises(RuntimeError) as exc_info:
        grading_provider.call_grading_model(
            ["data:image/png;base64,AAAA"],
            ["data:image/png;base64,BBBB"],
        )

    assert call_count["n"] == 3
    assert sleep_calls == [1, 2]
    assert "视觉模型调用失败" in str(exc_info.value)
    assert "底层网络异常" in str(exc_info.value)


def test_extract_json_object_recovers_json_surrounded_by_noise():
    text = "模型的多余旁白文字\n{\"questions\": [{\"question_id\": \"Q1\"}]}\n结尾多余文字"
    parsed, error = grading_provider.extract_json_object(text)

    assert error is None
    assert parsed == {"questions": [{"question_id": "Q1"}]}


def test_extract_json_object_reports_empty_text():
    parsed, error = grading_provider.extract_json_object("   ")

    assert parsed is None
    assert error == "返回文本为空"


def test_extract_json_object_reports_missing_json_content():
    parsed, error = grading_provider.extract_json_object("这段文本里完全没有花括号内容")

    assert parsed is None
    assert error == "未在返回文本中找到 JSON 内容"


def test_extract_json_object_reports_parse_failure():
    parsed, error = grading_provider.extract_json_object("前缀 { 这不是合法 json ]")

    assert parsed is None
    assert error is not None
    assert error.startswith("JSON 解析失败")


def test_get_active_provider_name_rejects_unknown_provider(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GRADING_PROVIDER", "chatgpt")

    with pytest.raises(RuntimeError, match="GRADING_PROVIDER 仅支持 doubao 或 qwen。"):
        grading_provider.get_active_provider_name()


def test_call_grading_model_reports_missing_doubao_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GRADING_PROVIDER", "doubao")
    monkeypatch.delenv("ARK_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="未配置 ARK_API_KEY，无法调用豆包批改。"):
        grading_provider.call_grading_model([], [])


def test_call_grading_model_reports_missing_qwen_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GRADING_PROVIDER", "qwen")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="未配置 DASHSCOPE_API_KEY，无法调用 Qwen 批改。"):
        grading_provider.call_grading_model([], [])


def test_build_messages_orders_answer_group_before_student_group_with_page_labels():
    messages = grading_provider.build_messages(
        ["data:image/png;base64,AAAA", "data:image/png;base64,BBBB"],
        ["data:image/png;base64,CCCC"],
    )

    assert len(messages) == 1
    assert messages[0]["role"] == "user"

    content = messages[0]["content"]
    assert content[0] == {"type": "text", "text": grading_provider.GRADING_PROMPT.strip()}
    assert content[1] == {"type": "text", "text": "【教师答案第1页】"}
    assert content[2] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}
    assert content[3] == {"type": "text", "text": "【教师答案第2页】"}
    assert content[4] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,BBBB"}}
    assert content[5] == {"type": "text", "text": "【学生作业第1页】"}
    assert content[6] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,CCCC"}}
    assert len(content) == 7
