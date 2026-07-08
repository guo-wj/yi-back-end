from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator

from config import settings
from services import prompts
from services.deepseek_client import chat_completion
from datetime import datetime

from services.meihua_data import cast_by_number, cast_by_time, resolve_cast_time

router = APIRouter()

METHOD_LABELS = {"time": "时间起卦", "number": "数字起卦"}


class GuaOut(BaseModel):
    number: int = Field(..., description="卦序（周易本经序，1~64）")
    name: str = Field(..., description="卦名，如「水雷屯」")
    lower_trigram: str = Field(..., description="下卦（内卦）")
    upper_trigram: str = Field(..., description="上卦（外卦）")
    bits: list[int] = Field(..., description="六爻阴阳，自下而上，1=阳 0=阴")


class MeihuaRequest(BaseModel):
    method: str = Field(..., description="起卦方式：time=时间起卦，number=数字起卦")
    question: str = Field(..., min_length=1, description="所问事项")
    number: int | None = Field(default=None, ge=1, description="起卦数字，仅 method=number 时必填")
    client_time: str | None = Field(
        default=None,
        description="客户端本地公历时间（YYYY-MM-DDTHH:MM:SS），时间起卦时优先于服务端时钟",
    )

    @model_validator(mode="after")
    def validate_method(self) -> "MeihuaRequest":
        if self.method not in METHOD_LABELS:
            raise ValueError(f"起卦方式须为：{' / '.join(METHOD_LABELS)}。")
        if self.method == "number" and self.number is None:
            raise ValueError("数字起卦须提供 number 参数。")
        if self.method == "time" and self.number is not None:
            raise ValueError("时间起卦不需要 number 参数。")
        return self


class MeihuaCastOut(BaseModel):
    """起数成卦结果（不含解读），供前端即时演数动画使用。"""

    method: str = Field(..., description="起卦方式标识")
    method_label: str = Field(..., description="起卦方式名称")
    method_detail: str = Field(..., description="起卦推算过程说明")
    lower_trigram: str = Field(..., description="下卦（内卦）")
    upper_trigram: str = Field(..., description="上卦（外卦）")
    moving_line: int = Field(..., description="动爻爻位（1~6，自下而上）")
    ti_trigram: str = Field(..., description="体卦")
    yong_trigram: str = Field(..., description="用卦")
    ben_gua: GuaOut = Field(..., description="本卦")
    bian_gua: GuaOut = Field(..., description="变卦")
    hu_gua: GuaOut = Field(..., description="互卦")


class MeihuaResponse(MeihuaCastOut):
    interpretation: str = Field(..., description="解卦正文（模型生成）")


def _gua_label(gua: dict) -> str:
    return f"{gua['name']}（第{gua['number']}卦，{gua['upper_trigram']}上{gua['lower_trigram']}下）"


def _cast(body: "MeihuaRequest") -> dict:
    if body.method == "time":
        return cast_by_time(resolve_cast_time(body.client_time))
    return cast_by_number(body.number)  # type: ignore[arg-type]


def _cast_out(cast: dict) -> MeihuaCastOut:
    return MeihuaCastOut(
        method=cast["method"],
        method_label=METHOD_LABELS[cast["method"]],
        method_detail=cast["method_detail"],
        lower_trigram=cast["lower_trigram"],
        upper_trigram=cast["upper_trigram"],
        moving_line=cast["moving_line"],
        ti_trigram=cast["ti_trigram"],
        yong_trigram=cast["yong_trigram"],
        ben_gua=GuaOut(**cast["ben_gua"]),
        bian_gua=GuaOut(**cast["bian_gua"]),
        hu_gua=GuaOut(**cast["hu_gua"]),
    )


@router.post("/cast", response_model=MeihuaCastOut)
async def cast_meihua(body: MeihuaRequest) -> MeihuaCastOut:
    """梅花易数起卦：仅起数成卦（本/变/互卦、体用、动爻），不含解读，秒级返回。"""
    return _cast_out(_cast(body))


@router.post("/divine", response_model=MeihuaResponse)
async def divine_meihua(body: MeihuaRequest) -> MeihuaResponse:
    """梅花易数 AI 解卦：需登录；积分由前端先 consume 再调用。"""
    cast = _cast(body)

    user = prompts.meihua_user(
        question=body.question,
        method_label=METHOD_LABELS[body.method],
        ben_gua=_gua_label(cast["ben_gua"]),
        bian_gua=_gua_label(cast["bian_gua"]),
        hu_gua=_gua_label(cast["hu_gua"]),
        ti_trigram=cast["ti_trigram"],
        yong_trigram=cast["yong_trigram"],
        moving_line=cast["moving_line"],
    )
    interpretation = await chat_completion(
        prompts.meihua_system(),
        user,
        temperature=0.35,
        max_tokens=settings.gua_interpret_max_tokens,
    )

    return MeihuaResponse(
        **_cast_out(cast).model_dump(),
        interpretation=interpretation,
    )
