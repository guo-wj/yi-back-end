from datetime import date

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from services.almanac import build_almanac

router = APIRouter()


class SolarInfo(BaseModel):
    date: str = Field(..., description="公历日期 YYYY-MM-DD")
    year: int
    month: int
    day: int
    weekday: str = Field(..., description="星期，如 星期二")
    constellation: str = Field(..., description="星座")


class LunarInfo(BaseModel):
    date: str = Field(..., description="农历完整日期，如 二〇二六年四月廿四")
    month_day: str = Field(..., description="农历月日，如 四月廿四")
    year_ganzhi: str = Field(..., description="年干支")
    month_ganzhi: str = Field(..., description="月干支")
    day_ganzhi: str = Field(..., description="日干支")
    shengxiao: str = Field(..., description="生肖")
    nayin: str = Field(..., description="日纳音")


class JieQiInfo(BaseModel):
    current: str | None = Field(None, description="当日节气，无则为空")
    term: str = Field(..., description="当前所处节气（上一个节气），用于节气印章")
    next_name: str = Field(..., description="下一个节气名称")
    next_date: str = Field(..., description="下一个节气公历日期")


class AlmanacDetails(BaseModel):
    chong: str = Field(..., description="当日冲（生肖）")
    sha: str = Field(..., description="煞方")
    zhishen: str = Field(..., description="值日天神")
    zhishen_luck: str = Field(..., description="值神吉凶")
    jian_chu: str = Field(..., description="建除十二神")
    xiu: str = Field(..., description="二十八宿（宿+七政+动物）")
    xiu_luck: str = Field(..., description="星宿吉凶")
    ji_shen_yi_qu: list[str] = Field(..., description="吉神宜趋")
    xiong_sha_yi_ji: list[str] = Field(..., description="凶煞宜忌")
    peng_zu: list[str] = Field(..., description="彭祖百忌（干、支两句）")
    xi_shen: str = Field(..., description="喜神方位")
    cai_shen: str = Field(..., description="财神方位")
    fu_shen: str = Field(..., description="福神方位")
    yang_gui: str = Field(..., description="阳贵神方位")
    yin_gui: str = Field(..., description="阴贵神方位")
    ji_shi: list[str] = Field(..., description="吉时（时辰地支）")
    tai_shen: str = Field(..., description="胎神占方")
    nine_star: str = Field(..., description="当日九星")


class AlmanacResponse(BaseModel):
    solar: SolarInfo
    lunar: LunarInfo
    festivals: list[str] = Field(..., description="公历与农历节日合并")
    jieqi: JieQiInfo
    yi: list[str] = Field(..., description="今日宜")
    ji: list[str] = Field(..., description="今日忌")
    details: AlmanacDetails


@router.get("/day", response_model=AlmanacResponse)
async def almanac_day(
    query_date: date | None = Query(
        default=None, alias="date", description="查询日期 YYYY-MM-DD，默认当天"
    ),
) -> AlmanacResponse:
    d = query_date or date.today()
    return AlmanacResponse(**build_almanac(d))
