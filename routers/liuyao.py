from fastapi import APIRouter
from pydantic import BaseModel, Field

from config import settings
from services import prompts
from services.deepseek_client import chat_completion
from services.liuyao_data import cast_from_yao

router = APIRouter()


class GuaOut(BaseModel):
    number: int = Field(..., description="卦序（周易本经序，1~64）")
    name: str = Field(..., description="卦名，如「水雷屯」")
    lower_trigram: str = Field(..., description="下卦（内卦）")
    upper_trigram: str = Field(..., description="上卦（外卦）")
    bits: list[int] = Field(..., description="六爻阴阳，自下而上，1=阳 0=阴")


class LineOut(BaseModel):
    position: int = Field(..., description="爻位：1=初爻（最下），6=上爻")
    yao_value: int
    name: str
    is_yang: bool
    is_moving: bool
    symbol: str


class CastRequest(BaseModel):
    question: str = Field(..., min_length=1, description="所问事项")
    yao_values: list[int] = Field(
        ...,
        min_length=6,
        max_length=6,
        description="六次摇钱结果，自下而上，每爻 6/7/8/9",
    )


class CastResponse(BaseModel):
    """起卦结果（不含 AI 解读）。"""

    lines: list[LineOut] = Field(..., description="六爻明细，自下而上")
    ben_gua: GuaOut = Field(..., description="本卦")
    bian_gua: GuaOut | None = Field(default=None, description="变卦（无动爻则为 null）")
    moving_positions: list[int] = Field(..., description="动爻爻位（自下而上）")


class InterpretResponse(BaseModel):
    interpretation: str = Field(..., description="解卦正文（模型生成）")


def _gua_label(gua: dict) -> str:
    return f"{gua['name']}（第{gua['number']}卦，{gua['upper_trigram']}上{gua['lower_trigram']}下）"


def _cast_payload(yao_values: list[int]) -> dict:
    return cast_from_yao(yao_values)


def _build_prompt_context(body: CastRequest, cast: dict) -> tuple[str, str, str, str]:
    ben_label = _gua_label(cast["ben_gua"])
    bian_label = _gua_label(cast["bian_gua"]) if cast["bian_gua"] else None
    moving = cast["moving_positions"]
    moving_desc = (
        "、".join(f"第{p}爻" for p in moving) if moving else "无动爻（六爻皆静）"
    )
    lines_desc = "；".join(
        f"第{ln['position']}爻{ln['name']}{'动' if ln['is_moving'] else ''}"
        for ln in cast["lines"]
    )
    return ben_label, bian_label or "", moving_desc, lines_desc


@router.post("/cast", response_model=CastResponse)
async def cast_liuyao(body: CastRequest) -> CastResponse:
    """接收六次摇卦结果，推算本卦、变卦与动爻（不含 LLM）。"""
    cast = _cast_payload(body.yao_values)
    return CastResponse(
        lines=[LineOut(**ln) for ln in cast["lines"]],
        ben_gua=GuaOut(**cast["ben_gua"]),
        bian_gua=GuaOut(**cast["bian_gua"]) if cast["bian_gua"] else None,
        moving_positions=cast["moving_positions"],
    )


@router.post("/interpret", response_model=InterpretResponse)
async def interpret_liuyao(body: CastRequest) -> InterpretResponse:
    """AI 解卦：需登录；积分由前端先 consume 再调用。"""
    cast = _cast_payload(body.yao_values)
    ben_label, bian_label, moving_desc, lines_desc = _build_prompt_context(body, cast)

    user = prompts.liuyao_cast_user(
        question=body.question,
        ben_gua=ben_label,
        bian_gua=bian_label or None,
        moving_desc=moving_desc,
        lines_desc=lines_desc,
    )
    interpretation = await chat_completion(
        prompts.liuyao_system(),
        user,
        temperature=0.35,
        max_tokens=settings.gua_interpret_max_tokens,
    )
    return InterpretResponse(interpretation=interpretation)
