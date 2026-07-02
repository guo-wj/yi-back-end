"""积分 API：余额、扣减、退还、流水、签到、配额。"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from services.auth_service import user_from_token
from services import points_db
from services.points_service import (
    InsufficientPointsError,
    checkin,
    consume_points,
    get_balance,
    get_quota,
    list_ledger,
    quote_consume,
    refund_points,
)

router = APIRouter()


def _require_user(authorization: str | None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ValueError("未登录，请先登录。")
    token = authorization[7:].strip()
    if not token:
        raise ValueError("未登录，请先登录。")
    return user_from_token(token)


class BalanceResponse(BaseModel):
    balance: int
    member_tier: str
    member_label: str
    member_discount: float
    member_expire_at: str | None = None
    referral_code: str | None = None
    checkin_streak: int = 0
    last_checkin_date: str | None = None


class QuotaResponse(BaseModel):
    feature: str
    free_daily: int
    free_remaining: int
    used_today: int
    reset_at: str


class QuoteResponse(BaseModel):
    feature: str
    base_cost: int
    cost: int
    member_discount: float
    uses_free_quota: bool
    balance: int
    sufficient: bool


class ConsumeRequest(BaseModel):
    feature: str = Field(..., description="功能标识：qian/liuyao/meihua/bazi/palm/face")
    focus_count: int = Field(default=1, ge=1, le=10)
    is_redo: bool = Field(default=False)
    idempotency_key: str | None = Field(default=None, max_length=128)
    meta: dict | None = None


class ConsumeResponse(BaseModel):
    transaction_id: int
    balance: int
    cost: int
    uses_free_quota: bool = False


class RefundRequest(BaseModel):
    transaction_id: int


class CheckinResponse(BaseModel):
    transaction_id: int
    balance: int
    streak: int
    reward: int


class LedgerItem(BaseModel):
    id: int
    type: str
    amount: int
    feature: str | None = None
    note: str | None = None
    balance_after: int
    created_at: str


class LedgerResponse(BaseModel):
    items: list[LedgerItem]
    total: int
    page: int
    page_size: int


@router.get("/balance", response_model=BalanceResponse)
async def points_balance(authorization: str | None = Header(default=None)) -> BalanceResponse:
    user = await asyncio.to_thread(_require_user, authorization)
    data = await get_balance(user["id"])
    return BalanceResponse(**data)


@router.get("/quota", response_model=QuotaResponse)
async def points_quota(
    feature: str,
    authorization: str | None = Header(default=None),
) -> QuotaResponse:
    user = await asyncio.to_thread(_require_user, authorization)
    data = await get_quota(user["id"], feature)
    return QuotaResponse(**data)


@router.get("/quote", response_model=QuoteResponse)
async def points_quote(
    feature: str,
    focus_count: int = 1,
    is_redo: bool = False,
    authorization: str | None = Header(default=None),
) -> QuoteResponse:
    user = await asyncio.to_thread(_require_user, authorization)
    data = await quote_consume(
        user["id"], feature, focus_count=focus_count, is_redo=is_redo
    )
    return QuoteResponse(**data)


@router.post("/consume", response_model=ConsumeResponse)
async def points_consume(
    body: ConsumeRequest,
    authorization: str | None = Header(default=None),
) -> ConsumeResponse:
    user = await asyncio.to_thread(_require_user, authorization)
    try:
        data = await consume_points(
            user["id"],
            body.feature,
            focus_count=body.focus_count,
            is_redo=body.is_redo,
            idempotency_key=body.idempotency_key,
            meta=body.meta,
        )
    except InsufficientPointsError as exc:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "INSUFFICIENT_POINTS",
                "message": str(exc),
                "required": exc.required,
                "balance": exc.balance,
            },
        ) from exc
    return ConsumeResponse(**data)


@router.post("/refund")
async def points_refund(
    body: RefundRequest,
    authorization: str | None = Header(default=None),
) -> dict:
    user = await asyncio.to_thread(_require_user, authorization)
    tx = await asyncio.to_thread(points_db.get_transaction_by_id, body.transaction_id)
    if not tx or tx["user_id"] != user["id"]:
        raise ValueError("流水不存在。")
    return await refund_points(body.transaction_id)


@router.post("/checkin", response_model=CheckinResponse)
async def points_checkin(authorization: str | None = Header(default=None)) -> CheckinResponse:
    user = await asyncio.to_thread(_require_user, authorization)
    data = await checkin(user["id"])
    return CheckinResponse(
        transaction_id=data["transaction_id"],
        balance=data["balance"],
        streak=data["streak"],
        reward=data["reward"],
    )


@router.get("/ledger", response_model=LedgerResponse)
async def points_ledger(
    page: int = 1,
    page_size: int = 20,
    authorization: str | None = Header(default=None),
) -> LedgerResponse:
    user = await asyncio.to_thread(_require_user, authorization)
    data = await list_ledger(user["id"], page=max(1, page), page_size=min(50, page_size))
    return LedgerResponse(
        items=[LedgerItem(**item) for item in data["items"]],
        total=data["total"],
        page=data["page"],
        page_size=data["page_size"],
    )
