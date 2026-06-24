import asyncio
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator, model_validator

from services.face_extractor import (
    analyze_face,
    feature_summary,
    per_image_summaries,
)
from services.image_utils import normalize_image_data_url_async

router = APIRouter()

FaceSlot = Literal["front", "side", "extra"]


class FaceAnalyzeRequest(BaseModel):
    """1～3 张面部照片，支持正面/侧面/补充任意组合。"""

    faces: list[str] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="面部照片 data URL 或 base64",
    )
    slots: list[FaceSlot] | None = Field(
        default=None,
        description="与 faces 一一对应：front=正面照 side=侧面照 extra=补充角度",
    )

    @field_validator("faces")
    @classmethod
    def _strip_faces(cls, values: list[str]) -> list[str]:
        cleaned = [v.strip() for v in values if v and v.strip()]
        if not cleaned:
            raise ValueError("请至少上传一张面部图片。")
        if len(cleaned) > 3:
            raise ValueError("最多上传 3 张面部图片。")
        return cleaned

    @model_validator(mode="after")
    def _check_slots(self) -> "FaceAnalyzeRequest":
        if self.slots is not None and len(self.slots) != len(self.faces):
            raise ValueError("slots 与 faces 数量须一致。")
        return self


class FaceAnalyzeResponse(BaseModel):
    content: str = Field(..., description="面相解读正文（Markdown）")
    summary: str | None = Field(default=None, description="综合一行摘要")
    summaries: list[str] | None = Field(default=None, description="各张照片一行摘要")


def _ensure_face_detected(features: dict) -> None:
    if features.get("face_detected") is False:
        raise ValueError("正面照未识别到清晰正脸，请在自然光下正对镜头、五官无遮挡后重拍。")


@router.post("/analyze", response_model=FaceAnalyzeResponse)
async def analyze_face_route(body: FaceAnalyzeRequest) -> FaceAnalyzeResponse:
    """接收 1～3 张面部照片（正面/侧面/补充），提取特征后由模型给出解读。"""
    image_urls = await asyncio.gather(
        *(normalize_image_data_url_async(raw) for raw in body.faces)
    )

    content, features = await analyze_face(list(image_urls), slots=body.slots)
    _ensure_face_detected(features)

    summaries = per_image_summaries(features)
    return FaceAnalyzeResponse(
        content=content,
        summary=feature_summary(features),
        summaries=summaries or None,
    )
