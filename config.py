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
    # 0 表示 JWT 不设 exp，登录态仅在前端手动退出或清除本地存储时失效
    jwt_expire_days: int = int(os.getenv("JWT_EXPIRE_DAYS", "0"))

    # SQLite 用户库
    sqlite_path: str = os.getenv("SQLITE_PATH", "yi.db")

    # 管理后台（yi-admin）
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "admin123")

    # GPT-4o 视觉（掌纹/面相特征提取）
    vision_api_key: str = os.getenv("VISION_API_KEY", "")
    vision_api_url: str = os.getenv(
        "VISION_API_URL",
        "https://aigateway.edgecloudapp.com/v1/dd49a827f86db98f499afcb77642ca6b/aicenter_gpt_chat",
    )
    vision_model: str = os.getenv("VISION_MODEL", "gpt-4o")
    palm_max_image_bytes: int = int(os.getenv("PALM_MAX_IMAGE_BYTES", "5242880"))
    palm_image_max_side: int = int(os.getenv("PALM_IMAGE_MAX_SIDE", "512"))
    palm_jpeg_quality: int = int(os.getenv("PALM_JPEG_QUALITY", "70"))
    # True：一次视觉调用同时出特征+解读（慢，不推荐）；False：并行提特征 + DeepSeek 解读
    vision_single_stage: bool = os.getenv("VISION_SINGLE_STAGE", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    palm_feature_max_tokens: int = int(os.getenv("PALM_FEATURE_MAX_TOKENS", "380"))
    vision_image_detail: str = os.getenv("VISION_IMAGE_DETAIL", "low")
    # 单阶段 analyze（VISION_SINGLE_STAGE）视觉输出上限
    vision_max_output_tokens: int = int(os.getenv("VISION_MAX_OUTPUT_TOKENS", "1500"))
    # 面相识象（/extract）：结构化 JSON，单独限 token
    face_feature_max_tokens: int = int(os.getenv("FACE_FEATURE_MAX_TOKENS", "800"))
    interpret_max_tokens: int = int(os.getenv("INTERPRET_MAX_TOKENS", "2800"))
    # 灵签 AI 参详：输出较短，单独限 token 以加快响应
    lottery_interpret_max_tokens: int = int(os.getenv("LOTTERY_INTERPRET_MAX_TOKENS", "900"))
    # 六爻/梅花 AI 解卦：输出较短，单独限 token
    gua_interpret_max_tokens: int = int(os.getenv("GUA_INTERPRET_MAX_TOKENS", "1000"))
    # 八字 AI 断语：按关注维度略增输出，单独限 token
    bazi_interpret_max_tokens: int = int(os.getenv("BAZI_INTERPRET_MAX_TOKENS", "1300"))
    # 掌纹/面相 AI 解读：结构化 JSON，单独限 token
    palm_interpret_max_tokens: int = int(os.getenv("PALM_INTERPRET_MAX_TOKENS", "1500"))
    face_interpret_max_tokens: int = int(os.getenv("FACE_INTERPRET_MAX_TOKENS", "1500"))

    # 掌纹/面相识象（/extract）每日次数上限（各会员档共用，测试可调）
    palm_extract_daily: int = int(os.getenv("PALM_EXTRACT_DAILY", "20"))
    face_extract_daily: int = int(os.getenv("FACE_EXTRACT_DAILY", "20"))


settings = Settings()
