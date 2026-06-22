import os

import litellm

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def complete(system: str, user: str, max_tokens: int = 4096) -> str:
    kwargs = {
        "model": os.getenv("LLM_MODEL", DEFAULT_MODEL),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
    }
    api_base = os.getenv("LLM_API_BASE")
    if api_base:
        kwargs["api_base"] = api_base
    api_key = os.getenv("LLM_API_KEY")
    if api_key:
        kwargs["api_key"] = api_key
    response = litellm.completion(**kwargs)
    return response.choices[0].message.content
