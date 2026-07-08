"""面相图片解码与 GPT-4o 视觉特征提取。"""

import json
from typing import Any, Literal

from config import settings
from services import prompts
from services.image_utils import extract_json
from services.vision_client import vision_completion, vision_completion_multi

FaceSlot = Literal["front", "side", "extra"]
FaceStopKey = Literal["upper", "middle", "lower"]
FaceOrganKey = Literal["brow", "eye", "nose", "mouth", "ear"]

SLOT_LABELS: dict[FaceSlot, str] = {
    "front": "正面照",
    "side": "侧面照",
    "extra": "补充角度",
}
SLOT_ORDER: tuple[FaceSlot, ...] = ("front", "side", "extra")

# 三停: name_cn, region(部位 · 主运)
STOP_META: dict[FaceStopKey, tuple[str, str]] = {
    "upper": ("上停", "发际至眉 · 主早年"),
    "middle": ("中停", "眉至鼻底 · 主中年"),
    "lower": ("下停", "鼻底至颏 · 主晚年"),
}

# 五官: name_cn, icon_text, office(传统官名), default_keywords
ORGAN_META: dict[FaceOrganKey, tuple[str, str, str, tuple[str, str]]] = {
    "brow": ("眉", "眉", "保寿官", ("情志", "兄弟")),
    "eye": ("眼", "眼", "监察官", ("心神", "智略")),
    "nose": ("鼻", "鼻", "审辨官", ("财帛", "自身")),
    "mouth": ("口", "口", "出纳官", ("言信", "福禄")),
    "ear": ("耳", "耳", "采听官", ("根基", "寿元")),
}


def _resolve_face_slots(
    image_urls: list[str],
    slots: list[FaceSlot] | None,
) -> list[FaceSlot]:
    if not image_urls:
        raise ValueError("请至少上传一张面部图片。")
    if len(image_urls) > 3:
        raise ValueError("最多上传 3 张面部图片。")

    effective_slots: list[FaceSlot] = list(slots) if slots else list(SLOT_ORDER[: len(image_urls)])
    if len(effective_slots) != len(image_urls):
        raise ValueError("图片与槽位数量不一致。")
    return effective_slots


async def extract_face_features(
    image_urls: list[str],
    slots: list[FaceSlot] | None = None,
) -> dict[str, Any]:
    """调用 GPT-4o 视觉模型，提取 1～3 张面相图的结构化特征。"""
    effective_slots = _resolve_face_slots(image_urls, slots)

    if len(image_urls) == 1:
        raw = await vision_completion(
            prompts.face_feature_system(),
            prompts.face_feature_user(slots=effective_slots),
            image_urls[0],
            image_detail="low",
            temperature=0.1,
            max_tokens=settings.face_feature_max_tokens,
        )
    else:
        raw = await vision_completion_multi(
            prompts.face_feature_system(),
            prompts.face_feature_user(slots=effective_slots),
            image_urls,
            image_detail="low",
            temperature=0.1,
            max_tokens=settings.face_feature_max_tokens,
        )
    return extract_json(raw, error_label="面相特征")


