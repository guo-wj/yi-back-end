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
FaceStopKey = Literal["upper", "middle", "lower"]
FaceOrganKey = Literal["brow", "eye", "nose", "mouth", "ear"]


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


class FaceStopDetail(BaseModel):
    key: FaceStopKey = Field(..., description="upper=上停 middle=中停 lower=下停")
    name_cn: str = Field(..., description="停名，如 上停")
    region: str = Field(..., description="部位与主运，如 发际至眉 · 主早年")
    attribute: str = Field(..., description="2-4 字特征词，如 丰隆、挺正、温厚")
    score: int = Field(..., ge=1, le=5, description="形质参考分 1-5")
    description: str = Field(..., description="该停文化解读正文")


class FaceOrganDetail(BaseModel):
    key: FaceOrganKey = Field(
        ...,
        description="brow=眉 eye=眼 nose=鼻 mouth=口 ear=耳",
    )
    name_cn: str = Field(..., description="官名，如 眉")
    icon_text: str = Field(..., description="图标单字：眉眼鼻口耳")
    office: str = Field(..., description="传统官名，如 保寿官")
    keywords: list[str] = Field(..., min_length=2, max_length=2, description="两个主题词")
    status: str = Field(..., description="旺|盛|匀|平|弱")
    description: str = Field(..., description="该官文化解读正文")


class FaceAnalyzeResponse(BaseModel):
    content: str = Field(..., description="面相解读正文（Markdown，兼容旧版）")
    face_type: str = Field(..., description="五行面型，如 木形面")
    complexion: str = Field(..., description="气色，如 明润")
    overview: str = Field(..., description="面相综述")
    stops: list[FaceStopDetail] = Field(..., description="三停结构化解读")
    organs: list[FaceOrganDetail] = Field(..., description="五官结构化解读")
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

    structured, features = await analyze_face(list(image_urls), slots=body.slots)
    _ensure_face_detected(features)

    summaries = per_image_summaries(features)
    return FaceAnalyzeResponse(
        **structured,
        summary=feature_summary(features),
        summaries=summaries or None,
    )
