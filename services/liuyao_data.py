"""六爻起卦数据与算法：六爻成卦、本卦变卦推算。

铜钱记数沿用纳甲筮法约定：背面记 2（阴），字面记 3（阳），三枚之和：
    6 老阴（少数派，动爻 → 阳）
    7 少阳（静）
    8 少阴（静）
    9 老阳（动爻 → 阴）
此约定与 routers.liuyao 中 YAO_NAMES 一致。
"""

# 单爻取值 → 名称、阴阳、是否动爻
YAO_INFO: dict[int, dict] = {
    6: {"name": "老阴", "is_yang": False, "is_moving": True, "symbol": "▅▅ ▅▅ ✕"},
    7: {"name": "少阳", "is_yang": True, "is_moving": False, "symbol": "▅▅▅▅▅"},
    8: {"name": "少阴", "is_yang": False, "is_moving": False, "symbol": "▅▅ ▅▅"},
    9: {"name": "老阳", "is_yang": True, "is_moving": True, "symbol": "▅▅▅▅▅ ○"},
}

# 八卦，三爻自下而上的阴阳位（1=阳，0=阴）
TRIGRAM_BITS: dict[str, tuple[int, int, int]] = {
    "乾": (1, 1, 1),
    "兑": (1, 1, 0),
    "离": (1, 0, 1),
    "震": (1, 0, 0),
    "巽": (0, 1, 1),
    "坎": (0, 1, 0),
    "艮": (0, 0, 1),
    "坤": (0, 0, 0),
}

# 矩阵下标顺序（行=下卦，列=上卦）
_TRIGRAM_ORDER = ["乾", "兑", "离", "震", "巽", "坎", "艮", "坤"]

# 六十四卦序卦表：MATRIX[下卦][上卦] = 卦序（周易本经序）
_MATRIX = [
    [1, 43, 14, 34, 9, 5, 26, 11],
    [10, 58, 38, 54, 61, 60, 41, 19],
    [13, 49, 30, 55, 37, 63, 22, 36],
    [25, 17, 21, 51, 42, 3, 27, 24],
    [44, 28, 50, 32, 57, 48, 18, 46],
    [6, 47, 64, 40, 59, 29, 4, 7],
    [33, 31, 56, 62, 53, 39, 52, 15],
    [12, 45, 35, 16, 20, 8, 23, 2],
]

# 卦序 → 卦名（含卦宫意象）
_HEXAGRAM_NAMES: dict[int, str] = {
    1: "乾为天", 2: "坤为地", 3: "水雷屯", 4: "山水蒙", 5: "水天需", 6: "天水讼",
    7: "地水师", 8: "水地比", 9: "风天小畜", 10: "天泽履", 11: "地天泰", 12: "天地否",
    13: "天火同人", 14: "火天大有", 15: "地山谦", 16: "雷地豫", 17: "泽雷随", 18: "山风蛊",
    19: "地泽临", 20: "风地观", 21: "火雷噬嗑", 22: "山火贲", 23: "山地剥", 24: "地雷复",
    25: "天雷无妄", 26: "山天大畜", 27: "山雷颐", 28: "泽风大过", 29: "坎为水", 30: "离为火",
    31: "泽山咸", 32: "雷风恒", 33: "天山遁", 34: "雷天大壮", 35: "火地晋", 36: "地火明夷",
    37: "风火家人", 38: "火泽睽", 39: "水山蹇", 40: "雷水解", 41: "山泽损", 42: "风雷益",
    43: "泽天夬", 44: "天风姤", 45: "泽地萃", 46: "地风升", 47: "泽水困", 48: "水风井",
    49: "泽火革", 50: "火风鼎", 51: "震为雷", 52: "艮为山", 53: "风山渐", 54: "雷泽归妹",
    55: "雷火丰", 56: "火山旅", 57: "巽为风", 58: "兑为泽", 59: "风水涣", 60: "水泽节",
    61: "风泽中孚", 62: "雷山小过", 63: "水火既济", 64: "火水未济",
}

# 由六爻阴阳位（自下而上 6 位）反查卦序，运行时一次性构建
_BITS_TO_NUMBER: dict[tuple[int, ...], int] = {}
_BITS_TO_NAME: dict[tuple[int, int, int], str] = {
    bits: name for name, bits in TRIGRAM_BITS.items()
}
for _li, _lower in enumerate(_TRIGRAM_ORDER):
    for _ui, _upper in enumerate(_TRIGRAM_ORDER):
        _bits = TRIGRAM_BITS[_lower] + TRIGRAM_BITS[_upper]  # 下卦在下，上卦在上
        _BITS_TO_NUMBER[_bits] = _MATRIX[_li][_ui]


def _trigram_name(bits: tuple[int, int, int]) -> str:
    return _BITS_TO_NAME[bits]


def _build_gua(bits: tuple[int, ...]) -> dict:
    """由 6 位阴阳（自下而上）构造单个卦的描述。"""
    number = _BITS_TO_NUMBER[bits]
    lower = _trigram_name(bits[:3])
    upper = _trigram_name(bits[3:])
    return {
        "number": number,
        "name": _HEXAGRAM_NAMES[number],
        "lower_trigram": lower,
        "upper_trigram": upper,
        "bits": list(bits),  # 自下而上，1=阳 0=阴
    }


def cast_from_yao(yao_values: list[int]) -> dict:
    """合并六次摇卦（自下而上的 6/7/8/9）成本卦、变卦及动爻信息。"""
    if len(yao_values) != 6:
        raise ValueError("六爻需恰好 6 个数字，自下而上。")
    for v in yao_values:
        if v not in YAO_INFO:
            raise ValueError("每爻须为 6、7、8、9 之一。")

    ben_bits = tuple(1 if YAO_INFO[v]["is_yang"] else 0 for v in yao_values)
    moving_positions = [i + 1 for i, v in enumerate(yao_values) if YAO_INFO[v]["is_moving"]]

    ben = _build_gua(ben_bits)
    lines = []
    for i, v in enumerate(yao_values, start=1):
        info = YAO_INFO[v]
        lines.append(
            {
                "position": i,  # 1=初爻（最下），6=上爻
                "yao_value": v,
                "name": info["name"],
                "is_yang": info["is_yang"],
                "is_moving": info["is_moving"],
                "symbol": info["symbol"],
            }
        )

    result: dict = {
        "lines": lines,
        "ben_gua": ben,
        "moving_positions": moving_positions,
        "bian_gua": None,
    }
    if moving_positions:
        # 动爻阴阳互变得变卦
        bian_bits = tuple(
            (1 - b) if (i + 1) in moving_positions else b for i, b in enumerate(ben_bits)
        )
        result["bian_gua"] = _build_gua(bian_bits)
    return result
