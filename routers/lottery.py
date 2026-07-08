from datetime import date

import asyncio

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from services.auth_service import user_from_token
from services.lottery_service import draw_only, interpret_only
from services.points_service import check_and_record_draw

router = APIRouter()


def _require_user(authorization: str | None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ValueError("未登录，请先登录。")
    token = authorization[7:].strip()
    if not token:
        raise ValueError("未登录，请先登录。")
    return user_from_token(token)


class SlipOut(BaseModel):
    id: int = Field(..., description="签号")
    tier: str = Field(..., description="签等等第（文化语境，非断言）")
    title: str = Field(..., description="签题")
    poem: str = Field(..., description="签诗（四句）")
    gist: str = Field(..., description="签文简解（传统解曰，免费展示）")


class LotteryDrawRequest(BaseModel):
    name: str | None = Field(default=None, description="称呼或昵称")
    focus: str | None = Field(default=None, description="今日关注，如事业、人际")
    question: str | None = Field(default=None, description="具体所问，可选")
    solar_date: date | None = Field(default=None, description="占问日，默认当天")


class LotteryDrawResponse(BaseModel):
    solar_date: str
    lunar_summary: str
    slip: SlipOut


class LotteryInterpretRequest(BaseModel):
    slip_id: int = Field(..., description="已摇出的签号")
    name: str | None = Field(default=None, description="称呼或昵称")
    focus: str | None = Field(default=None, description="今日关注")
    question: str | None = Field(default=None, description="具体所问，可选")
    solar_date: date | None = Field(default=None, description="占问日，默认当天")


class LotteryInterpretResponse(BaseModel):
    solar_date: str
    lunar_summary: str
    slip: SlipOut
    interpretation: str = Field(..., description="解签正文（模型生成，紧扣本签）")


@router.post("/draw", response_model=LotteryDrawResponse)
async def draw_lottery(
    body: LotteryDrawRequest,
    authorization: str | None = Header(default=None),
) -> LotteryDrawResponse:
    """摇签：仅出签文，不调 LLM。"""
    user = await asyncio.to_thread(_require_user, authorization)
    try:
        await check_and_record_draw(user["id"])
    except ValueError as exc:
        if "上限" in str(exc):
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        raise

    slip, ctx = await draw_only(solar_date=body.solar_date)
    return LotteryDrawResponse(
        solar_date=ctx.solar_date_str,
        lunar_summary=ctx.lunar_summary,
        slip=SlipOut(
            id=slip["id"],
            tier=slip["tier"],
            title=slip["title"],
            poem=slip["poem"],
            gist=slip["gist"],
        ),
    )


@router.post("/interpret", response_model=LotteryInterpretResponse)
async def interpret_lottery(
    body: LotteryInterpretRequest,
    authorization: str | None = Header(default=None),
) -> LotteryInterpretResponse:
    """AI 解签：需登录；积分由前端先 consume 再调用。"""
    await asyncio.to_thread(_require_user, authorization)
    slip, ctx, interpretation = await interpret_only(
        slip_id=body.slip_id,
        solar_date=body.solar_date,
        name=body.name,
        focus=body.focus,
        question=body.question,
    )
    return LotteryInterpretResponse(
        solar_date=ctx.solar_date_str,
        lunar_summary=ctx.lunar_summary,
        slip=SlipOut(
            id=slip["id"],
            tier=slip["tier"],
            title=slip["title"],
            poem=slip["poem"],
            gist=slip["gist"],
        ),
        interpretation=interpretation,
    )
