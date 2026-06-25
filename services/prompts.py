"""各玄学功能的系统提示与用户内容模板。"""

SYSTEM_BASE = (
    "你是一位精通中国传统术数（易经、六爻、紫微斗数、八字命理）的学者，"
    "回答需条理清晰、用语准确，避免迷信恐吓式话术；可作文化参考，不替代医疗与法律建议。"
)


def lottery_interpret_system() -> str:
    return (
        SYSTEM_BASE
        + "当前任务：解签。签文已由问卜方抽出并给定，你不得改换签号、签题或签诗原文。"
        "请紧扣签诗意象与签题，结合问卜者的日期与所问（若有），用中性、温和的语言解签："
        "简述寓意、心态与行事建议；避免绝对化断语与恐吓；可作文化参考。"
    )


def lottery_interpret_user(
    *,
    slip_id: int,
    slip_tier: str,
    slip_title: str,
    slip_poem: str,
    solar_date: str,
    lunar_hint: str,
    name: str | None,
    focus: str | None,
    question: str | None,
) -> str:
    parts = [
        f"【所抽灵签】第 {slip_id} 签",
        f"等第：{slip_tier}",
        f"签题：{slip_title}",
        "签诗：",
        slip_poem,
        f"占问公历：{solar_date}",
        f"农历参考：{lunar_hint}",
    ]
    if name:
        parts.append(f"称呼：{name}")
    if focus:
        parts.append(f"今日关注：{focus}")
    if question:
        parts.append(f"所问事项：{question}")
    parts.append(
        "请输出结构化解签（可用小标题）：①签意总览 ②与所问之呼应（若无则写通用心境）"
        "③宜与忌（行事与心态，忌夸大）④一句赠言。总字数控制在 400 字以内。"
    )
    return "\n".join(parts)


def liuyao_system() -> str:
    return (
        SYSTEM_BASE
        + "当前任务：六爻纳甲分析。根据所给卦象与问事，解读动爻、用神、旺衰与应期思路（学术化表述）。"
    )


def liuyao_cast_user(
    *,
    question: str,
    ben_gua: str,
    bian_gua: str | None,
    moving_desc: str,
    lines_desc: str,
) -> str:
    parts = [
        f"所问事项：{question}",
        f"本卦：{ben_gua}",
    ]
    if bian_gua:
        parts.append(f"变卦：{bian_gua}")
    else:
        parts.append("变卦：无动爻，以本卦静断。")
    parts.append(f"动爻：{moving_desc}")
    parts.append("六爻（自下而上）：")
    parts.append(lines_desc)
    parts.append(
        "请输出结构化解卦（可用小标题）：①卦象总述（本卦卦意，有变卦则述卦变趋势）"
        "②动爻提示（无动爻则述静卦取意）③针对所问的吉凶趋势 ④可操作建议 ⑤一句赠言。"
        "用中性、温和、学术化的语言，避免绝对化与恐吓，总字数 500 字以内。"
    )
    return "\n".join(parts)


def ziwei_system() -> str:
    return (
        SYSTEM_BASE
        + "当前任务：紫微斗数排盘解读。根据出生资料，简述命盘结构、主星分布重点与大运流年切入点（文化参考）。"
    )


def ziwei_user(*, birth_solar: str, gender: str, extra: str | None) -> str:
    lines = [f"出生时间（公历）：{birth_solar}", f"性别：{gender}"]
    if extra:
        lines.append(f"补充说明：{extra}")
    lines.append("请给出命宫身宫要点、三方四正概览、当前大运可留意之处。")
    return "\n".join(lines)


def bazi_system() -> str:
    return (
        SYSTEM_BASE
        + "当前任务：四柱八字分析。根据出生干支与五行流通，分析格局、喜忌与运势倾向（不作绝对断语）。"
    )


