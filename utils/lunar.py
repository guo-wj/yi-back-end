"""农历转换与干支等排盘基础（公历↔农历、年柱）。"""

from dataclasses import dataclass
from datetime import date, datetime

from lunardate import LunarDate

TIAN_GAN = "甲乙丙丁戊己庚辛壬癸"
DI_ZHI = "子丑寅卯辰巳午未申酉戌亥"

# 时辰地支 → 用于排时柱的代表整点（子初 0 点；与 _hour_branch_index 一致）
SHI_CHEN_HOUR: dict[str, int] = {
    "子": 0,
    "丑": 1,
    "寅": 3,
    "卯": 5,
    "辰": 7,
    "巳": 9,
    "午": 11,
    "未": 13,
    "申": 15,
    "酉": 17,
    "戌": 19,
    "亥": 21,
}


@dataclass(frozen=True)
class LunarInfo:
    lunar_year: int
    lunar_month: int
    lunar_day: int
    is_leap_month: bool

    def label(self) -> str:
        leap = "闰" if self.is_leap_month else ""
        return f"{leap}{self.lunar_month}月{self.lunar_day}日"


def solar_to_lunar(d: date) -> LunarInfo:
    ld = LunarDate.fromSolarDate(d.year, d.month, d.day)
    return LunarInfo(
        lunar_year=ld.year,
        lunar_month=ld.month,
        lunar_day=ld.day,
        is_leap_month=bool(ld.isLeapMonth),
    )


def lunar_to_solar(year: int, month: int, day: int, *, is_leap_month: bool = False) -> date:
    """阴历日期转公历。"""
    ld = LunarDate(year, month, day, isLeapMonth=is_leap_month)
    return ld.toSolarDate()


def shi_chen_to_hour(branch: str) -> int:
    """时辰地支 → 排盘用代表整点。"""
    if branch not in SHI_CHEN_HOUR:
        raise ValueError(f"无效时辰：{branch}")
    return SHI_CHEN_HOUR[branch]


def year_ganzhi(year: int) -> str:
    """以立春前仍算上一年为常见流派简化：此处按公历年近似年柱（与严格节气派可能有边界差异）。"""
    g = (year - 4) % 10
    z = (year - 4) % 12
    return TIAN_GAN[g] + DI_ZHI[z]


def _pillar_from_offset(gan0: int, zhi0: int, offset: int) -> str:
    return TIAN_GAN[(gan0 + offset) % 10] + DI_ZHI[(zhi0 + offset) % 12]


def day_pillar_solar(d: date) -> str:
    """日柱：以公历 1900-01-01 为甲戌日锚点做连续推算（与部分万年历边界日可能差一日）。"""
    anchor = date(1900, 1, 1)
    # 1900-01-01 甲戌：甲=0, 戌=10
    gan0, zhi0 = 0, 10
    delta = (d - anchor).days
    return _pillar_from_offset(gan0, zhi0, delta)


def _hour_branch_index(hour: int) -> int:
    """子时含 23 点与 0 点；每两个整点为一个时辰。"""
    if hour >= 23 or hour < 1:
        return 0
    return ((hour + 1) // 2) % 12


def hour_pillar(d: date, hour: int) -> str:
    """时柱：由日干五鼠遁推子时天干，再顺推时辰天干。"""
    day_gan_idx = TIAN_GAN.index(day_pillar_solar(d)[0])
    zi_gan = (day_gan_idx % 5) * 2
    zhi_idx = _hour_branch_index(hour)
    gan_idx = (zi_gan + zhi_idx) % 10
    return TIAN_GAN[gan_idx] + DI_ZHI[zhi_idx]


def month_pillar_solar(d: date) -> str:
    """月柱：以农历月配合五虎遁（与节气换月派别仍有差异，仅供模型参考）。"""
    ld = LunarDate.fromSolarDate(d.year, d.month, d.day)
    lunar_m = ld.month
    zhi_idx = (lunar_m + 1) % 12
    year_g = (d.year - 4) % 10
    first_month_gan = ((year_g % 5) * 2 + 2) % 10
    gan_idx = (first_month_gan + lunar_m - 1) % 10
    return TIAN_GAN[gan_idx] + DI_ZHI[zhi_idx]


def four_pillars_hint(dt: datetime) -> str:
    """四柱提示字符串（简化算法，强调供模型复核）。"""
    d = dt.date()
    yg = year_ganzhi(d.year)
    mg = month_pillar_solar(d)
    dg = day_pillar_solar(d)
    hg = hour_pillar(d, dt.hour)
    return f"{yg}年 {mg}月 {dg}日 {hg}时"


def format_lunar_display(d: date) -> str:
    info = solar_to_lunar(d)
    gz = year_ganzhi(d.year)
    return f"{d.isoformat()} → 农历{info.lunar_year}年{info.label()}（{gz}年）"
