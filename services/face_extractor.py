"""面相图片解码与智谱视觉特征提取。"""

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
    """调用智谱视觉模型，提取 1～3 张面相图的结构化特征。"""
    effective_slots = _resolve_face_slots(image_urls, slots)

    if len(image_urls) == 1:
        raw = await vision_completion(
            prompts.face_feature_system(),
            prompts.face_feature_user(slots=effective_slots),
            image_urls[0],
        )
    else:
        raw = await vision_completion_multi(
            prompts.face_feature_system(),
            prompts.face_feature_user(slots=effective_slots),
            image_urls,
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


def _fallback_face_type(features: dict[str, Any]) -> str:
    combined = _combined(features)
    face_type = combined.get("face_type")
    if isinstance(face_type, str) and face_type.strip() and face_type != "未知":
        return face_type.strip()
    shape = combined.get("face_shape")
    if isinstance(shape, str) and shape.strip() and shape != "未知":
        return shape.strip()
    return "未知"


def _fallback_complexion(features: dict[str, Any]) -> str:
    combined = _combined(features)
    complexion = combined.get("complexion")
    if isinstance(complexion, str) and complexion.strip() and complexion != "未知":
        return complexion.strip()
    return "未知"


def _build_content_markdown(
    overview: str,
    stops: list[dict[str, Any]],
    organs: list[dict[str, Any]],
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

    content_raw = parsed.get("content")
    content = (
        content_raw.strip()
        if isinstance(content_raw, str) and content_raw.strip()
        else _build_content_markdown(overview, stops, organs)
    )

    return {
        "content": content,
        "face_type": face_type,
        "complexion": complexion,
        "overview": overview,
        "stops": stops,
        "organs": organs,
    }


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
    from services.deepseek_client import chat_completion

    user = prompts.face_interpret_user(
        features=json.dumps(features, ensure_ascii=False, separators=(",", ":")),
    )
    raw = await chat_completion(
        prompts.face_interpret_system(),
        user,
        temperature=0.65,
        max_tokens=settings.interpret_max_tokens,
    )
    parsed = extract_json(raw, error_label="面相解读")
    structured = parse_structured_face_result(parsed, features=features)
    return structured, features
