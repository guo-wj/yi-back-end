"""智谱 OpenAI 兼容视觉 API 封装。"""

from functools import lru_cache

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from config import settings
from services.ai_errors import map_ai_error, raise_service_not_configured
from services.openai_factory import make_async_openai_client


@lru_cache
def _client() -> AsyncOpenAI:
    return make_async_openai_client(
        api_key=settings.zhipu_api_key,
        base_url=settings.zhipu_base_url,
    )


async def vision_completion(
    system_prompt: str,
    user_text: str,
    image_data_url: str,
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> str:
    """发送单张图片的图文消息。"""
    return await vision_completion_multi(
        system_prompt,
        user_text,
        [image_data_url],
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


async def vision_completion_multi(
    system_prompt: str,
    user_text: str,
    image_data_urls: list[str],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> str:
    """发送多张图片的图文消息，返回模型文本回复。"""
    if not settings.zhipu_api_key:
        raise_service_not_configured(env_key="ZHIPU_API_KEY", context="vision")
    if not image_data_urls:
        raise ValueError("未提供图片。")

    content: list[dict] = [{"type": "text", "text": user_text}]
    for url in image_data_urls:
        content.append({"type": "image_url", "image_url": {"url": url}})

    token_limit = max_tokens if max_tokens is not None else settings.vision_max_output_tokens

    client = _client()
    try:
        resp = await client.chat.completions.create(
            model=model or settings.zhipu_vision_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            temperature=temperature,
            max_tokens=token_limit,
            extra_body={"thinking": {"type": "disabled"}},
        )
    except (APIConnectionError, RateLimitError, APIStatusError) as exc:
        raise map_ai_error(exc, context="vision") from exc

    choice = resp.choices[0].message
    return (choice.content or "").strip()
