"""掌纹图片解码与 GPT-4o 视觉特征提取。"""

import asyncio
import json
from typing import Any, Literal

from config import settings
from services import prompts
from services.image_utils import extract_json
from services.vision_client import vision_completion, vision_completion_multi

HandSide = Literal["left", "right"]
PalmLineKey = Literal["life", "head", "heart"]
PalmMountKey = Literal["venus", "jupiter", "saturn", "apollo", "mercury"]

LINE_META: dict[PalmLineKey, tuple[str, str]] = {
    "life": ("生命线", "LIFE LINE"),
    "head": ("智慧线", "HEAD LINE"),
    "heart": ("感情线", "HEART LINE"),
}

MOUNT_META: dict[PalmMountKey, tuple[str, str, tuple[str, str]]] = {
    "venus": ("金星丘", "金", ("情爱", "活力")),
    "jupiter": ("木星丘", "木", ("志向", "进取")),
    "saturn": ("土星丘", "土", ("命运", "持守")),
    "apollo": ("太阳丘", "日", ("声名", "才艺")),
    "mercury": ("水星丘", "水", ("财利", "机变")),
}


def _normalize_hand_features(features: dict[str, Any], hand_side: HandSide) -> dict[str, Any]:
    features.setdefault("hand_side", hand_side)
    return features


async def extract_palm_features(
    image_data_url: str,
    hand_side: HandSide,
) -> dict[str, Any]:
    """调用 GPT-4o 视觉模型，提取单手掌纹结构化特征。"""
    side_label = "左手" if hand_side == "left" else "右手"
    raw = await vision_completion(
        prompts.palm_feature_system(),
        prompts.palm_feature_user(hand_side=side_label),
        image_data_url,
        max_tokens=settings.palm_feature_max_tokens,
        image_detail="low",
        temperature=0.1,
    )
    return _normalize_hand_features(
        extract_json(raw, error_label="掌纹特征"), hand_side
    )


