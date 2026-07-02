"""会员档位 API。"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from services.points_service import MEMBER_TIERS, RECHARGE_PACKAGES

router = APIRouter()


class MemberPlan(BaseModel):
    id: str
    label: str
    price_cents: int
    monthly_points: int
    discount: float
    qian_free_daily: int
    liuyao_free_daily: int
    meihua_free_daily: int
    bazi_free_daily: int
    palm_free_daily: int
    face_free_daily: int


class RechargePlan(BaseModel):
    id: str
    label: str
    price_cents: int
    points: int
    bonus_pct: int


class PlansResponse(BaseModel):
    members: list[MemberPlan]
    recharge: list[RechargePlan]


@router.get("/plans", response_model=PlansResponse)
async def member_plans() -> PlansResponse:
    members = [
        MemberPlan(
            id=tier_id,
            label=plan["label"],
            price_cents=plan["price_cents"],
            monthly_points=plan["monthly_points"],
            discount=plan["discount"],
            qian_free_daily=plan["qian_free_daily"],
            liuyao_free_daily=plan["liuyao_free_daily"],
            meihua_free_daily=plan["meihua_free_daily"],
            bazi_free_daily=plan["bazi_free_daily"],
            palm_free_daily=plan["palm_free_daily"],
            face_free_daily=plan["face_free_daily"],
        )
        for tier_id, plan in MEMBER_TIERS.items()
        if tier_id != "none"
    ]
    recharge = [
        RechargePlan(
            id=p["id"],
            label=p["label"],
            price_cents=p["price_cents"],
            points=p["points"],
            bonus_pct=p["bonus_pct"],
        )
        for p in RECHARGE_PACKAGES
    ]
    return PlansResponse(members=members, recharge=recharge)
