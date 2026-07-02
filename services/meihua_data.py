"""梅花易数起卦：时间起卦、数字起卦，推算本卦、互卦、变卦与体用。"""

from datetime import datetime

from lunardate import LunarDate

from services.liuyao_data import TRIGRAM_BITS, _build_gua
from utils.lunar import DI_ZHI, _hour_branch_index

# 先天八卦数：1乾 2兑 3离 4震 5巽 6坎 7艮 8坤
_BA_GUA = ["", "乾", "兑", "离", "震", "巽", "坎", "艮", "坤"]


def _mod8(n: int) -> int:
    r = n % 8
    return 8 if r == 0 else r


def _mod6(n: int) -> int:
    r = n % 6
    return 6 if r == 0 else r


def _trigram_from_index(idx: int) -> str:
    return _BA_GUA[idx]


def _bits_from_trigrams(lower: str, upper: str) -> tuple[int, ...]:
    return TRIGRAM_BITS[lower] + TRIGRAM_BITS[upper]


def _year_zhi_number(lunar_year: int) -> int:
    """年支序数：子1 … 亥12。"""
    return (lunar_year - 4) % 12 + 1


def _hour_zhi_number(hour: int) -> int:
    """时支序数：子1 … 亥12。"""
    return _hour_branch_index(hour) + 1


def _build_mutual(bits: tuple[int, ...]) -> dict:
    """互卦：二三四爻为下互，三四五爻为上互。"""
    lower = _trigram_from_bits(bits[1:4])
    upper = _trigram_from_bits(bits[2:5])
    mutual_bits = TRIGRAM_BITS[lower] + TRIGRAM_BITS[upper]
    return _build_gua(mutual_bits)


def _trigram_from_bits(bits: tuple[int, ...]) -> str:
    for name, tri_bits in TRIGRAM_BITS.items():
        if tri_bits == bits:
            return name
    raise ValueError(f"无效三爻：{bits}")


def _ti_yong(lower: str, upper: str, moving_line: int) -> tuple[str, str]:
    """体用：动爻在下卦则上为体、下为用；动爻在上卦则下为体、上为用。"""
    if moving_line <= 3:
        return upper, lower
    return lower, upper


def cast_from_indices(
    *,
    lower_idx: int,
    upper_idx: int,
    moving_line: int,
    method: str,
    method_detail: str,
) -> dict:
    lower = _trigram_from_index(lower_idx)
    upper = _trigram_from_index(upper_idx)
    ben_bits = _bits_from_trigrams(lower, upper)
    ben = _build_gua(ben_bits)

    bian_bits = tuple(
        (1 - b) if (i + 1) == moving_line else b for i, b in enumerate(ben_bits)
    )
    bian = _build_gua(bian_bits)
    hu = _build_mutual(ben_bits)
    ti, yong = _ti_yong(lower, upper, moving_line)

    return {
        "method": method,
        "method_detail": method_detail,
        "lower_trigram": lower,
        "upper_trigram": upper,
        "moving_line": moving_line,
        "ti_trigram": ti,
        "yong_trigram": yong,
        "ben_gua": ben,
        "bian_gua": bian,
        "hu_gua": hu,
    }


def resolve_cast_time(client_time: str | None) -> datetime:
    """解析前端传来的本地公历时间；无效时回退服务端当前时间。"""
    if client_time:
        raw = client_time.strip()
        for candidate in (raw, raw[:19]):
            try:
                return datetime.fromisoformat(candidate)
            except ValueError:
                continue
    return datetime.now()


def cast_by_time(dt: datetime | None = None) -> dict:
    """时间起卦：农历年月日 + 时辰地支序数（邵雍法）；动爻另加分、秒以应占时之刻。"""
    dt = dt or datetime.now()
    ld = LunarDate.fromSolarDate(dt.year, dt.month, dt.day)
    year_n = _year_zhi_number(ld.year)
    month_n = ld.month
    day_n = ld.day
    hour_n = _hour_zhi_number(dt.hour)
    minute_n = dt.minute + 1
    second_n = dt.second + 1

    upper_sum = year_n + month_n + day_n
    lower_sum = upper_sum + hour_n
    upper_idx = _mod8(upper_sum)
    lower_idx = _mod8(lower_sum)
    moving_sum = lower_sum + minute_n + second_n
    moving = _mod6(moving_sum)

    hour_branch = DI_ZHI[_hour_branch_index(dt.hour)]
    leap = "闰" if ld.isLeapMonth else ""
    detail = (
        f"公历 {dt.strftime('%Y-%m-%d %H:%M:%S')}，"
        f"农历 {ld.year}年{leap}{ld.month}月{ld.day}日 {hour_branch}时；"
        f"上卦数=({year_n}+{month_n}+{day_n}) mod 8 → {upper_idx}（{_trigram_from_index(upper_idx)}），"
        f"下卦数=({year_n}+{month_n}+{day_n}+{hour_n}) mod 8 → {lower_idx}（{_trigram_from_index(lower_idx)}），"
        f"动爻=({year_n}+{month_n}+{day_n}+{hour_n}+{minute_n}+{second_n}) mod 6 → 第{moving}爻"
    )
    return cast_from_indices(
        lower_idx=lower_idx,
        upper_idx=upper_idx,
        moving_line=moving,
        method="time",
        method_detail=detail,
    )


def cast_by_number(number: int) -> dict:
    """数字起卦：上卦=数 mod 8，下卦=(数÷8) mod 8，动爻=数 mod 6。"""
    if number < 1:
        raise ValueError("起卦数字须为正整数。")

    upper_idx = _mod8(number)
    lower_idx = _mod8(number // 8)
    moving = _mod6(number)
    detail = (
        f"起卦数 {number}；"
        f"上卦={number} mod 8 → {upper_idx}（{_trigram_from_index(upper_idx)}），"
        f"下卦=({number}÷8) mod 8 → {lower_idx}（{_trigram_from_index(lower_idx)}），"
        f"动爻={number} mod 6 → 第{moving}爻"
    )
    return cast_from_indices(
        lower_idx=lower_idx,
        upper_idx=upper_idx,
        moving_line=moving,
        method="number",
        method_detail=detail,
    )
