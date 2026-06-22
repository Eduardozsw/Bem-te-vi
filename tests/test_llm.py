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
