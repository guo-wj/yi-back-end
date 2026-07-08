"""邮箱验证码登录业务逻辑：发码、验码、查/建用户、签发 JWT。"""

from __future__ import annotations

import asyncio
import re
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from config import settings
from services import auth_db
from services.email_service import send_code_email
from services.redis_client import get_redis


def _code_key(email: str) -> str:
    return f"auth:code:{email}"


def _cooldown_key(email: str) -> str:
    return f"auth:cooldown:{email}"


def _gen_code() -> str:
    """6 位数字验证码（含前导零）。"""
    return f"{secrets.randbelow(10 ** 6):06d}"


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def jwt_expires_in_seconds() -> int:
    """返回 JWT 有效期（秒）；0 表示不设过期。"""
    if settings.jwt_expire_days <= 0:
        return 0
    return settings.jwt_expire_days * 24 * 3600


def _issue_token(user: dict) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user["id"]),
        "email": user.get("email"),
        "phone": user.get("phone"),
        "iat": now,
    }
    if settings.jwt_expire_days > 0:
        payload["exp"] = now + timedelta(days=settings.jwt_expire_days)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def send_code(email: str) -> int:
    """生成验证码 → 存 Redis → 发邮件。返回有效期秒数。"""
    email = _normalize_email(email)
    r = get_redis()

    # 重发冷却：避免被刷
    if await r.ttl(_cooldown_key(email)) > 0:
        raise ValueError("验证码发送过于频繁，请稍后再试。")

    code = _gen_code()
    # 先写 Redis 再发信；发信失败则回滚，避免占用冷却但用户收不到
    await r.set(_code_key(email), code, ex=settings.code_ttl_seconds)
    await r.set(_cooldown_key(email), "1", ex=settings.code_resend_seconds)

    try:
        await asyncio.to_thread(send_code_email, email, code)
    except Exception:
        await r.delete(_code_key(email), _cooldown_key(email))
        raise

    return settings.code_ttl_seconds


async def verify_code(email: str, code: str) -> tuple[dict, bool, str]:
    """从 Redis 取码比对 → 通过则查/建用户 → 签发 JWT。

    返回 (用户, 是否新注册, token)。
    """
    email = _normalize_email(email)
    code = code.strip()
    r = get_redis()

    stored = await r.get(_code_key(email))
    if stored is None:
        raise ValueError("验证码不存在或已过期，请重新获取。")
    if not secrets.compare_digest(stored, code):
        raise ValueError("验证码错误，请重新输入。")

    # 验证通过即作废，防止重放
    await r.delete(_code_key(email))

    user, is_new = await asyncio.to_thread(auth_db.get_or_create_user, email)
    token = _issue_token(user)
    return user, is_new, token


_PHONE_RE = re.compile(r"^1\d{10}$")


def _normalize_phone(phone: str) -> str:
    value = phone.strip()
    if not _PHONE_RE.fullmatch(value):
        raise ValueError("请输入有效的 11 位手机号。")
    return value


def _validate_password(password: str) -> str:
    value = password.strip()
    if len(value) < 6:
        raise ValueError("密码至少 6 位。")
    if len(value) > 64:
        raise ValueError("密码过长。")
    return value


async def register_with_password(
    phone: str,
    password: str,
    invite_code: str | None = None,
) -> tuple[dict, str]:
    """手机号注册，返回 (用户, token)。"""
    from services.auth_password import hash_password

    phone = _normalize_phone(phone)
    password = _validate_password(password)

    existing = await asyncio.to_thread(auth_db.get_user_by_phone, phone)
    if existing:
        raise ValueError("该手机号已注册，请直接登录。")

    code = invite_code.strip() if invite_code else None
    if code == "":
        code = None

    password_hash = hash_password(password)
    user = await asyncio.to_thread(
        auth_db.create_phone_user, phone, password_hash, code
    )
    token = _issue_token(user)
    return user, token


