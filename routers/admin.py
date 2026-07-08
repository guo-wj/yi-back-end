"""管理后台 API。"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from services import admin_db
from services.admin_service import (
    admin_from_token,
    admin_grant_points,
    admin_set_member,
    verify_admin_login,
)
from services.points_service import MEMBER_TIERS

router = APIRouter()


def _require_admin(authorization: str | None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ValueError("未登录，请先登录。")
    token = authorization[7:].strip()
    if not token:
        raise ValueError("未登录，请先登录。")
    return admin_from_token(token)


class AdminLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class AdminLoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    username: str


class AdminMeResponse(BaseModel):
    username: str
    role: str


class PaginatedUsers(BaseModel):
    items: list[dict]
    total: int
    page: int
    page_size: int


class PaginatedOrders(BaseModel):
    items: list[dict]
    total: int
    page: int
    page_size: int


class PaginatedTransactions(BaseModel):
    items: list[dict]
    total: int
    page: int
    page_size: int


class GrantPointsRequest(BaseModel):
    amount: int = Field(..., description="正数发放，负数扣减")
    note: str = Field(default="", max_length=200)


class SetMemberRequest(BaseModel):
    tier: str = Field(..., description="none/yiyou/yishi/yizun")
    days: int | None = Field(default=30, ge=0, le=3650, description="会员天数，tier=none 时忽略")


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(body: AdminLoginRequest) -> AdminLoginResponse:
    token = verify_admin_login(body.username, body.password)
    if not token:
        raise ValueError("用户名或密码错误。")
    return AdminLoginResponse(token=token, username=body.username)


@router.get("/me", response_model=AdminMeResponse)
async def admin_me(authorization: str | None = Header(default=None)) -> AdminMeResponse:
    admin = _require_admin(authorization)
    return AdminMeResponse(username=admin["username"], role=admin["role"])


@router.get("/stats/overview")
async def stats_overview(authorization: str | None = Header(default=None)) -> dict:
    _require_admin(authorization)
    return await asyncio.to_thread(admin_db.get_overview_stats)


@router.get("/stats/features")
async def stats_features(
    authorization: str | None = Header(default=None),
    days: int = 30,
) -> list[dict]:
    _require_admin(authorization)
    return await asyncio.to_thread(admin_db.get_feature_usage_stats, days)


@router.get("/stats/trends")
async def stats_trends(
    authorization: str | None = Header(default=None),
    days: int = 14,
) -> dict:
    _require_admin(authorization)
    return await asyncio.to_thread(admin_db.get_daily_trends, days)


@router.get("/users", response_model=PaginatedUsers)
async def list_users(
    authorization: str | None = Header(default=None),
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
) -> PaginatedUsers:
    _require_admin(authorization)
    page_size = min(max(1, page_size), 100)
    items, total = await asyncio.to_thread(
        admin_db.list_users, page=page, page_size=page_size, keyword=keyword
    )
    for item in items:
        tier = item.get("member_tier", "none")
        item["member_label"] = MEMBER_TIERS.get(tier, MEMBER_TIERS["none"])["label"]
    return PaginatedUsers(items=items, total=total, page=page, page_size=page_size)


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    authorization: str | None = Header(default=None),
) -> dict:
    _require_admin(authorization)
    user = await asyncio.to_thread(admin_db.get_user_detail, user_id)
    if not user:
        raise ValueError("用户不存在。")
    tier = user.get("member_tier", "none")
    user["member_label"] = MEMBER_TIERS.get(tier, MEMBER_TIERS["none"])["label"]
    user["member_discount"] = MEMBER_TIERS.get(tier, MEMBER_TIERS["none"])["discount"]
    return user


@router.get("/users/{user_id}/transactions", response_model=PaginatedTransactions)
async def get_user_transactions(
    user_id: int,
    authorization: str | None = Header(default=None),
    page: int = 1,
    page_size: int = 20,
) -> PaginatedTransactions:
    _require_admin(authorization)
    page_size = min(max(1, page_size), 50)
    items, total = await asyncio.to_thread(
        admin_db.list_user_transactions, user_id, page=page, page_size=page_size
    )
    return PaginatedTransactions(items=items, total=total, page=page, page_size=page_size)


@router.post("/users/{user_id}/points")
async def grant_user_points(
    user_id: int,
    body: GrantPointsRequest,
    authorization: str | None = Header(default=None),
) -> dict:
    _require_admin(authorization)
    return await admin_grant_points(user_id, body.amount, body.note)


@router.post("/users/{user_id}/member")
async def set_user_member(
    user_id: int,
    body: SetMemberRequest,
    authorization: str | None = Header(default=None),
) -> dict:
    _require_admin(authorization)
    return await admin_set_member(user_id, body.tier, body.days)


@router.get("/orders", response_model=PaginatedOrders)
async def list_orders(
    authorization: str | None = Header(default=None),
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    order_type: str | None = None,
    user_id: int | None = None,
) -> PaginatedOrders:
    _require_admin(authorization)
    page_size = min(max(1, page_size), 100)
    items, total = await asyncio.to_thread(
        admin_db.list_orders,
        page=page,
        page_size=page_size,
        status=status,
        order_type=order_type,
        user_id=user_id,
    )
    return PaginatedOrders(items=items, total=total, page=page, page_size=page_size)
