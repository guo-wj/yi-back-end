from fastapi import APIRouter

from . import almanac, auth, bazi, face, liuyao, lottery, meihua, palm, ziwei

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router, prefix="/auth", tags=["登录鉴权"])
api_router.include_router(lottery.router, prefix="/lottery", tags=["今日灵签"])
api_router.include_router(almanac.router, prefix="/almanac", tags=["老黄历"])
api_router.include_router(liuyao.router, prefix="/liuyao", tags=["六爻"])
api_router.include_router(meihua.router, prefix="/meihua", tags=["梅花易数"])
api_router.include_router(ziwei.router, prefix="/ziwei", tags=["紫微斗数"])
api_router.include_router(bazi.router, prefix="/bazi", tags=["八字"])
api_router.include_router(palm.router, prefix="/palm", tags=["掌纹解析"])
api_router.include_router(face.router, prefix="/face", tags=["面相解析"])

__all__ = ["api_router"]
