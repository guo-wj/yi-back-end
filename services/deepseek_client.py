"""DeepSeek OpenAI 兼容 API 封装。"""

from functools import lru_cache

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from config import settings
from services.ai_errors import map_ai_error, raise_service_not_configured
from services.openai_factory import make_async_openai_client


@lru_cache
def _client() -> AsyncOpenAI:
    return make_async_openai_client(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )


async def chat_completion(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> str:
    if not settings.deepseek_api_key:
        raise_service_not_configured(env_key="DEEPSEEK_API_KEY", context="chat")

    client = _client()
    kwargs: dict = {
        "model": model or settings.deepseek_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

    try:
        resp = await client.chat.completions.create(**kwargs)
    except (APIConnectionError, RateLimitError, APIStatusError) as exc:
        raise map_ai_error(exc, context="chat") from exc

    choice = resp.choices[0].message
    return (choice.content or "").strip()