def feature_summary(features: dict[str, Any]) -> str:
    combined = features.get("combined")
    if isinstance(combined, dict):
        summary = combined.get("one_line_summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()

    summary = features.get("one_line_summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()

    shape = "未知脸型"
    if isinstance(combined, dict):
        shape = combined.get("face_shape", shape)
    else:
        shape = features.get("face_shape", shape)
    return f"脸型{shape}。"


def per_image_summaries(features: dict[str, Any]) -> list[str]:
    """按上传顺序返回每张图的一行摘要。"""
    per_image = features.get("per_image")
    if isinstance(per_image, list):
        out: list[str] = []
        for item in per_image:
            if not isinstance(item, dict):
                continue
            text = item.get("one_line_summary")
            if isinstance(text, str) and text.strip():
                out.append(text.strip())
            else:
                slot = item.get("slot", "")
                label = SLOT_LABELS.get(slot, "照片") if isinstance(slot, str) else "照片"
                quality = item.get("image_quality", "未知")
                out.append(f"{label}，图像{quality}。")
        if out:
            return out

    # 兼容旧版单图结构
    single = feature_summary(features)
    return [single] if single else []


def _clamp_score(value: Any) -> int:
    if isinstance(value, bool):
        return 3
    if isinstance(value, (int, float)):
        return max(1, min(5, int(value)))
    return 3


def _normalize_keywords(raw: Any, defaults: tuple[str, str]) -> list[str]:
    if isinstance(raw, list):
        cleaned = [str(item).strip() for item in raw if str(item).strip()]
        if len(cleaned) >= 2:
            return cleaned[:2]
        if len(cleaned) == 1:
            return [cleaned[0], defaults[1]]
    if isinstance(raw, str) and raw.strip():
        parts = [part.strip() for part in raw.replace("·", " ").split() if part.strip()]
        if len(parts) >= 2:
            return parts[:2]
        if len(parts) == 1:
            return [parts[0], defaults[1]]
    return [defaults[0], defaults[1]]


def _normalize_stop_items(raw_stops: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_stops, list):
        raise ValueError("面相三停解读解析失败，请重试。")

    by_key: dict[FaceStopKey, dict[str, Any]] = {}
    for item in raw_stops:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if key not in STOP_META:
            continue
        typed_key: FaceStopKey = key
        name_cn, region = STOP_META[typed_key]
        attribute = item.get("attribute")
        description = item.get("description")
        by_key[typed_key] = {
            "key": typed_key,
            "name_cn": name_cn,
            "region": region,
            "attribute": attribute.strip() if isinstance(attribute, str) and attribute.strip() else "—",
            "score": _clamp_score(item.get("score")),
            "description": description.strip() if isinstance(description, str) else "",
        }

    missing = [key for key in STOP_META if key not in by_key]
    if missing:
        raise ValueError("面相三停解读不完整，请重试。")

    return [by_key[key] for key in STOP_META]


def _normalize_organ_items(raw_organs: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_organs, list):
        raise ValueError("面相五官解读解析失败，请重试。")

    by_key: dict[FaceOrganKey, dict[str, Any]] = {}
    for item in raw_organs:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if key not in ORGAN_META:
            continue
        typed_key: FaceOrganKey = key
        name_cn, icon_text, office, default_keywords = ORGAN_META[typed_key]
        status = item.get("status")
        description = item.get("description")
        by_key[typed_key] = {
            "key": typed_key,
            "name_cn": name_cn,
            "icon_text": icon_text,
            "office": office,
            "keywords": _normalize_keywords(item.get("keywords"), default_keywords),
            "status": status.strip() if isinstance(status, str) and status.strip() else "匀",
            "description": description.strip() if isinstance(description, str) else "",
        }

    missing = [key for key in ORGAN_META if key not in by_key]
    if missing:
        raise ValueError("面相五官解读不完整，请重试。")

    return [by_key[key] for key in ORGAN_META]


def _combined(features: dict[str, Any]) -> dict[str, Any]:
    combined = features.get("combined")
    return combined if isinstance(combined, dict) else features


_SHAPE_TO_FACE_TYPE: dict[str, str] = {
    "圆形": "水形面",
    "方形": "金形面",
    "长形": "木形面",
    "鹅蛋": "土形面",
    "菱形": "火形面",
}

_FEATURE_ORGAN_KEYS: dict[FaceOrganKey, str] = {
    "brow": "eyebrows",
    "eye": "eyes",
    "nose": "nose",
    "mouth": "mouth",
    "ear": "ears",
}

_STOP_LENGTH_HINT: dict[str, str] = {
    "长": "停面偏长，该阶段行事重心更易被他人感知",
    "中": "停面适中，节奏平稳，宜守正出奇",
    "短": "停面偏短，该阶段宜主动经营，不宜完全随缘",
}

_ORGAN_FEATURE_HINT: dict[FaceOrganKey, str] = {
    "brow": "眉为保寿官，主情志与兄弟缘，眉势影响第一印象与决断气度",
    "eye": "眼为监察官，主心神与智略，眼神决定识人之准与专注深度",
    "nose": "鼻为审辨官，主财帛与自身，鼻梁鼻翼关系取舍与守成能力",
    "mouth": "口为出纳官，主言信与福禄，唇形口角影响表达分寸与人缘",
    "ear": "耳为采听官，主根基与寿元，耳位形态关系早年根基与吸纳力",
}


def _section_length(combined: dict[str, Any], key: FaceStopKey) -> str:
    sections = combined.get("three_sections")
    if not isinstance(sections, dict):
        return "中"
    raw = sections.get(key)
    if isinstance(raw, str) and raw.strip() in ("长", "中", "短"):
        return raw.strip()
    return "中"


def _organ_feature_text(combined: dict[str, Any], key: FaceOrganKey) -> str:
    features = combined.get("features")
    if not isinstance(features, dict):
        return ""
    raw = features.get(_FEATURE_ORGAN_KEYS[key])
    return raw.strip() if isinstance(raw, str) else ""


def _organ_preview_status(text: str) -> str:
    if any(word in text for word in ("饱满", "丰", "厚", "明", "有神", "挺直", "端正")):
        return "盛"
    if any(word in text for word in ("薄", "淡", "弱", "塌", "窄", "模糊")):
        return "平"
    return "匀"


def _stop_preview_hint(key: FaceStopKey, length: str) -> str:
    name_cn, region = STOP_META[key]
    body = _STOP_LENGTH_HINT.get(length, _STOP_LENGTH_HINT["中"])
    return f"{name_cn}（{region.split('·')[0].strip()}）{body}。"


def _organ_preview_hint(key: FaceOrganKey, text: str) -> str:
    name_cn, _, office, keywords = ORGAN_META[key]
    kw = "、".join(keywords)
    if text:
        feat = text if text.startswith(name_cn) else f"{name_cn}{text}"
        return f"{office}{feat}；多主{kw}。"
    return f"{_ORGAN_FEATURE_HINT[key]}；多主{kw}。"


def build_stop_previews(features: dict[str, Any]) -> list[dict[str, Any]]:
    combined = _combined(features)
    previews: list[dict[str, Any]] = []
    for key in STOP_META:
        typed_key: FaceStopKey = key
        name_cn, region = STOP_META[typed_key]
        length = _section_length(combined, typed_key)
        previews.append(
            {
                "key": typed_key,
                "name_cn": name_cn,
                "region": region,
                "attribute": length,
                "hint": _stop_preview_hint(typed_key, length),
            }
        )
    return previews


def build_organ_previews(features: dict[str, Any]) -> list[dict[str, Any]]:
    combined = _combined(features)
    previews: list[dict[str, Any]] = []
    for key in ORGAN_META:
        typed_key: FaceOrganKey = key
        name_cn, icon_text, office, default_keywords = ORGAN_META[typed_key]
        text = _organ_feature_text(combined, typed_key)
        attribute = text if text else "—"
        if len(attribute) > 18:
            attribute = attribute[:17] + "…"
        previews.append(
            {
                "key": typed_key,
                "name_cn": name_cn,
                "icon_text": icon_text,
                "office": office,
                "keywords": list(default_keywords),
                "status": _organ_preview_status(text),
                "attribute": attribute,
                "hint": _organ_preview_hint(typed_key, text),
            }
        )
    return previews


def build_extract_overview(features: dict[str, Any]) -> str:
    """识别阶段综合摘要：面型气色、三停比例与五官要点。"""
    combined = _combined(features)
    shape = combined.get("face_shape")
    shape_text = shape.strip() if isinstance(shape, str) and shape.strip() else "未知"
    face_type = _SHAPE_TO_FACE_TYPE.get(shape_text, shape_text)
    complexion = _fallback_complexion(features)

    sections = combined.get("three_sections")
    section_bits: list[str] = []
    if isinstance(sections, dict):
        for key in STOP_META:
            typed_key: FaceStopKey = key
            length = _section_length(combined, typed_key)
            name_cn = STOP_META[typed_key][0]
            section_bits.append(f"{name_cn}{length}")

    lead = f"{face_type}，气色{complexion}。"
    if section_bits:
        lead += f"三停比例：{'、'.join(section_bits)}。"

    organ_bits: list[str] = []
    for key in ORGAN_META:
        typed_key: FaceOrganKey = key
        text = _organ_feature_text(combined, typed_key)
        if text:
            name_cn = ORGAN_META[typed_key][0]
            label = text if text.startswith(name_cn) else f"{name_cn}{text}"
            organ_bits.append(label)
    if organ_bits:
        lead += "五官要点：" + "；".join(organ_bits[:5]) + "。"

    marks = combined.get("special_marks")
    if isinstance(marks, list):
        cleaned = [str(m).strip() for m in marks if str(m).strip() and str(m) != "无"]
        if cleaned:
            lead += "可见标记：" + "、".join(cleaned[:3]) + "。"

    per_image = features.get("per_image")
    if isinstance(per_image, list) and len(per_image) > 1:
        angles: list[str] = []
        for item in per_image:
            if not isinstance(item, dict):
                continue
            slot = item.get("slot")
            label = SLOT_LABELS.get(slot, "照片") if isinstance(slot, str) else "照片"
            quality = item.get("image_quality")
            if isinstance(quality, str) and quality.strip():
                angles.append(f"{label}{quality.strip()}")
        if angles:
            lead += "多角度：" + "；".join(angles) + "。"

    return lead


def build_extract_result(features: dict[str, Any]) -> dict[str, Any]:
    """组装特征提取结果，供前端先渲染识象预览。"""
    combined = _combined(features)
    shape = combined.get("face_shape")
    shape_text = shape.strip() if isinstance(shape, str) and shape.strip() else "未知面型"
    face_type = _SHAPE_TO_FACE_TYPE.get(shape_text, shape_text)
    summaries = per_image_summaries(features)
    return {
        "face_type": face_type,
        "face_shape": shape_text,
        "complexion": _fallback_complexion(features),
        "summary": feature_summary(features),
        "summaries": summaries or [feature_summary(features)],
        "extract_overview": build_extract_overview(features),
        "preview_stops": build_stop_previews(features),
        "preview_organs": build_organ_previews(features),
        "features": features,
    }


def _fallback_face_type(features: dict[str, Any]) -> str:
    combined = _combined(features)
    face_type = combined.get("face_type")
    if isinstance(face_type, str) and face_type.strip() and face_type != "未知":
        return face_type.strip()
    shape = combined.get("face_shape")
    if isinstance(shape, str) and shape.strip() and shape != "未知":
        mapped = _SHAPE_TO_FACE_TYPE.get(shape.strip())
        if mapped:
            return mapped
        return shape.strip()
    return "未知"


def _fallback_complexion(features: dict[str, Any]) -> str:
    combined = _combined(features)
    complexion = combined.get("complexion")
    if isinstance(complexion, str) and complexion.strip() and complexion != "未知":
        return complexion.strip()
    return "未知"


def _normalize_advice_items(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        raise ValueError("面相解读缺少实践建议，请重试。")
    items = [str(item).strip() for item in raw if str(item).strip()]
    if len(items) < 2:
        raise ValueError("面相实践建议不足，请重试。")
    return items[:6]


def _normalize_closing_summary(raw: Any) -> str:
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    raise ValueError("面相解读缺少综合总结，请重试。")


def _build_content_markdown(
    overview: str,
    stops: list[dict[str, Any]],
    organs: list[dict[str, Any]],
    *,
    closing_summary: str = "",
    advice_items: list[str] | None = None,
) -> str:
    parts: list[str] = []
    if overview:
        parts.append(f"## 面相综述\n\n{overview}")
    if stops:
        parts.append("## 三停")
        for stop in stops:
            parts.append(
                f"### {stop['name_cn']} · {stop['attribute']}（{stop['score']}/5）\n\n{stop['description']}"
            )
    if organs:
        parts.append("## 五官")
        for organ in organs:
            kw = " · ".join(organ["keywords"])
            parts.append(
                f"### {organ['name_cn']} · {organ['office']} · {kw}（{organ['status']}）\n\n{organ['description']}"
            )
    if closing_summary:
        parts.append(f"## 综合总结\n\n{closing_summary}")
    if advice_items:
        parts.append("## 实践建议\n\n" + "\n".join(f"- {item}" for item in advice_items))
    return "\n\n".join(parts)


def parse_structured_face_result(
    parsed: dict[str, Any],
    *,
    features: dict[str, Any],
) -> dict[str, Any]:
    """从模型 JSON 中解析前端所需的结构化面相解读。"""
    overview_raw = parsed.get("overview")
    if not isinstance(overview_raw, str) or not overview_raw.strip():
        raise ValueError("面相解读生成失败，请重试。")

    stops = _normalize_stop_items(parsed.get("stops"))
    organs = _normalize_organ_items(parsed.get("organs"))

    face_type_raw = parsed.get("face_type")
    complexion_raw = parsed.get("complexion")
    face_type = (
        face_type_raw.strip()
        if isinstance(face_type_raw, str) and face_type_raw.strip()
        else _fallback_face_type(features)
    )
    complexion = (
        complexion_raw.strip()
        if isinstance(complexion_raw, str) and complexion_raw.strip()
        else _fallback_complexion(features)
    )
    overview = overview_raw.strip()
    closing_summary = _normalize_closing_summary(parsed.get("closing_summary"))
    advice_items = _normalize_advice_items(parsed.get("advice_items"))

    content_raw = parsed.get("content")
    content = (
        content_raw.strip()
        if isinstance(content_raw, str) and content_raw.strip()
        else _build_content_markdown(
            overview, stops, organs,
            closing_summary=closing_summary,
            advice_items=advice_items,
        )
    )

    return {
        "content": content,
        "face_type": face_type,
        "complexion": complexion,
        "overview": overview,
        "closing_summary": closing_summary,
        "advice_items": advice_items,
        "stops": stops,
        "organs": organs,
    }


def _compact_face_features(features: dict[str, Any]) -> dict[str, Any]:
    """解读阶段精简特征：保留 combined 与各图角度/质量，去掉逐图长摘要。"""
    combined = features.get("combined")
    if not isinstance(combined, dict):
        return features
    per_image = features.get("per_image")
    compact_per: list[dict[str, Any]] = []
    if isinstance(per_image, list):
        for item in per_image:
            if not isinstance(item, dict):
                continue
            compact_per.append(
                {
                    "slot": item.get("slot"),
                    "image_quality": item.get("image_quality"),
                }
            )
    return {"combined": combined, "per_image": compact_per}


async def interpret_face_features(features: dict[str, Any]) -> dict[str, Any]:
    """基于已提取特征，由 DeepSeek 生成结构化面相解读。"""
    from services.deepseek_client import chat_completion

    overview = build_extract_overview(features)
    user = prompts.face_interpret_user(
        features=json.dumps(
            _compact_face_features(features), ensure_ascii=False, separators=(",", ":")
        ),
        extract_overview=overview,
    )
    raw = await chat_completion(
        prompts.face_interpret_system(),
        user,
        temperature=0.35,
        max_tokens=settings.face_interpret_max_tokens,
    )
    parsed = extract_json(raw, error_label="面相解读")
    return parse_structured_face_result(parsed, features=features)


async def analyze_face(
    image_urls: list[str],
    slots: list[FaceSlot] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """一次或两次模型调用完成面相解读，返回 (structured, features)。"""
    effective_slots = _resolve_face_slots(image_urls, slots)

    if settings.vision_single_stage:
        system = prompts.face_analyze_system()
        user = prompts.face_analyze_user(slots=effective_slots)
        if len(image_urls) == 1:
            raw = await vision_completion(system, user, image_urls[0], temperature=0.55)
        else:
            raw = await vision_completion_multi(
                system, user, image_urls, temperature=0.55
            )
        parsed = extract_json(raw, error_label="面相解读")
        structured = parse_structured_face_result(parsed, features=parsed)
        return structured, parsed

    features = await extract_face_features(image_urls, slots=effective_slots)
    structured = await interpret_face_features(features)
    return structured, features