def bazi_user(
    *,
    gender: str,
    birth_place: str,
    birth_input: str,
    birth_solar: str,
    birth_hour_label: str,
    sexual_orientation: str,
    pillars_hint: str,
    focus: list[str],
) -> str:
    focus_text = "、".join(focus)
    lines = [
        f"性别：{gender}",
        f"出生地：{birth_place}",
        f"出生日期（用户填写）：{birth_input}",
        f"出生时间（归一公历）：{birth_solar}",
        f"出生时辰：{birth_hour_label}",
        f"性取向：{sexual_orientation}",
        f"四柱参考（程序推算，请复核）：{pillars_hint}",
        f"关注事项：{focus_text}",
    ]
    lines.append(
        "请结合四柱八字，针对用户所选关注事项分别解读（仅写已选维度，用小标题区分）。"
        "感情分析须兼顾性取向语境，避免刻板异性恋假设；"
        "整体须含：日主强弱与喜用神方向、性格基调。"
        "用语中性温和、学术化，避免绝对化与恐吓，总字数 600 字以内。"
    )
    return "\n".join(lines)


def meihua_system() -> str:
    return (
        SYSTEM_BASE
        + "当前任务：梅花易数解卦。依据体用生克、本卦变卦与互卦，结合所问给出卦象解读（学术化、文化参考）。"
    )


def meihua_user(
    *,
    question: str,
    method_label: str,
    method_detail: str,
    ben_gua: str,
    bian_gua: str,
    hu_gua: str,
    ti_trigram: str,
    yong_trigram: str,
    moving_line: int,
) -> str:
    parts = [
        f"所问事项：{question}",
        f"起卦方式：{method_label}",
        f"起卦过程：{method_detail}",
        f"本卦：{ben_gua}",
        f"变卦：{bian_gua}",
        f"互卦：{hu_gua}",
        f"体卦：{ti_trigram}，用卦：{yong_trigram}",
        f"动爻：第{moving_line}爻",
    ]
    parts.append(
        "请输出结构化梅花易数解卦（可用小标题）：①卦象总述（本卦卦意）"
        "②体用生克与动静趋势 ③变卦、互卦对事态的提示 ④针对所问的分析与建议 ⑤一句赠言。"
        "用中性、温和、学术化的语言，避免绝对化与恐吓，总字数 500 字以内。"
    )
    return "\n".join(parts)


def palm_feature_system() -> str:
    return (
        "你是掌纹图像观察助手，只描述可见特征，不作吉凶断语。"
        "无法识别清晰手掌时 hand_detected=false。只输出 JSON，无 markdown、无说明。"
    )


def palm_feature_user(*, hand_side: str) -> str:
    return _palm_single_hand_schema(hand_side)


def palm_feature_dual_user() -> str:
    return (
        "第一张图是左手，第二张图是右手。分别观察并输出 JSON：\n"
        '{"left":' + _palm_hand_fields("左手") + ',"right":' + _palm_hand_fields("右手") + "}"
    )


def _palm_hand_fields(hand_side: str) -> str:
    return (
        "{"
        f'"hand_detected":true,"hand_side":"{hand_side}",'
        '"image_quality":"clear|blurry|shadowed",'
        '"palm_shape":"方形|长方形|修长|其他",'
        '"palm_type":"金形掌|木形掌|水形掌|火形掌|土形掌|未知",'
        '"complexion":"红润|苍白|暗沉|偏黄|未知",'
        '"lines":{"life":{"visible":true,"length":"短|中|长","clarity":"清晰|一般|模糊","trend":"走向简述"},'
        '"heart":{"visible":true,"length":"短|中|长","clarity":"清晰|一般|模糊","trend":"走向简述"},'
        '"head":{"visible":true,"length":"短|中|长","clarity":"清晰|一般|模糊","trend":"走向简述"}},'
        '"mounts":{"venus":"平坦|适中|隆起","jupiter":"平坦|适中|隆起","saturn":"平坦|适中|隆起",'
        '"apollo":"平坦|适中|隆起","mercury":"平坦|适中|隆起"},'
        '"special_marks":[],"one_line_summary":"20字内客观描述"}'
    )


def _palm_structured_interpret_fields() -> str:
    line = (
        '{"key":"life|head|heart","attribute":"2-4字特征词如深长|清晰|柔缓",'
        '"score":1-5,"description":"60-90字该线文化解读，不作医疗断语"}'
    )
    mount = (
        '{"key":"venus|jupiter|saturn|apollo|mercury",'
        '"keywords":["2字词","2字词"],'
        '"status":"旺|盛|匀|平|弱",'
        '"description":"30-50字该丘文化解读，基于隆起程度与位置"}'
    )
    return (
        '"palm_type":"金形掌|木形掌|水形掌|火形掌|土形掌",'
        '"complexion":"红润|苍白|暗沉|偏黄|其他简述",'
        '"primary_hand":"left|right",'
        '"overview":"掌象综述，100-150字，综合左右掌形气质与整体印象",'
        f'"lines":[{line},{line},{line}],'
        f'"mounts":[{mount},{mount},{mount},{mount},{mount}]'
    )


