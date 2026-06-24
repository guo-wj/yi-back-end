"""创建绕过系统代理的 OpenAI 兼容 Async 客户端。"""

from functools import lru_cache

import httpx
from openai import AsyncOpenAI


@lru_cache
def _http_client() -> httpx.AsyncClient:
    # trust_env=False：避免 http_proxy 指向不可用本地代理（如 127.0.0.1:15236）
    return httpx.AsyncClient(trust_env=False, timeout=120.0)


def make_async_openai_client(*, api_key: str, base_url: str) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        http_client=_http_client(),
    )
