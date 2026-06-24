import asyncio

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.image_utils import normalize_image_data_url_async
from services.palm_extractor import analyze_palms, feature_summary

router = APIRouter()


class PalmAnalyzeRequest(BaseModel):
    left_palm: str = Field(..., min_length=1, description="左手掌图 data URL 或 base64")
    right_palm: str = Field(..., min_length=1, description="右手掌图 data URL 或 base64")


class PalmAnalyzeResponse(BaseModel):
    content: str = Field(..., description="掌纹解读正文（Markdown）")
    left_summary: str | None = Field(default=None, description="左手一行摘要")
    right_summary: str | None = Field(default=None, description="右手一行摘要")


def _ensure_hand_detected(features: dict, label: str) -> None:
    if features.get("hand_detected") is False:
        raise ValueError(f"{label}未识别到清晰手掌，请在自然光下平展手掌后重拍。")


@router.post("/analyze", response_model=PalmAnalyzeResponse)
async def analyze_palm(body: PalmAnalyzeRequest) -> PalmAnalyzeResponse:
    """接收左右掌纹图片，提取特征后由模型给出解读。"""
    left_url, right_url = await asyncio.gather(
        normalize_image_data_url_async(body.left_palm),
        normalize_image_data_url_async(body.right_palm),
    )

    content, left_features, right_features = await analyze_palms(left_url, right_url)
    _ensure_hand_detected(left_features, "左手")
    _ensure_hand_detected(right_features, "右手")

    return PalmAnalyzeResponse(
        content=content,
        left_summary=feature_summary(left_features),
        right_summary=feature_summary(right_features),
    )
