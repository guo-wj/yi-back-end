"""充值与会员订阅（MVP：创建订单 + 模拟确认支付）。"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from services.auth_service import user_from_token
from services.points_service import confirm_payment, create_member_order, create_recharge_order

router = APIRouter()


def _require_user(authorization: str | None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ValueError("未登录，请先登录。")
    token = authorization[7:].strip()
    if not token:
        raise ValueError("未登录，请先登录。")
    return user_from_token(token)


class RechargeRequest(BaseModel):
    product_id: str = Field(..., description="充值包 id")


class MemberSubscribeRequest(BaseModel):
    tier: str = Field(..., description="会员档位：yiyou/yishi/yizun")


class OrderResponse(BaseModel):
    order_id: int
    status: str


class ConfirmPaymentRequest(BaseModel):
    order_id: int


@router.post("/recharge", response_model=OrderResponse)
async def payment_recharge(
    body: RechargeRequest,
    authorization: str | None = Header(default=None),
) -> OrderResponse:
    user = await asyncio.to_thread(_require_user, authorization)
    data = await create_recharge_order(user["id"], body.product_id)
    return OrderResponse(order_id=data["order_id"], status=data["status"])


@router.post("/member", response_model=OrderResponse)
async def payment_member(
    body: MemberSubscribeRequest,
    authorization: str | None = Header(default=None),
) -> OrderResponse:
    user = await asyncio.to_thread(_require_user, authorization)
    data = await create_member_order(user["id"], body.tier)
    return OrderResponse(order_id=data["order_id"], status=data["status"])


@router.post("/confirm")
async def payment_confirm(
    body: ConfirmPaymentRequest,
    authorization: str | None = Header(default=None),
) -> dict:
    """开发/MVP：模拟支付成功。生产环境由微信/支付宝回调替代。"""
    user = await asyncio.to_thread(_require_user, authorization)
    return await confirm_payment(body.order_id, user["id"])