def _palm_single_hand_schema(hand_side: str) -> str:
    return f"观察这张{hand_side}掌图，输出 JSON：\n{_palm_hand_fields(hand_side)}"


def palm_interpret_system() -> str:
    return (
        SYSTEM_BASE
        + "当前任务：掌纹（手相）文化解读。根据已给的结构化掌纹特征输出 JSON，"
        "不得臆造特征中未出现的线条或标记；强调文化参考与心态建议，不作医疗诊断或绝对命运断语。"
        "只输出 JSON，无 markdown、无说明。"
    )


def palm_interpret_user(*, left_features: str, right_features: str) -> str:
    parts = [
        "【左手特征（程序提取，请据此解读）】",
        left_features,
        "",
        "【右手特征（程序提取，请据此解读）】",
        right_features,
        "",
        "请只输出 JSON（无 markdown 代码块），字段：",
        "{" + _palm_structured_interpret_fields() + "}",
        "lines 须含 life、head、heart 各一条且 key 不重复；"
        "mounts 须含 venus、jupiter、saturn、apollo、mercury 各一条且 key 不重复；"
        "mounts.status 反映该丘隆起与饱满程度（隆起→旺/盛，适中→匀/盛，平坦→平/弱）；"
        "primary_hand 表示惯用手/主看之手（通常右手）；"
        "score 为 1-5 整数，表该线形质优劣的文化参考，非医学指标；"
        "解读须严格基于特征，不得臆造未见线条。",
    ]
    return "\n".join(parts)


def palm_analyze_system() -> str:
    return (
        SYSTEM_BASE
        + "当前任务：观察左右掌纹并一次输出 JSON（含特征与解读）。"
        "无法识别清晰手掌时对应 hand_detected=false。"
        "解读须基于所见特征，文化参考、温和表述，不作医疗或绝对断语。"
        "只输出 JSON，无 markdown 代码块。"
    )


def palm_analyze_dual_user() -> str:
    return (
        "图1=左手，图2=右手。输出 JSON：\n"
        '{"left":' + _palm_hand_fields("左手") + ',"right":' + _palm_hand_fields("右手") + ","
        + _palm_structured_interpret_fields()
        + "}"
    )


def face_feature_system() -> str:
    return (
        "你是面相图像观察助手，只描述可见的面部结构与五官特征，"
        "不作吉凶、命运、健康等断语。正面照无法识别清晰正脸时 face_detected=false。"
        "只输出 JSON，无 markdown、无说明。"
    )


def _face_per_image_fields(slot: str, label: str) -> str:
    return (
        "{"
        f'"slot":"{slot}","label":"{label}",'
        '"image_quality":"clear|blurry|shadowed|侧脸|未辨识",'
        '"visible_parts":"可见部位简述",'
        '"one_line_summary":"20字内客观描述"'
        "}"
    )


def _face_combined_fields() -> str:
    return (
        "{"
        '"face_shape":"圆形|方形|长形|鹅蛋|菱形|其他",'
        '"three_sections":{"upper":"长|中|短","middle":"长|中|短","lower":"长|中|短"},'
        '"features":{'
        '"eyebrows":"眉形与浓淡简述",'
        '"eyes":"眼型与神采简述",'
        '"nose":"鼻型简述",'
        '"mouth":"口型与唇形简述",'
        '"ears":"耳位与形态简述"'
        "},"
        '"complexion":"气色简述",'
        '"special_marks":["痣|疤|纹|无"],'
        '"one_line_summary":"综合20字内客观描述"'
        "}"
    )


