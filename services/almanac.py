"""老黄历（黄历/通胜）数据：基于 lunar_python 离线计算。

含公历/农历日期、干支、节日、节气、每日宜忌，以及冲煞、值神、二十八宿、
彭祖百忌、喜财福神方位、胎神等传统黄历条目。纯本地计算，无需第三方接口与密钥。
"""

from __future__ import annotations

from datetime import date as _date

from lunar_python import Solar


def _lucky_hours(lunar) -> list[str]:
    """当日吉时的时辰地支（黄道时，去重保序）。"""
    result: list[str] = []
    for t in lunar.getTimes():
        zhi = t.getZhi()
        if t.getTianShenLuck() == "吉" and zhi not in result:
            result.append(zhi)
    return result


def build_almanac(d: _date) -> dict:
    solar = Solar.fromYmd(d.year, d.month, d.day)
    lunar = solar.getLunar()
    next_jq = lunar.getNextJieQi()
    prev_jq = lunar.getPrevJieQi()
    current_jq = lunar.getJieQi() or None

    festivals = list(solar.getFestivals()) + list(lunar.getFestivals())

    return {
        "solar": {
            "date": d.isoformat(),
            "year": d.year,
            "month": d.month,
            "day": d.day,
            "weekday": f"星期{solar.getWeekInChinese()}",
            "constellation": solar.getXingZuo(),
        },
        "lunar": {
            "date": f"{lunar.getYearInChinese()}年{lunar.getMonthInChinese()}月{lunar.getDayInChinese()}",
            "month_day": f"{lunar.getMonthInChinese()}月{lunar.getDayInChinese()}",
            "year_ganzhi": lunar.getYearInGanZhi(),
            "month_ganzhi": lunar.getMonthInGanZhi(),
            "day_ganzhi": lunar.getDayInGanZhi(),
            "shengxiao": lunar.getYearShengXiao(),
            "nayin": lunar.getDayNaYin(),
        },
        "festivals": festivals,
        "jieqi": {
            "current": current_jq,
            "term": prev_jq.getName(),
            "next_name": next_jq.getName(),
            "next_date": next_jq.getSolar().toYmd(),
        },
        "yi": lunar.getDayYi(),
        "ji": lunar.getDayJi(),
        "details": {
            "chong": lunar.getDayChongDesc(),
            "sha": lunar.getDaySha(),
            "zhishen": lunar.getDayTianShen(),
            "zhishen_luck": lunar.getDayTianShenLuck(),
            "jian_chu": lunar.getZhiXing(),
            "xiu": f"{lunar.getXiu()}{lunar.getZheng()}{lunar.getAnimal()}",
            "xiu_luck": lunar.getXiuLuck(),
            "ji_shen_yi_qu": lunar.getDayJiShen(),
            "xiong_sha_yi_ji": lunar.getDayXiongSha(),
            "peng_zu": [lunar.getPengZuGan(), lunar.getPengZuZhi()],
            "xi_shen": lunar.getDayPositionXiDesc(),
            "cai_shen": lunar.getDayPositionCaiDesc(),
            "fu_shen": lunar.getDayPositionFuDesc(),
            "yang_gui": lunar.getDayPositionYangGuiDesc(),
            "yin_gui": lunar.getDayPositionYinGuiDesc(),
            "ji_shi": _lucky_hours(lunar),
            "tai_shen": lunar.getDayPositionTai(),
            "nine_star": lunar.getDayNineStar().toString(),
        },
    }
