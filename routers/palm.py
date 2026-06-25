import asyncio
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.image_utils import normalize_image_data_url_async
from services.palm_extractor import (
    analyze_palms,
    extract_palms,
    feature_summary,
    interpret_palm_features,
)

router = APIRouter()

PalmLineKey = Literal["life", "head", "heart"]
PalmMountKey = Literal["venus", "jupiter", "saturn", "apollo", "mercury"]
PrimaryHand = Literal["left", "right"]


class PalmImagesRequest(BaseModel):
    left_palm: str = Field(..., min_length=1, description="左手掌图 data URL 或 base64")
    right_palm: str = Field(..., min_length=1, description="右手掌图 data URL 或 base64")


class PalmLineDetail(BaseModel):
    key: PalmLineKey = Field(..., description="life=生命线 head=智慧线 heart=感情线")
    name_cn: str = Field(..., description="中文线名")
    name_en: str = Field(..., description="英文线名")
    attribute: str = Field(..., description="2-4 字特征词，如深长、清晰、柔缓")
    score: int = Field(..., ge=1, le=5, description="形质参考分 1-5")
    description: str = Field(..., description="该线文化解读正文")


class PalmMountDetail(BaseModel):
    key: PalmMountKey = Field(
        ...,
        description="venus=金星丘 jupiter=木星丘 saturn=土星丘 apollo=太阳丘 mercury=水星丘",
    )
    name_cn: str = Field(..., description="丘名，如 金星丘")
    icon_text: str = Field(..., description="图标单字：金木土日水")
    keywords: list[str] = Field(..., min_length=2, max_length=2, description="两个主题词")
    status: str = Field(..., description="旺|盛|匀|平|弱")
    description: str = Field(..., description="该丘文化解读正文")


class PalmStructuredBody(BaseModel):
    content: str = Field(..., description="完整解读正文（Markdown）")
    palm_type: str = Field(..., description="五行掌形，如 水形掌")
    complexion: str = Field(..., description="掌色气色，如 红润")
    primary_hand: PrimaryHand = Field(..., description="主看之手：left 或 right")
    overview: str = Field(..., description="掌象综述")
    lines: list[PalmLineDetail] = Field(..., description="三大主线结构化解读")
    mounts: list[PalmMountDetail] = Field(..., description="五丘结构化解读")


class PalmExtractResponse(BaseModel):
    """特征提取结果：先返回，供前端渲染头部标签与加载态。"""

    left_features: dict[str, Any] = Field(..., description="左手结构化特征（供 /interpret 回传）")
    right_features: dict[str, Any] = Field(..., description="右手结构化特征（供 /interpret 回传）")
    left_summary: str = Field(..., description="左手一行摘要")
    right_summary: str = Field(..., description="右手一行摘要")
    palm_type: str = Field(..., description="主看之手掌形")
    complexion: str = Field(..., description="主看之手气色")
    primary_hand: PrimaryHand = Field(default="right", description="主看之手")


class PalmInterpretRequest(BaseModel):
    left_features: dict[str, Any] = Field(..., description="/extract 返回的 left_features")
    right_features: dict[str, Any] = Field(..., description="/extract 返回的 right_features")
    primary_hand: PrimaryHand | None = Field(default=None, description="可选，默认 right")


class PalmAnalyzeResponse(PalmStructuredBody):
    left_summary: str | None = Field(default=None, description="左手一行摘要")
    right_summary: str | None = Field(default=None, description="右手一行摘要")


def _ensure_hand_detected(features: dict, label: str) -> None:
    if features.get("hand_detected") is False:
        raise ValueError(f"{label}未识别到清晰手掌，请在自然光下平展手掌后重拍。")


async def _normalize_palm_images(body: PalmImagesRequest) -> tuple[str, str]:
    return await asyncio.gather(
        normalize_image_data_url_async(body.left_palm),
        normalize_image_data_url_async(body.right_palm),
    )


@router.post("/extract", response_model=PalmExtractResponse)
async def extract_palm(body: PalmImagesRequest) -> PalmExtractResponse:
    """并行提取左右掌纹特征（约 5–10s）。前端可先展示掌型/气色，再调 /interpret。"""
    left_url, right_url = await _normalize_palm_images(body)
    result = await extract_palms(left_url, right_url)
    _ensure_hand_detected(result["left_features"], "左手")
    _ensure_hand_detected(result["right_features"], "右手")
    return PalmExtractResponse(**result)


@router.post("/interpret", response_model=PalmStructuredBody)
async def interpret_palm(body: PalmInterpretRequest) -> PalmStructuredBody:
    """基于 /extract 的特征生成三线五丘解读（约 3–6s，纯文本模型）。"""
    _ensure_hand_detected(body.left_features, "左手")
    _ensure_hand_detected(body.right_features, "右手")
    structured = await interpret_palm_features(
        body.left_features,
        body.right_features,
        primary_hand=body.primary_hand,
    )
    return PalmStructuredBody(**structured)


@router.post("/analyze", response_model=PalmAnalyzeResponse)
async def analyze_palm(body: PalmImagesRequest) -> PalmAnalyzeResponse:
    """一次性完整解读（兼容旧版）。推荐前端改用 /extract + /interpret 分段加载。"""
    left_url, right_url = await _normalize_palm_images(body)
    structured, left_features, right_features = await analyze_palms(left_url, right_url)
    _ensure_hand_detected(left_features, "左手")
    _ensure_hand_detected(right_features, "右手")

    return PalmAnalyzeResponse(
        **structured,
        left_summary=feature_summary(left_features),
        right_summary=feature_summary(right_features),
    )
