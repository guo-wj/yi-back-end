"""面向用户的 AI 调用错误文案（不暴露具体模型/供应商）。"""

import logging
from typing import NoReturn

from openai import APIConnectionError, APIStatusError, RateLimitError

logger = logging.getLogger(__name__)

AI_BUSY = "AI 服务繁忙，请稍后再试。"
AI_CONNECTION = "AI 服务连接失败，请检查网络后重试。"
AI_UNAVAILABLE = "AI 服务暂不可用，请稍后再试。"
AI_FAILED = "AI 服务调用失败，请稍后重试。"


def map_ai_error(exc: Exception, *, context: str = "ai") -> ValueError:
    """将 OpenAI 兼容 SDK 异常映射为用户可见 ValueError，详细原因仅写日志。"""
    if isinstance(exc, APIConnectionError):
        logger.warning("%s connection error: %s", context, exc)
        return ValueError(AI_CONNECTION)
    if isinstance(exc, RateLimitError):
        logger.warning("%s rate limit: %s", context, exc)
        return ValueError(AI_BUSY)
    if isinstance(exc, APIStatusError):
        logger.warning("%s status error: %s", context, exc)
        return ValueError(AI_UNAVAILABLE)
    logger.exception("%s unexpected error", context)
    return ValueError(AI_FAILED)


def raise_service_not_configured(*, env_key: str, context: str) -> NoReturn:
    """服务未配置：日志记录 env 变量名，对用户返回通用提示。"""
    logger.error("%s not configured (%s missing)", context, env_key)
    raise ValueError(AI_UNAVAILABLE)