async def login_with_password(phone: str, password: str) -> tuple[dict, str]:
    """手机号密码登录，返回 (用户, token)。"""
    from services.auth_password import verify_password

    phone = _normalize_phone(phone)
    password = _validate_password(password)

    user = await asyncio.to_thread(auth_db.get_user_by_phone, phone)
    if not user:
        raise ValueError("账号不存在，请先注册。")

    stored = user.get("password_hash")
    if not stored or not verify_password(password, stored):
        raise ValueError("密码错误，请重试。")

    user["last_login"] = await asyncio.to_thread(
        auth_db.touch_last_login, user["id"]
    )
    token = _issue_token(user)
    return user, token


_EMAIL_ACCOUNT_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _is_phone_account(account: str) -> bool:
    return bool(_PHONE_RE.fullmatch(account))


def _normalize_account(account: str) -> tuple[str, str]:
    """识别账号类型并归一化，返回 (account_type, normalized_value)。"""
    value = account.strip()
    if not value:
        raise ValueError("请输入手机号或邮箱。")

    if "@" in value:
        email = _normalize_account_email(value)
        return "email", email

    if _is_phone_account(value):
        return "phone", _normalize_phone(value)

    raise ValueError("请输入有效的手机号或邮箱。")


def _normalize_account_email(email: str) -> str:
    value = _normalize_email(email)
    if not _EMAIL_ACCOUNT_RE.fullmatch(value):
        raise ValueError("请输入有效的邮箱。")
    if value.endswith(auth_db._PHONE_EMAIL_SUFFIX):
        raise ValueError("邮箱格式无效。")
    return value


async def register_email_with_password(
    email: str,
    password: str,
    invite_code: str | None = None,
) -> tuple[dict, str]:
    """邮箱注册，返回 (用户, token)。"""
    from services.auth_password import hash_password

    email = _normalize_account_email(email)
    password = _validate_password(password)

    existing = await asyncio.to_thread(auth_db.get_user_by_email, email)
    if existing:
        raise ValueError("该邮箱已注册，请直接登录。")

    code = invite_code.strip() if invite_code else None
    if code == "":
        code = None

    password_hash = hash_password(password)
    user = await asyncio.to_thread(
        auth_db.create_email_user, email, password_hash, code
    )
    token = _issue_token(user)
    return user, token


async def login_email_with_password(email: str, password: str) -> tuple[dict, str]:
    """邮箱密码登录，返回 (用户, token)。"""
    from services.auth_password import verify_password

    email = _normalize_account_email(email)
    password = _validate_password(password)

    user = await asyncio.to_thread(auth_db.get_user_by_email, email)
    if not user:
        raise ValueError("账号不存在，请先注册。")

    stored = user.get("password_hash")
    if not stored or not verify_password(password, stored):
        raise ValueError("密码错误，请重试。")

    user["last_login"] = await asyncio.to_thread(
        auth_db.touch_last_login, user["id"]
    )
    token = _issue_token(user)
    return user, token


async def register_account(
    account: str,
    password: str,
    invite_code: str | None = None,
) -> tuple[dict, str]:
    """手机号或邮箱注册，返回 (用户, token)。"""
    kind, normalized = _normalize_account(account)
    if kind == "phone":
        return await register_with_password(normalized, password, invite_code)
    return await register_email_with_password(normalized, password, invite_code)


async def login_account(account: str, password: str) -> tuple[dict, str]:
    """手机号或邮箱登录，返回 (用户, token)。"""
    kind, normalized = _normalize_account(account)
    if kind == "phone":
        return await login_with_password(normalized, password)
    return await login_email_with_password(normalized, password)


def user_from_token(token: str) -> dict:
    """校验 JWT 并返回用户记录；无效或用户不存在时抛出 ValueError。"""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise ValueError("登录已失效，请重新登录。") from exc

    sub = payload.get("sub")
    if not sub:
        raise ValueError("登录已失效，请重新登录。")

    try:
        user_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise ValueError("登录已失效，请重新登录。") from exc

    user = auth_db.get_user_by_id(user_id)
    if not user:
        raise ValueError("用户不存在，请重新登录。")
    return user
