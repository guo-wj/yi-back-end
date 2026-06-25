"""掌纹图片解码与智谱视觉特征提取。"""

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
    """调用智谱视觉模型，提取单手掌纹结构化特征。"""
    side_label = "左手" if hand_side == "left" else "右手"
    raw = await vision_completion(
        prompts.palm_feature_system(),
        prompts.palm_feature_user(hand_side=side_label),
        image_data_url,
        max_tokens=settings.palm_feature_max_tokens,
    )
    return _normalize_hand_features(
        extract_json(raw, error_label="掌纹特征"), hand_side
    )


async def extract_both_palm_features(
    left_url: str,
    right_url: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """左右手并行视觉提取，耗时约等于较慢的一侧。"""
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


def _fallback_palm_type(features: dict[str, Any]) -> str:
    palm_type = features.get("palm_type")
    if isinstance(palm_type, str) and palm_type.strip() and palm_type != "未知":
        return palm_type.strip()
    shape = features.get("palm_shape")
    if isinstance(shape, str) and shape.strip():
        return shape.strip()
    return "未知"


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
        "complexion": _fallback_complexion(primary),
    }


def _build_content_markdown(
    overview: str,
    lines: list[dict[str, Any]],
    mounts: list[dict[str, Any]],
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

    content_raw = parsed.get("content")
    content = (
        content_raw.strip()
        if isinstance(content_raw, str) and content_raw.strip()
        else _build_content_markdown(overview, lines, mounts)
    )

    return {
        "content": content,
        "palm_type": palm_type,
        "complexion": complexion,
        "primary_hand": resolved_primary,
        "overview": overview,
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
    """并行提取左右掌纹特征，通常 5–10s。"""
    left, right = await extract_both_palm_features(left_url, right_url)
    return build_extract_result(left, right)


async def interpret_palm_features(
    left_features: dict[str, Any],
    right_features: dict[str, Any],
    *,
    primary_hand: HandSide | None = None,
) -> dict[str, Any]:
    """基于已提取特征，由 DeepSeek 生成结构化解读，通常 3–6s。"""
    from services.deepseek_client import chat_completion

    resolved_primary = _normalize_primary_hand(primary_hand)
    user = prompts.palm_interpret_user(
        left_features=json.dumps(left_features, ensure_ascii=False, separators=(",", ":")),
        right_features=json.dumps(right_features, ensure_ascii=False, separators=(",", ":")),
    )
    raw = await chat_completion(
        prompts.palm_interpret_system(),
        user,
        temperature=0.65,
        max_tokens=settings.interpret_max_tokens,
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
