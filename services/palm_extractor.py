"""掌纹图片解码与智谱视觉特征提取。"""

import json
from typing import Any, Literal

from config import settings
from services import prompts
from services.image_utils import extract_json
from services.vision_client import vision_completion, vision_completion_multi

HandSide = Literal["left", "right"]


def _normalize_hand_features(features: dict[str, Any], hand_side: HandSide) -> dict[str, Any]:
    features.setdefault("hand_side", hand_side)
    return features


async def extract_palm_features(
    image_data_url: str,
    hand_side: HandSide,
) -> dict[str, Any]:
    """调用智谱视觉模型，提取单手掌纹结构化特征（回退用）。"""
    side_label = "左手" if hand_side == "left" else "右手"
    raw = await vision_completion(
        prompts.palm_feature_system(),
        prompts.palm_feature_user(hand_side=side_label),
        image_data_url,
    )
    return _normalize_hand_features(
        extract_json(raw, error_label="掌纹特征"), hand_side
    )


async def extract_both_palm_features(
    left_url: str,
    right_url: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """一次视觉请求同时提取左右手特征，减少往返耗时。"""
    raw = await vision_completion_multi(
        prompts.palm_feature_system(),
        prompts.palm_feature_dual_user(),
        [left_url, right_url],
    )
    parsed = extract_json(raw, error_label="掌纹特征")

    if "left" in parsed and "right" in parsed:
        left = _normalize_hand_features(parsed["left"], "left")
        right = _normalize_hand_features(parsed["right"], "right")
        return left, right

    left = await extract_palm_features(left_url, "left")
    right = await extract_palm_features(right_url, "right")
    return left, right


def feature_summary(features: dict[str, Any]) -> str:
    summary = features.get("one_line_summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    shape = features.get("palm_shape", "未知掌形")
    quality = features.get("image_quality", "未知")
    return f"掌形{shape}，图像{quality}。"


def _parse_dual_palm_response(raw: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    parsed = extract_json(raw, error_label="掌纹解读")
    content = parsed.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("掌纹解读生成失败，请重试。")

    left_raw = parsed.get("left")
    right_raw = parsed.get("right")
    if not isinstance(left_raw, dict) or not isinstance(right_raw, dict):
        raise ValueError("掌纹特征解析失败，请重试。")

    return (
        content.strip(),
        _normalize_hand_features(left_raw, "left"),
        _normalize_hand_features(right_raw, "right"),
    )


async def analyze_palms(
    left_url: str,
    right_url: str,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """一次或两次模型调用完成掌纹解读，返回 (content, left_features, right_features)。"""
    if settings.vision_single_stage:
        raw = await vision_completion_multi(
            prompts.palm_analyze_system(),
            prompts.palm_analyze_dual_user(),
            [left_url, right_url],
            temperature=0.55,
        )
        return _parse_dual_palm_response(raw)

    left, right = await extract_both_palm_features(left_url, right_url)
    from services.deepseek_client import chat_completion

    user = prompts.palm_interpret_user(
        left_features=json.dumps(left, ensure_ascii=False, separators=(",", ":")),
        right_features=json.dumps(right, ensure_ascii=False, separators=(",", ":")),
    )
    content = await chat_completion(
        prompts.palm_interpret_system(),
        user,
        temperature=0.65,
        max_tokens=settings.interpret_max_tokens,
    )
    return content, left, right
