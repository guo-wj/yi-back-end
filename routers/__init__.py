from fastapi import APIRouter

from . import admin, almanac, auth, bazi, face, invite, liuyao, lottery, meihua, member, palm, payment, points, ziwei

api_router = APIRouter(prefix="/api")
api_router.include_router(admin.router, prefix="/admin", tags=["管理后台"])
api_router.include_router(auth.router, prefix="/auth", tags=["登录鉴权"])
api_router.include_router(invite.router, prefix="/invite", tags=["邀请"])
api_router.include_router(points.router, prefix="/points", tags=["积分"])
api_router.include_router(member.router, prefix="/member", tags=["会员"])
api_router.include_router(payment.router, prefix="/payment", tags=["支付"])
api_router.include_router(lottery.router, prefix="/lottery", tags=["今日灵签"])
api_router.include_router(almanac.router, prefix="/almanac", tags=["老黄历"])
api_router.include_router(liuyao.router, prefix="/liuyao", tags=["六爻"])
api_router.include_router(meihua.router, prefix="/meihua", tags=["梅花易数"])
api_router.include_router(ziwei.router, prefix="/ziwei", tags=["紫微斗数"])
api_router.include_router(bazi.router, prefix="/bazi", tags=["八字"])
api_router.include_router(palm.router, prefix="/palm", tags=["掌纹解析"])
api_router.include_router(face.router, prefix="/face", tags=["面相解析"])

__all__ = ["api_router"]
