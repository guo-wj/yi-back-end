"""图片 base64 解码与压缩（掌纹、面相等视觉功能共用）。"""

import asyncio
import base64
import json
import re
from io import BytesIO
from typing import Any

from config import settings

try:
    from PIL import Image

    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

_DATA_URL_RE = re.compile(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$", re.DOTALL)


def decode_image_bytes(raw: str) -> bytes:
    text = raw.strip()
    if not text:
        raise ValueError("图片数据为空。")

    b64_part = text
    match = _DATA_URL_RE.match(text)
    if match:
        b64_part = match.group(2)

    try:
        data = base64.b64decode(b64_part, validate=True)
    except Exception as exc:
        raise ValueError("图片 base64 解码失败，请重新上传。") from exc

    if len(data) > settings.palm_max_image_bytes:
        limit_mb = settings.palm_max_image_bytes // (1024 * 1024)
        raise ValueError(f"图片过大，请压缩后重试（上限约 {limit_mb}MB）。")

    if not data:
        raise ValueError("图片数据无效。")
    return data


def compress_image_bytes(data: bytes) -> str:
    """缩放并压缩为 JPEG data URL；无 Pillow 时原样返回。"""
    if not _HAS_PIL:
        encoded = base64.b64encode(data).decode("ascii")
        mime = "image/jpeg"
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            mime = "image/png"
        return f"data:{mime};base64,{encoded}"

    img = Image.open(BytesIO(data))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    elif img.mode == "L":
        img = img.convert("RGB")

    max_side = settings.palm_image_max_side
    w, h = img.size
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.BILINEAR)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=settings.palm_jpeg_quality, optimize=True)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def normalize_image_data_url(raw: str) -> str:
    return compress_image_bytes(decode_image_bytes(raw))


async def normalize_image_data_url_async(raw: str) -> str:
    data = decode_image_bytes(raw)
    return await asyncio.to_thread(compress_image_bytes, data)


def extract_json(text: str, *, error_label: str = "特征") -> dict[str, Any]:
    """从模型回复中解析 JSON 对象。"""
    stripped = text.strip()
    if not stripped:
        raise ValueError(f"{error_label}解析失败，未返回有效内容，请重试。")

    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)

    if not stripped.startswith("{"):
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            stripped = stripped[start : end + 1]

    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{error_label}解析失败，请换一张更清晰的照片重试。") from exc

    if not isinstance(obj, dict):
        raise ValueError(f"{error_label}格式异常，请重新上传。")
    return obj
