from datetime import date, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from services import prompts
from services.deepseek_client import chat_completion
from utils.lunar import (
    format_lunar_display,
    four_pillars_hint,
    lunar_to_solar,
    shi_chen_to_hour,
)

router = APIRouter()

ShiChen = str  # 子丑寅卯辰巳午未申酉戌亥
FocusArea = str  # 感情、事业、学业、财运


class BaziRequest(BaseModel):
    gender: str = Field(..., description="性别：男 / 女")
    birth_place: str = Field(..., min_length=1, description="出生地，如「北京市」")
    calendar: str = Field(..., description="出生历法：solar=阳历，lunar=阴历")
    birth_year: int = Field(..., ge=1900, le=2099, description="出生年")
    birth_month: int = Field(..., ge=1, le=12, description="出生月")
    birth_day: int = Field(..., ge=1, le=31, description="出生日")
    is_leap_month: bool = Field(default=False, description="是否闰月，仅阴历有效")
    birth_hour: str = Field(..., description="出生时辰地支：子丑寅卯辰巳午未申酉戌亥")
    sexual_orientation: str = Field(
        ...,
        description="性取向：异性恋 / 同性恋 / 双性恋 / 其他 / 不愿透露",
    )
    focus: list[str] = Field(
        ...,
        min_length=1,
        description="关注事项，可多选：感情、事业、学业、财运",
    )

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: str) -> str:
        if v not in ("男", "女"):
            raise ValueError("性别须为「男」或「女」。")
        return v

    @field_validator("calendar")
    @classmethod
    def validate_calendar(cls, v: str) -> str:
        if v not in ("solar", "lunar"):
            raise ValueError("calendar 须为 solar（阳历）或 lunar（阴历）。")
        return v

    @field_validator("birth_hour")
    @classmethod
    def validate_birth_hour(cls, v: str) -> str:
        if v not in "子丑寅卯辰巳午未申酉戌亥":
            raise ValueError("出生时辰须为十二地支之一：子丑寅卯辰巳午未申酉戌亥。")
        return v

    @field_validator("sexual_orientation")
    @classmethod
    def validate_orientation(cls, v: str) -> str:
        allowed = ("异性恋", "同性恋", "双性恋", "其他", "不愿透露")
        if v not in allowed:
            raise ValueError(f"性取向须为：{' / '.join(allowed)}。")
        return v

    @field_validator("focus")
    @classmethod
    def validate_focus(cls, v: list[str]) -> list[str]:
        allowed = ("感情", "事业", "学业", "财运")
        if not v:
            raise ValueError("请至少选择一项关注事项。")
        invalid = [f for f in v if f not in allowed]
        if invalid:
            raise ValueError(f"关注事项仅支持：{'、'.join(allowed)}。")
        # 去重保序
        seen: set[str] = set()
        deduped: list[str] = []
        for item in v:
            if item not in seen:
                seen.add(item)
                deduped.append(item)
        return deduped

    @model_validator(mode="after")
    def validate_leap_month(self) -> "BaziRequest":
        if self.is_leap_month and self.calendar != "lunar":
            raise ValueError("闰月仅适用于阴历出生日期。")
        return self


class BaziResponse(BaseModel):
    birth_solar: str = Field(..., description="归一化后的公历出生日期")
    birth_hour_label: str = Field(..., description="出生时辰，如「午时」")
    lunar_summary: str = Field(..., description="农历与干支摘要")
    pillars_hint: str = Field(..., description="四柱参考（程序推算）")
    focus: list[str] = Field(..., description="本次解读的关注事项")
    content: str = Field(..., description="命理解读正文")


def _resolve_birth_date(body: BaziRequest) -> date:
    if body.calendar == "solar":
        try:
            return date(body.birth_year, body.birth_month, body.birth_day)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="阳历出生日期无效。") from e
    try:
        return lunar_to_solar(
            body.birth_year,
            body.birth_month,
            body.birth_day,
            is_leap_month=body.is_leap_month,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail="阴历出生日期无效或闰月设置有误。") from e


def _birth_input_label(body: BaziRequest) -> str:
    cal = "阳历" if body.calendar == "solar" else "阴历"
    leap = "闰" if body.is_leap_month else ""
    return f"{cal}{body.birth_year}年{leap}{body.birth_month}月{body.birth_day}日"


@router.post("/analyze", response_model=BaziResponse)
async def bazi_analyze(body: BaziRequest) -> BaziResponse:
    birth_date = _resolve_birth_date(body)
    hour = shi_chen_to_hour(body.birth_hour)
    birth_dt = datetime(birth_date.year, birth_date.month, birth_date.day, hour)

    lunar_summary = format_lunar_display(birth_date)
    pillars = four_pillars_hint(birth_dt)
    hour_label = f"{body.birth_hour}时"

    user = prompts.bazi_user(
        gender=body.gender,
        birth_place=body.birth_place,
        birth_input=_birth_input_label(body),
        birth_solar=birth_dt.isoformat(timespec="minutes"),
        birth_hour_label=hour_label,
        sexual_orientation=body.sexual_orientation,
        pillars_hint=pillars,
        focus=body.focus,
    )
    content = await chat_completion(prompts.bazi_system(), user)

    return BaziResponse(
        birth_solar=birth_date.isoformat(),
        birth_hour_label=hour_label,
        lunar_summary=lunar_summary,
        pillars_hint=pillars,
        focus=body.focus,
        content=content,
    )
