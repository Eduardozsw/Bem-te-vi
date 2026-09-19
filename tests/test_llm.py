import os
from unittest.mock import patch, MagicMock

from src.llm import complete, DEFAULT_MODEL


def _mock_completion(content="resposta"):
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=content))]
    return resp


def test_complete_uses_default_model_when_unset():
    with patch.dict(os.environ, {}, clear=True), \
         patch("litellm.completion", return_value=_mock_completion()) as mock_c:
        complete("sys", "usr")
    assert mock_c.call_args.kwargs["model"] == DEFAULT_MODEL


def test_complete_honors_llm_model_env():
    with patch.dict(os.environ, {"LLM_MODEL": "ollama/qwen2.5:7b"}, clear=True), \
         patch("litellm.completion", return_value=_mock_completion()) as mock_c:
        complete("sys", "usr")
    assert mock_c.call_args.kwargs["model"] == "ollama/qwen2.5:7b"


def test_complete_includes_api_base_and_key_when_set():
    env = {"LLM_API_BASE": "http://localhost:11434", "LLM_API_KEY": "k"}
    with patch.dict(os.environ, env, clear=True), \
         patch("litellm.completion", return_value=_mock_completion()) as mock_c:
        complete("sys", "usr")
    kwargs = mock_c.call_args.kwargs
    assert kwargs["api_base"] == "http://localhost:11434"
    assert kwargs["api_key"] == "k"


def test_complete_omits_api_base_and_key_when_unset():
    with patch.dict(os.environ, {}, clear=True), \
         patch("litellm.completion", return_value=_mock_completion()) as mock_c:
        complete("sys", "usr")
    kwargs = mock_c.call_args.kwargs
    assert "api_base" not in kwargs
    assert "api_key" not in kwargs


def test_complete_passes_messages_and_max_tokens():
    with patch.dict(os.environ, {}, clear=True), \
         patch("litellm.completion", return_value=_mock_completion()) as mock_c:
        complete("the system", "the user", max_tokens=2048)
    kwargs = mock_c.call_args.kwargs
    assert kwargs["max_tokens"] == 2048
    assert kwargs["messages"] == [
        {"role": "system", "content": "the system"},
        {"role": "user", "content": "the user"},
    ]


def test_complete_returns_message_content():
    with patch.dict(os.environ, {}, clear=True), \
         patch("litellm.completion", return_value=_mock_completion("olá")):
        assert complete("sys", "usr") == "olá"


def test_complete_raises_value_error_when_content_is_none():
    with patch.dict(os.environ, {}, clear=True), \
         patch("litellm.completion", return_value=_mock_completion(None)):
        import pytest
        with pytest.raises(ValueError, match="LLM returned empty content"):
            complete("sys", "usr")


def test_complete_passes_default_retries_and_timeout():
    from src.llm import DEFAULT_NUM_RETRIES, DEFAULT_TIMEOUT
    with patch.dict(os.environ, {}, clear=True), \
         patch("litellm.completion", return_value=_mock_completion()) as mock_c:
        complete("sys", "usr")
    kwargs = mock_c.call_args.kwargs
    assert kwargs["num_retries"] == DEFAULT_NUM_RETRIES
    assert kwargs["timeout"] == DEFAULT_TIMEOUT


def test_complete_honors_retry_and_timeout_env():
    env = {"LLM_NUM_RETRIES": "5", "LLM_TIMEOUT": "12.5"}
    with patch.dict(os.environ, env, clear=True), \
         patch("litellm.completion", return_value=_mock_completion()) as mock_c:
        complete("sys", "usr")
    kwargs = mock_c.call_args.kwargs
    assert kwargs["num_retries"] == 5
    assert kwargs["timeout"] == 12.5


def _mock_with_usage(prompt=100, completion=20):
    resp = _mock_completion()
    resp.usage = MagicMock(prompt_tokens=prompt, completion_tokens=completion)
    return resp


def test_complete_records_usage_and_cost_in_status():
    from src.run_status import RunStatus
    status = RunStatus()
    with patch.dict(os.environ, {}, clear=True), \
         patch("litellm.completion", return_value=_mock_with_usage(100, 20)), \
         patch("litellm.completion_cost", return_value=0.0015):
        complete("sys", "usr", status=status)
        complete("sys", "usr", status=status)
    assert status.prompt_tokens == 200
    assert status.completion_tokens == 40
    assert status.total_cost_usd == 0.003


def test_complete_marks_cost_unknown_when_pricing_fails():
    from src.run_status import RunStatus
    status = RunStatus()
    with patch.dict(os.environ, {}, clear=True), \
         patch("litellm.completion", return_value=_mock_with_usage(10, 5)), \
         patch("litellm.completion_cost", side_effect=Exception("model not mapped")):
        assert complete("sys", "usr", status=status) == "resposta"
    assert status.prompt_tokens == 10
    assert status.cost_unknown is True
    assert status.total_cost_usd is None
