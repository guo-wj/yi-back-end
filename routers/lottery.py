from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.lottery_service import draw_and_interpret

router = APIRouter()


class SlipOut(BaseModel):
    id: int = Field(..., description="签号")
    tier: str = Field(..., description="签等等第（文化语境，非断言）")
    title: str = Field(..., description="签题")
    poem: str = Field(..., description="签诗（四句）")


class LotteryDrawRequest(BaseModel):
    name: str | None = Field(default=None, description="称呼或昵称")
    focus: str | None = Field(default=None, description="今日关注，如事业、人际")
    question: str | None = Field(default=None, description="具体所问，可选")
    solar_date: date | None = Field(default=None, description="占问日，默认当天")


class LotteryDrawResponse(BaseModel):
    solar_date: str
    lunar_summary: str
    slip: SlipOut
    interpretation: str = Field(..., description="解签正文（模型生成，紧扣本签）")


@router.post("/draw", response_model=LotteryDrawResponse)
async def draw_lottery(body: LotteryDrawRequest) -> LotteryDrawResponse:
    slip, ctx, interpretation = await draw_and_interpret(
        solar_date=body.solar_date,
        name=body.name,
        focus=body.focus,
        question=body.question,
    )
    return LotteryDrawResponse(
        solar_date=ctx.solar_date_str,
        lunar_summary=ctx.lunar_summary,
        slip=SlipOut(
            id=slip["id"],
            tier=slip["tier"],
            title=slip["title"],
            poem=slip["poem"],
        ),
        interpretation=interpretation,
    )
