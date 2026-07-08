"""管理后台业务逻辑。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import jwt

from config import settings
from services import admin_db, points_db
from services.points_service import MEMBER_TIERS, grant_points


def issue_admin_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": f"admin:{username}",
        "role": "admin",
        "username": username,
        "iat": int(now.timestamp()),
    }
    if settings.jwt_expire_days > 0:
        payload["exp"] = now + timedelta(days=settings.jwt_expire_days)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_admin_login(username: str, password: str) -> str | None:
    if username != settings.admin_username or password != settings.admin_password:
        return None
    return issue_admin_token(username)


def admin_from_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise ValueError("登录已失效，请重新登录。") from exc

    if payload.get("role") != "admin":
        raise ValueError("无管理员权限。")
    return {
        "username": payload.get("username", "admin"),
        "role": "admin",
    }


async def admin_grant_points(user_id: int, amount: int, note: str) -> dict:
    if amount == 0:
        raise ValueError("调整积分不能为 0。")

    user = await asyncio.to_thread(admin_db.get_user_detail, user_id)
    if not user:
        raise ValueError("用户不存在。")

    points_db.ensure_user_points(user_id)
    if amount > 0:
        result = await grant_points(
            user_id,
            amount,
            feature="admin_grant",
            note=note or "管理员发放",
            idempotency_key=f"admin_grant:{user_id}:{datetime.now(timezone.utc).isoformat()}",
        )
        balance = result["balance"]
    else:
        balance = points_db.update_balance(user_id, amount)
        points_db.insert_transaction(
            user_id=user_id,
            tx_type="consume",
            amount=amount,
            balance_after=balance,
            feature="admin_deduct",
            note=note or "管理员扣减",
        )
    return {"user_id": user_id, "balance": balance, "amount": amount}


async def admin_set_member(user_id: int, tier: str, days: int | None) -> dict:
    if tier not in MEMBER_TIERS:
        raise ValueError(f"无效会员等级：{tier}")

    user = await asyncio.to_thread(admin_db.get_user_detail, user_id)
    if not user:
        raise ValueError("用户不存在。")

    points_db.ensure_user_points(user_id)
    expire_at = None
    if tier != "none" and days and days > 0:
        expire_at = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    points_db.set_member(user_id, tier, expire_at)
    return {
        "user_id": user_id,
        "member_tier": tier,
        "member_label": MEMBER_TIERS[tier]["label"],
        "member_expire_at": expire_at,
    }
