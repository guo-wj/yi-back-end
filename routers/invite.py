"""邀请 API：校验邀请码、邀请统计。"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel, Field

from services.auth_service import user_from_token
from services.points_service import (
    INVITEE_BONUS,
    INVITER_BONUS,
    INVITER_MONTHLY_CAP,
    REGISTER_BONUS,
    get_invite_stats,
    validate_invite_code,
)

router = APIRouter()


def _optional_user(authorization: str | None) -> dict | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization[7:].strip()
    if not token:
        return None
    try:
        return user_from_token(token)
    except ValueError:
        return None


def _require_user(authorization: str | None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ValueError("未登录，请先登录。")
    token = authorization[7:].strip()
    if not token:
        raise ValueError("未登录，请先登录。")
    return user_from_token(token)


class InviteValidateResponse(BaseModel):
    valid: bool
    message: str


class InviteStatsResponse(BaseModel):
    referral_code: str
    invite_count: int = 0
    points_earned_total: int = 0
    points_earned_this_month: int = 0
    monthly_cap: int = Field(default=INVITER_MONTHLY_CAP)
    monthly_cap_remaining: int = 0
    invitee_bonus: int = Field(default=INVITEE_BONUS)
    inviter_bonus: int = Field(default=INVITER_BONUS)
    register_bonus: int = Field(default=REGISTER_BONUS)


@router.get("/validate", response_model=InviteValidateResponse)
async def invite_validate(
    code: str = Query(..., min_length=1, max_length=32, description="邀请码"),
    authorization: str | None = Header(default=None),
) -> InviteValidateResponse:
    user = await asyncio.to_thread(_optional_user, authorization)
    data = await validate_invite_code(code, user_id=user["id"] if user else None)
    return InviteValidateResponse(**data)


@router.get("/stats", response_model=InviteStatsResponse)
async def invite_stats(authorization: str | None = Header(default=None)) -> InviteStatsResponse:
    user = await asyncio.to_thread(_require_user, authorization)
    data = await get_invite_stats(user["id"])
    return InviteStatsResponse(**data)
