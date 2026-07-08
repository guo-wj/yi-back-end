import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from openai import APIConnectionError, APIStatusError, RateLimitError
from starlette.responses import JSONResponse

from config import settings
from routers import api_router
from services.ai_errors import AI_BUSY, AI_CONNECTION, AI_UNAVAILABLE

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # 与 allow_origins=["*"] 不能同时为 True，否则浏览器会拒绝跨域（抽签等前端调不通）
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str | bool]:
    """健康检查；vision_configured / deepseek_configured 便于排查部署漏配 Key。"""
    return {
        "status": "ok",
        "vision_configured": bool(settings.vision_api_key),
        "deepseek_configured": bool(settings.deepseek_api_key),
    }


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(APIConnectionError)
async def api_connection_error_handler(_: Request, exc: APIConnectionError):
    logger.warning("AI connection error: %s", exc)
    return JSONResponse(
        status_code=502,
        content={"detail": AI_CONNECTION},
    )


@app.exception_handler(RateLimitError)
async def rate_limit_error_handler(_: Request, exc: RateLimitError):
    logger.warning("AI rate limit: %s", exc)
    return JSONResponse(
        status_code=429,
        content={"detail": AI_BUSY},
    )


@app.exception_handler(APIStatusError)
async def api_status_error_handler(_: Request, exc: APIStatusError):
    logger.warning("AI status error: %s", exc)
    return JSONResponse(status_code=502, content={"detail": AI_UNAVAILABLE})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        # 改 .env 也触发热重载（配合 config 的 load_dotenv(override=True) 才能生效）
        reload_includes=["*.py", ".env"],
    )