def face_feature_user(*, slots: list[str]) -> str:
    slot_defs = {
        "front": ("front", "正面照"),
        "side": ("side", "侧面照"),
        "extra": ("extra", "补充角度"),
    }
    lines = ["按上传顺序观察下列照片，并输出 JSON："]
    for i, slot in enumerate(slots, start=1):
        key, label = slot_defs.get(slot, (slot, f"图{i}"))
        lines.append(f"第{i}张={label}")

    per_items = ", ".join(
        _face_per_image_fields(*slot_defs.get(s, (s, s)))
        for s in slots
    )
    lines.append(
        "{"
        '"face_detected":true,'
        f'"per_image":[{per_items}],'
        f'"combined":{_face_combined_fields()}'
        "}"
    )
    lines.append("综合特征应主要依据正面照，侧面与补充图用于补充耳、颌、轮廓等信息。看不清写「未辨识」。")
    return "\n".join(lines)


def _face_structured_interpret_fields() -> str:
    stop = (
        '{"key":"upper|middle|lower","attribute":"2-4字特征词如丰隆|挺正|温厚",'
        '"score":1-5,"description":"60-100字该停文化解读，不作医疗断语"}'
    )
    organ = (
        '{"key":"brow|eye|nose|mouth|ear",'
        '"keywords":["2字词","2字词"],'
        '"status":"旺|盛|匀|平|弱",'
        '"description":"40-60字该官文化解读，基于五官形态"}'
    )
    return (
        '"face_type":"金形面|木形面|水形面|火形面|土形面",'
        '"complexion":"红润|明润|苍白|暗沉|偏黄|其他简述",'
        '"overview":"面相综述，120-180字，综合三停五官与整体气质印象",'
        f'"stops":[{stop},{stop},{stop}],'
        f'"organs":[{organ},{organ},{organ},{organ},{organ}]'
    )


def _face_structured_rules() -> str:
    return (
        "stops 须含 upper、middle、lower 各一条且 key 不重复"
        "（上停=发际至眉主早年，中停=眉至鼻底主中年，下停=鼻底至颏主晚年）；"
        "organs 须含 brow、eye、nose、mouth、ear 各一条且 key 不重复；"
        "organs.status 反映该官的端正与饱满程度；"
        "score 为 1-5 整数，表该停形质的文化参考，非医学指标；"
        "解读须严格基于特征，不得臆造未见部位。"
    )


def face_interpret_system() -> str:
    return (
        SYSTEM_BASE
        + "当前任务：面相文化解读。根据已给的结构化面部特征输出 JSON，"
        "不得臆造特征中未出现的部位或标记；强调文化参考与心态建议，不作医疗诊断或绝对命运断语。"
        "只输出 JSON，无 markdown、无说明。"
    )


def face_interpret_user(*, features: str) -> str:
    parts = [
        "【面相特征（程序提取，请据此解读）】",
        features,
        "",
        "请只输出 JSON（无 markdown 代码块），字段：",
        "{" + _face_structured_interpret_fields() + "}",
        _face_structured_rules(),
    ]
    return "\n".join(parts)


def face_analyze_system() -> str:
    return (
        SYSTEM_BASE
        + "当前任务：观察面部照片并一次输出 JSON（含特征与结构化解读）。"
        "无清晰正脸时 face_detected=false。"
        "解读须基于所见特征，文化参考、温和表述，不作医疗或绝对断语。"
        "只输出 JSON，无 markdown 代码块。"
    )


def face_analyze_user(*, slots: list[str]) -> str:
    slot_defs = {
        "front": ("front", "正面照"),
        "side": ("side", "侧面照"),
        "extra": ("extra", "补充角度"),
    }
    lines = ["按顺序观察照片并输出 JSON："]
    for i, slot in enumerate(slots, start=1):
        _, label = slot_defs.get(slot, (slot, f"图{i}"))
        lines.append(f"第{i}张={label}")

    per = (
        '{"slot":"front","one_line_summary":"20字内","image_quality":"clear|blurry|shadowed"}'
    )
    lines.append(
        "{"
        '"face_detected":true,'
        f'"per_image":[{per}],'
        '"combined":{"face_shape":"圆形|方形|长形|鹅蛋|其他","one_line_summary":"综合20字内"},'
        + _face_structured_interpret_fields()
        + "}"
    )
    lines.append("per_image 数量与照片一致；综合特征以正面为主。" + _face_structured_rules())
    return "\n".join(lines)
