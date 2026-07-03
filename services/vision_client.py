"""GPT-4o 视觉 API 封装（OpenAI 兼容网关）。"""

import httpx

from config import settings
from services.ai_errors import AI_BUSY, AI_CONNECTION, AI_FAILED, AI_UNAVAILABLE, raise_service_not_configured
from services.openai_factory import _http_client


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
    if not settings.vision_api_key:
        raise_service_not_configured(env_key="VISION_API_KEY", context="vision")
    if not image_data_urls:
        raise ValueError("未提供图片。")

    content: list[dict] = [{"type": "text", "text": user_text}]
    for url in image_data_urls:
        content.append({"type": "image_url", "image_url": {"url": url}})

    token_limit = max_tokens if max_tokens is not None else settings.vision_max_output_tokens

    payload = {
        "model": model or settings.vision_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        "temperature": temperature,
        "max_tokens": token_limit,
    }

    client = _http_client()
    try:
        resp = await client.post(
            settings.vision_api_url,
            headers={
                "Authorization": f"Bearer {settings.vision_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 429:
            raise ValueError(AI_BUSY) from exc
        if status >= 500:
            raise ValueError(AI_UNAVAILABLE) from exc
        raise ValueError(AI_FAILED) from exc
    except httpx.RequestError as exc:
        raise ValueError(AI_CONNECTION) from exc

    data = resp.json()
    choice = data["choices"][0]["message"]
    return (choice.get("content") or "").strip()
