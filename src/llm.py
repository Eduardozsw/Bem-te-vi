import logging
import os

import litellm

from src.run_status import RunStatus

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_NUM_RETRIES = 3
DEFAULT_TIMEOUT = 60.0  # segundos por tentativa


def current_model() -> str:
    return os.getenv("LLM_MODEL", DEFAULT_MODEL)


def _record_usage(response, status: RunStatus) -> None:
    usage = getattr(response, "usage", None)
    prompt = getattr(usage, "prompt_tokens", 0) or 0
    completion = getattr(usage, "completion_tokens", 0) or 0
    try:
        cost = float(litellm.completion_cost(completion_response=response))
    except Exception as e:  # modelo sem preço na tabela do LiteLLM (ex.: local)
        logger.warning("Could not compute LLM cost: %s", e)
        cost = None
    status.record_usage(int(prompt), int(completion), cost)


def complete(
    system: str,
    user: str,
    max_tokens: int = 4096,
    status: RunStatus | None = None,
) -> str:
    kwargs = {
        "model": current_model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        # LiteLLM refaz a chamada com backoff em erros transitórios (rate limit, 5xx, timeout)
        "num_retries": int(os.getenv("LLM_NUM_RETRIES", DEFAULT_NUM_RETRIES)),
        "timeout": float(os.getenv("LLM_TIMEOUT", DEFAULT_TIMEOUT)),
    }
    api_base = os.getenv("LLM_API_BASE")
    if api_base:
        kwargs["api_base"] = api_base
    api_key = os.getenv("LLM_API_KEY")
    if api_key:
        kwargs["api_key"] = api_key
    response = litellm.completion(**kwargs)
    if status is not None:
        _record_usage(response, status)
    content = response.choices[0].message.content
    if content is None:
        raise ValueError("LLM returned empty content")
    return content