async def extract_both_palm_features(
    left_url: str,
    right_url: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """左右手并行视觉提取，墙钟耗时≈较慢的一侧（优于单次双图请求）。"""
    left, right = await asyncio.gather(
        extract_palm_features(left_url, "left"),
        extract_palm_features(right_url, "right"),
    )
    return left, right


def feature_summary(features: dict[str, Any]) -> str:
    summary = features.get("one_line_summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    palm_type = features.get("palm_type")
    if isinstance(palm_type, str) and palm_type.strip() and palm_type != "未知":
        complexion = features.get("complexion", "")
        if isinstance(complexion, str) and complexion.strip() and complexion != "未知":
            return f"{palm_type.strip()}，气色{complexion.strip()}。"
        return f"{palm_type.strip()}。"
    shape = features.get("palm_shape", "未知掌形")
    quality = features.get("image_quality", "未知")
    return f"掌形{shape}，图像{quality}。"


def _clamp_score(value: Any) -> int:
    if isinstance(value, bool):
        return 3
    if isinstance(value, (int, float)):
        return max(1, min(5, int(value)))
    return 3


def _normalize_line_items(raw_lines: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_lines, list):
        raise ValueError("掌纹三线解读解析失败，请重试。")

    by_key: dict[PalmLineKey, dict[str, Any]] = {}
    for item in raw_lines:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if key not in LINE_META:
            continue
        typed_key: PalmLineKey = key
        name_cn, name_en = LINE_META[typed_key]
        attribute = item.get("attribute")
        description = item.get("description")
        by_key[typed_key] = {
            "key": typed_key,
            "name_cn": name_cn,
            "name_en": name_en,
            "attribute": attribute.strip() if isinstance(attribute, str) and attribute.strip() else "—",
            "score": _clamp_score(item.get("score")),
            "description": description.strip() if isinstance(description, str) else "",
        }

    missing = [key for key in LINE_META if key not in by_key]
    if missing:
        raise ValueError("掌纹三线解读不完整，请重试。")

    return [by_key[key] for key in LINE_META]


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


def _normalize_mount_items(raw_mounts: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_mounts, list):
        raise ValueError("掌纹五丘解读解析失败，请重试。")

    by_key: dict[PalmMountKey, dict[str, Any]] = {}
    for item in raw_mounts:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if key not in MOUNT_META:
            continue
        typed_key: PalmMountKey = key
        name_cn, icon_text, default_keywords = MOUNT_META[typed_key]
        status = item.get("status")
        description = item.get("description")
        by_key[typed_key] = {
            "key": typed_key,
            "name_cn": name_cn,
            "icon_text": icon_text,
            "keywords": _normalize_keywords(item.get("keywords"), default_keywords),
            "status": status.strip() if isinstance(status, str) and status.strip() else "匀",
            "description": description.strip() if isinstance(description, str) else "",
        }

    missing = [key for key in MOUNT_META if key not in by_key]
    if missing:
        raise ValueError("掌纹五丘解读不完整，请重试。")

    return [by_key[key] for key in MOUNT_META]


def _mount_status_from_features(raw_mounts: dict[str, Any] | None) -> dict[PalmMountKey, str]:
    mapping = {"隆起": "盛", "适中": "匀", "平坦": "平"}
    result: dict[PalmMountKey, str] = {}
    if not isinstance(raw_mounts, dict):
        return result
    for key in MOUNT_META:
        value = raw_mounts.get(key)
        if isinstance(value, str) and value in mapping:
            result[key] = mapping[value]
    return result


def _apply_mount_status_fallbacks(
    mounts: list[dict[str, Any]],
    primary_features: dict[str, Any],
) -> list[dict[str, Any]]:
    inferred = _mount_status_from_features(primary_features.get("mounts"))
    for mount in mounts:
        if mount["status"] == "匀" and mount["key"] in inferred:
            mount["status"] = inferred[mount["key"]]
    return mounts


def _normalize_primary_hand(value: Any) -> HandSide:
    if value == "left":
        return "left"
    return "right"


def _pick_hand_features(
    left: dict[str, Any],
    right: dict[str, Any],
    primary_hand: HandSide,
) -> dict[str, Any]:
    return right if primary_hand == "right" else left


_SHAPE_TO_PALM_TYPE: dict[str, str] = {
    "方形": "土形掌",
    "长方形": "木形掌",
    "修长": "水形掌",
}


def _line_preview_attribute(line: Any) -> str:
    if not isinstance(line, dict):
        return "—"
    parts: list[str] = []
    for key in ("length", "clarity"):
        value = line.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    trend = line.get("trend")
    if isinstance(trend, str) and trend.strip():
        parts.append(trend.strip())
    return " · ".join(parts) if parts else "—"


_LINE_LENGTH_HINT: dict[str, str] = {
    "长": "偏长，耐力与续航较好，习惯把事情做到底",
    "中": "长度适中，进退有度，不轻易冒进也不轻易放弃",
    "短": "偏短，决策明快，更倾向短平快的事务节奏",
}
_LINE_CLARITY_HINT: dict[str, str] = {
    "清晰": "纹线清楚，心性较稳，思路不易被外界带偏",
    "一般": "纹线尚可，遇压力时需刻意稳住节奏",
    "模糊": "纹线略浅，宜减少多线并行，先聚焦一件要事",
}
_MOUNT_STATUS_HINT: dict[str, str] = {
    "隆起": "隆起饱满，该领域精力投入多、存在感强",
    "适中": "饱满适中，能收能放，不宜过度偏科",
    "平坦": "相对平坦，该领域宜主动经营，不宜完全随缘",
}


def _line_preview_hint(key: PalmLineKey, line: dict[str, Any]) -> str:
    name_cn = LINE_META[key][0]
    length = str(line.get("length") or "中")
    clarity = str(line.get("clarity") or "一般")
    trend = str(line.get("trend") or "").strip()
    parts = [
        f"{name_cn}{_LINE_LENGTH_HINT.get(length, '长度适中')}",
        _LINE_CLARITY_HINT.get(clarity, ""),
    ]
    if trend:
        parts.append(f"走势{trend}")
    return "；".join(p for p in parts if p) + "。"


def _mount_preview_hint(key: PalmMountKey, raw_status: Any) -> str:
    name_cn = MOUNT_META[key][0]
    keywords = "、".join(MOUNT_META[key][2])
    status = raw_status if isinstance(raw_status, str) else "适中"
    body = _MOUNT_STATUS_HINT.get(status, _MOUNT_STATUS_HINT["适中"])
    return f"{name_cn}{body}，多主{keywords}。"


def _mount_preview_status(raw: Any) -> str:
    mapping = {"隆起": "盛", "适中": "匀", "平坦": "平"}
    if isinstance(raw, str) and raw in mapping:
        return mapping[raw]
    return "匀"


def build_line_previews(features: dict[str, Any]) -> list[dict[str, Any]]:
    raw_lines = features.get("lines")
    if not isinstance(raw_lines, dict):
        return []
    previews: list[dict[str, Any]] = []
    for key in LINE_META:
        typed_key: PalmLineKey = key
        name_cn, name_en = LINE_META[typed_key]
        line = raw_lines.get(key)
        if isinstance(line, dict) and line.get("visible") is False:
            continue
        previews.append(
            {
                "key": typed_key,
                "name_cn": name_cn,
                "name_en": name_en,
                "attribute": _line_preview_attribute(line if isinstance(line, dict) else {}),
                "hint": _line_preview_hint(
                    typed_key, line if isinstance(line, dict) else {}
                ),
            }
        )
    return previews


def build_mount_previews(features: dict[str, Any]) -> list[dict[str, Any]]:
    raw_mounts = features.get("mounts")
    if not isinstance(raw_mounts, dict):
        return []
    previews: list[dict[str, Any]] = []
    for key in MOUNT_META:
        typed_key: PalmMountKey = key
        name_cn, icon_text, keywords = MOUNT_META[typed_key]
        raw_status = raw_mounts.get(key)
        previews.append(
            {
                "key": typed_key,
                "name_cn": name_cn,
                "icon_text": icon_text,
                "status": _mount_preview_status(raw_status),
                "keywords": list(keywords),
                "hint": _mount_preview_hint(typed_key, raw_status),
            }
        )
    return previews


def _fallback_palm_type(features: dict[str, Any]) -> str:
    palm_type = features.get("palm_type")
    if isinstance(palm_type, str) and palm_type.strip() and palm_type != "未知":
        return palm_type.strip()
    shape = features.get("palm_shape")
    if isinstance(shape, str) and shape.strip():
        mapped = _SHAPE_TO_PALM_TYPE.get(shape.strip())
        if mapped:
            return mapped
        return shape.strip()
    return "未知"


def _fallback_palm_shape(features: dict[str, Any]) -> str:
    shape = features.get("palm_shape")
    if isinstance(shape, str) and shape.strip():
        return shape.strip()
    return "未知"


def build_extract_overview(
    left_features: dict[str, Any],
    right_features: dict[str, Any],
    *,
    primary_hand: HandSide,
) -> str:
    """识别阶段综合摘要：突出左右差异，避免与分手摘要重复堆砌。"""
    primary = _pick_hand_features(left_features, right_features, primary_hand)
    hand_label = "右手" if primary_hand == "right" else "左手"
    left_type = _fallback_palm_type(left_features)
    right_type = _fallback_palm_type(right_features)
    left_comp = _fallback_complexion(left_features)
    right_comp = _fallback_complexion(right_features)

    lead = (
        f"主看{hand_label}，{_fallback_palm_type(primary)}，气色{_fallback_complexion(primary)}。"
    )
    contrast_parts: list[str] = []
    if left_type != right_type:
        contrast_parts.append(f"左手偏{left_type}、右手偏{right_type}")
    if left_comp != right_comp:
        contrast_parts.append(f"左气色{left_comp}、右气色{right_comp}")
    if contrast_parts:
        lead += "左右对照：" + "；".join(contrast_parts) + "。"

    line_notes: list[str] = []
    for label, feats in (("左手", left_features), ("右手", right_features)):
        raw_lines = feats.get("lines")
        if not isinstance(raw_lines, dict):
            continue
        for key in LINE_META:
            line = raw_lines.get(key)
            if not isinstance(line, dict):
                continue
            attr = _line_preview_attribute(line)
            if attr != "—":
                line_notes.append(f"{label}{LINE_META[key][0]}{attr}")
    if line_notes:
        lead += "主线：" + "；".join(line_notes[:4]) + "。"

    return lead


def _fallback_complexion(features: dict[str, Any]) -> str:
    complexion = features.get("complexion")
    if isinstance(complexion, str) and complexion.strip() and complexion != "未知":
        return complexion.strip()
    return "未知"


def build_extract_result(
    left_features: dict[str, Any],
    right_features: dict[str, Any],
    *,
    primary_hand: HandSide = "right",
) -> dict[str, Any]:
    """组装特征提取结果，供前端先渲染头部标签。"""
    primary = _pick_hand_features(left_features, right_features, primary_hand)
    return {
        "left_features": left_features,
        "right_features": right_features,
        "left_summary": feature_summary(left_features),
        "right_summary": feature_summary(right_features),
        "primary_hand": primary_hand,
        "palm_type": _fallback_palm_type(primary),
        "palm_shape": _fallback_palm_shape(primary),
        "complexion": _fallback_complexion(primary),
        "extract_overview": build_extract_overview(
            left_features, right_features, primary_hand=primary_hand
        ),
        "preview_lines": build_line_previews(primary),
        "preview_mounts": build_mount_previews(primary),
    }


def _normalize_advice_items(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        raise ValueError("掌纹解读缺少实践建议，请重试。")
    items = [str(item).strip() for item in raw if str(item).strip()]
    if len(items) < 2:
        raise ValueError("掌纹实践建议不足，请重试。")
    return items[:6]


def _normalize_closing_summary(raw: Any) -> str:
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    raise ValueError("掌纹解读缺少综合总结，请重试。")


def _build_content_markdown(
    overview: str,
    lines: list[dict[str, Any]],
    mounts: list[dict[str, Any]],
    *,
    closing_summary: str = "",
    advice_items: list[str] | None = None,
) -> str:
    parts: list[str] = []
    if overview:
        parts.append(f"## 掌象综述\n\n{overview}")
    for line in lines:
        title = line["name_cn"]
        attribute = line["attribute"]
        score = line["score"]
        body = line["description"]
        parts.append(f"## {title} · {attribute}（{score}/5）\n\n{body}")
    if mounts:
        parts.append("## 五丘")
        for mount in mounts:
            kw = " · ".join(mount["keywords"])
            parts.append(
                f"### {mount['name_cn']} · {kw}（{mount['status']}）\n\n{mount['description']}"
            )
    if closing_summary:
        parts.append(f"## 综合总结\n\n{closing_summary}")
    if advice_items:
        parts.append("## 实践建议\n\n" + "\n".join(f"- {item}" for item in advice_items))
    return "\n\n".join(parts)


def parse_structured_palm_result(
    parsed: dict[str, Any],
    *,
    left_features: dict[str, Any],
    right_features: dict[str, Any],
    primary_hand: HandSide | None = None,
) -> dict[str, Any]:
    """从模型 JSON 中解析前端所需的结构化掌纹解读。"""
    overview_raw = parsed.get("overview")
    if not isinstance(overview_raw, str) or not overview_raw.strip():
        raise ValueError("掌纹解读生成失败，请重试。")

    resolved_primary = _normalize_primary_hand(
        primary_hand if primary_hand is not None else parsed.get("primary_hand")
    )
    primary_features = _pick_hand_features(left_features, right_features, resolved_primary)
    lines = _normalize_line_items(parsed.get("lines"))
    mounts = _apply_mount_status_fallbacks(
        _normalize_mount_items(parsed.get("mounts")),
        primary_features,
    )

    palm_type_raw = parsed.get("palm_type")
    complexion_raw = parsed.get("complexion")
    palm_type = (
        palm_type_raw.strip()
        if isinstance(palm_type_raw, str) and palm_type_raw.strip()
        else _fallback_palm_type(primary_features)
    )
    complexion = (
        complexion_raw.strip()
        if isinstance(complexion_raw, str) and complexion_raw.strip()
        else _fallback_complexion(primary_features)
    )
    overview = overview_raw.strip()
    closing_summary = _normalize_closing_summary(parsed.get("closing_summary"))
    advice_items = _normalize_advice_items(parsed.get("advice_items"))

    content_raw = parsed.get("content")
    content = (
        content_raw.strip()
        if isinstance(content_raw, str) and content_raw.strip()
        else _build_content_markdown(
            overview, lines, mounts,
            closing_summary=closing_summary,
            advice_items=advice_items,
        )
    )

    return {
        "content": content,
        "palm_type": palm_type,
        "complexion": complexion,
        "primary_hand": resolved_primary,
        "overview": overview,
        "closing_summary": closing_summary,
        "advice_items": advice_items,
        "lines": lines,
        "mounts": mounts,
    }


def _parse_dual_palm_response(raw: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    parsed = extract_json(raw, error_label="掌纹解读")

    left_raw = parsed.get("left")
    right_raw = parsed.get("right")
    if not isinstance(left_raw, dict) or not isinstance(right_raw, dict):
        raise ValueError("掌纹特征解析失败，请重试。")

    left = _normalize_hand_features(left_raw, "left")
    right = _normalize_hand_features(right_raw, "right")
    structured = parse_structured_palm_result(parsed, left_features=left, right_features=right)
    return structured, left, right


async def extract_palms(
    left_url: str,
    right_url: str,
) -> dict[str, Any]:
    """左右手并行提取掌纹特征，墙钟耗时≈单手的 GPT 耗时。"""
    left, right = await extract_both_palm_features(left_url, right_url)
    return build_extract_result(left, right)


def _compact_hand_features(features: dict[str, Any]) -> dict[str, Any]:
    """解读阶段精简特征 JSON，去掉识象摘要等重复字段。"""
    keys = ("hand_side", "palm_shape", "palm_type", "complexion", "lines", "mounts")
    return {k: features[k] for k in keys if k in features}


async def interpret_palm_features(
    left_features: dict[str, Any],
    right_features: dict[str, Any],
    *,
    primary_hand: HandSide | None = None,
) -> dict[str, Any]:
    """基于已提取特征，由 DeepSeek 生成结构化解读。"""
    from services.deepseek_client import chat_completion

    resolved_primary = _normalize_primary_hand(primary_hand)
    overview = build_extract_overview(
        left_features, right_features, primary_hand=resolved_primary
    )
    user = prompts.palm_interpret_user(
        left_features=json.dumps(
            _compact_hand_features(left_features), ensure_ascii=False, separators=(",", ":")
        ),
        right_features=json.dumps(
            _compact_hand_features(right_features), ensure_ascii=False, separators=(",", ":")
        ),
        extract_overview=overview,
    )
    raw = await chat_completion(
        prompts.palm_interpret_system(),
        user,
        temperature=0.35,
        max_tokens=settings.palm_interpret_max_tokens,
    )
    parsed = extract_json(raw, error_label="掌纹解读")
    return parse_structured_palm_result(
        parsed,
        left_features=left_features,
        right_features=right_features,
        primary_hand=resolved_primary,
    )


async def analyze_palms_single_stage(
    left_url: str,
    right_url: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """单阶段视觉解读（慢，仅 VISION_SINGLE_STAGE=true 时使用）。"""
    raw = await vision_completion_multi(
        prompts.palm_analyze_system(),
        prompts.palm_analyze_dual_user(),
        [left_url, right_url],
        temperature=0.55,
    )
    return _parse_dual_palm_response(raw)


async def analyze_palms(
    left_url: str,
    right_url: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """完整掌纹解读：默认走「并行提取 + DeepSeek 解读」。"""
    if settings.vision_single_stage:
        return await analyze_palms_single_stage(left_url, right_url)

    extracted = await extract_palms(left_url, right_url)
    structured = await interpret_palm_features(
        extracted["left_features"],
        extracted["right_features"],
        primary_hand=extracted["primary_hand"],
    )
    return (
        structured,
        extracted["left_features"],
        extracted["right_features"],
    )
