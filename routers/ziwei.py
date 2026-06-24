from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services import prompts
from services.deepseek_client import chat_completion
from utils.lunar import format_lunar_display

router = APIRouter()


class ZiweiRequest(BaseModel):
    birth_solar: datetime = Field(..., description="出生时间（公历，本地或注明时区）")
    gender: str = Field(..., description="性别，如 男 / 女")
    extra: str | None = Field(default=None, description="补充：出生地、夏令时等")


class ZiweiResponse(BaseModel):
    content: str
    lunar_summary: str


@router.post("/chart", response_model=ZiweiResponse)
async def ziwei_chart(body: ZiweiRequest) -> ZiweiResponse:
    d = body.birth_solar.date()
    lunar_summary = format_lunar_display(d)
    user = prompts.ziwei_user(
        birth_solar=body.birth_solar.isoformat(timespec="minutes"),
        gender=body.gender,
        extra=body.extra,
    )
    content = await chat_completion(prompts.ziwei_system(), user)
    return ZiweiResponse(content=content, lunar_summary=lunar_summary)
