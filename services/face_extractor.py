"""面相图片解码与智谱视觉特征提取。"""

import json
from typing import Any, Literal

from config import settings
from services import prompts
from services.image_utils import extract_json
from services.vision_client import vision_completion, vision_completion_multi

FaceSlot = Literal["front", "side", "extra"]
SLOT_LABELS: dict[FaceSlot, str] = {
    "front": "正面照",
    "side": "侧面照",
    "extra": "补充角度",
}
SLOT_ORDER: tuple[FaceSlot, ...] = ("front", "side", "extra")


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


def _parse_face_analyze_response(raw: str) -> tuple[str, dict[str, Any]]:
    parsed = extract_json(raw, error_label="面相解读")
    content = parsed.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("面相解读生成失败，请重试。")
    return content.strip(), parsed


async def analyze_face(
    image_urls: list[str],
    slots: list[FaceSlot] | None = None,
) -> tuple[str, dict[str, Any]]:
    """一次或两次模型调用完成面相解读，返回 (content, features)。"""
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
        return _parse_face_analyze_response(raw)

    features = await extract_face_features(image_urls, slots=effective_slots)
    from services.deepseek_client import chat_completion

    user = prompts.face_interpret_user(
        features=json.dumps(features, ensure_ascii=False, separators=(",", ":")),
    )
    content = await chat_completion(
        prompts.face_interpret_system(),
        user,
        temperature=0.65,
        max_tokens=settings.interpret_max_tokens,
    )
    return content, features
