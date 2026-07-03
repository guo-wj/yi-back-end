"""应用配置：从环境变量读取 API Key 等敏感项。"""

import os

from dotenv import load_dotenv

# override=True：uvicorn reload 的子进程会继承主进程的旧环境变量，须用 .env 最新值覆盖
load_dotenv(override=True)


class Settings:
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    app_name: str = os.getenv("APP_NAME", "易鉴后端")
    debug: bool = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")

    # Redis（验证码存储）
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # SMTP 邮件（发送验证码）
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "465"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    # 显示发件人，未配置时回退为登录账号
    smtp_from: str = os.getenv("SMTP_FROM", "") or os.getenv("SMTP_USER", "")
    smtp_from_name: str = os.getenv("SMTP_FROM_NAME", "易鉴")
    # 465 用 SSL，587 用 STARTTLS
    smtp_use_ssl: bool = os.getenv("SMTP_USE_SSL", "true").lower() in ("1", "true", "yes")

    # 验证码策略
    code_ttl_seconds: int = int(os.getenv("CODE_TTL_SECONDS", "300"))  # 有效期 5 分钟
    code_resend_seconds: int = int(os.getenv("CODE_RESEND_SECONDS", "60"))  # 重发冷却

    # JWT 签发
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-change-me-please-use-a-long-random-string")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expire_days: int = int(os.getenv("JWT_EXPIRE_DAYS", "7"))

    # SQLite 用户库
    sqlite_path: str = os.getenv("SQLITE_PATH", "yi.db")

    # GPT-4o 视觉（掌纹/面相特征提取）
    vision_api_key: str = os.getenv("VISION_API_KEY", "")
    vision_api_url: str = os.getenv(
        "VISION_API_URL",
        "https://aigateway.edgecloudapp.com/v1/dd49a827f86db98f499afcb77642ca6b/aicenter_gpt_chat",
    )
    vision_model: str = os.getenv("VISION_MODEL", "gpt-4o")
    palm_max_image_bytes: int = int(os.getenv("PALM_MAX_IMAGE_BYTES", "5242880"))
    palm_image_max_side: int = int(os.getenv("PALM_IMAGE_MAX_SIDE", "768"))
    palm_jpeg_quality: int = int(os.getenv("PALM_JPEG_QUALITY", "75"))
    # True：一次视觉调用同时出特征+解读（慢，不推荐）；False：并行提特征 + DeepSeek 解读
    vision_single_stage: bool = os.getenv("VISION_SINGLE_STAGE", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    palm_feature_max_tokens: int = int(os.getenv("PALM_FEATURE_MAX_TOKENS", "512"))
    vision_max_output_tokens: int = int(os.getenv("VISION_MAX_OUTPUT_TOKENS", "1800"))
    interpret_max_tokens: int = int(os.getenv("INTERPRET_MAX_TOKENS", "1000"))


settings = Settings()
