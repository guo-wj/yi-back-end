"""积分业务：定价、扣减、退还、签到、注册/邀请奖励、会员折扣。"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
from datetime import date, datetime, timedelta, timezone

from config import settings
from services import points_db

# 注册与邀请
REGISTER_BONUS = 100
INVITEE_BONUS = 30
INVITER_BONUS = 50
INVITER_MONTHLY_CAP = 500

# 签到 7 日循环
CHECKIN_REWARDS = [5, 5, 8, 8, 10, 10, 20]

INTERPRET_FEATURES = ("qian", "liuyao", "meihua", "bazi", "palm", "face")
EXTRACT_FEATURES = ("palm", "face")

MEMBER_TIERS: dict[str, dict] = {
    "none": {
        "label": "普通用户",
        "discount": 1.0,
        "monthly_points": 0,
        "price_cents": 0,
        "qian_free_daily": 1,
        "liuyao_free_daily": 0,
        "meihua_free_daily": 0,
        "bazi_free_daily": 0,
        "palm_free_daily": 0,
        "face_free_daily": 0,
        "palm_extract_daily": 10,
        "face_extract_daily": 10,
    },
    "yiyou": {
        "label": "易友",
        "discount": 0.9,
        "monthly_points": 200,
        "price_cents": 1800,
        "qian_free_daily": 2,
        "liuyao_free_daily": 1,
        "meihua_free_daily": 1,
        "bazi_free_daily": 0,
        "palm_free_daily": 1,
        "face_free_daily": 1,
        "palm_extract_daily": 10,
        "face_extract_daily": 10,
    },
    "yishi": {
        "label": "易师",
        "discount": 0.8,
        "monthly_points": 500,
        "price_cents": 3800,
        "qian_free_daily": 3,
        "liuyao_free_daily": 2,
        "meihua_free_daily": 2,
        "bazi_free_daily": 1,
        "palm_free_daily": 2,
        "face_free_daily": 2,
        "palm_extract_daily": 10,
        "face_extract_daily": 10,
    },
    "yizun": {
        "label": "易尊",
        "discount": 0.7,
        "monthly_points": 1000,
        "price_cents": 6800,
        "qian_free_daily": 5,
        "liuyao_free_daily": 3,
        "meihua_free_daily": 3,
        "bazi_free_daily": 2,
        "palm_free_daily": 3,
        "face_free_daily": 3,
        "palm_extract_daily": 10,
        "face_extract_daily": 10,
    },
}

QIAN_DRAW_DAILY_LIMIT = 10
# 解签免费额度单独计数，与旧版「摇签扣点」的 qian 记录隔离
QIAN_INTERPRET_QUOTA_FEATURE = "qian_interpret"


def _interpret_quota_feature(feature: str) -> str:
    if feature == "qian":
        return QIAN_INTERPRET_QUOTA_FEATURE
    return f"{feature}_interpret"


def _free_daily_for_feature(tier: str, feature: str) -> int:
    key = f"{feature}_free_daily"
    return int(MEMBER_TIERS.get(tier, MEMBER_TIERS["none"]).get(key, 0))


def _extract_daily_limit(tier: str, feature: str) -> int:
    if feature == "palm":
        return settings.palm_extract_daily
    if feature == "face":
        return settings.face_extract_daily
    key = f"{feature}_extract_daily"
    return int(MEMBER_TIERS.get(tier, MEMBER_TIERS["none"]).get(key, 3))


async def check_and_record_draw(user_id: int) -> None:
    """摇签软限流：每日 QIAN_DRAW_DAILY_LIMIT 次。"""
    quota = await asyncio.to_thread(points_db.get_daily_quota, user_id, "qian_draw")
    used = int(quota.get("used_count") or 0)
    if used >= QIAN_DRAW_DAILY_LIMIT:
        raise ValueError("今日摇签次数已达上限，明日再来。")
    await asyncio.to_thread(points_db.increment_daily_quota, user_id, "qian_draw")


async def check_and_record_extract(user_id: int, feature: str) -> None:
    """掌纹/面相识别软限流。"""
    if feature not in EXTRACT_FEATURES:
        raise ValueError(f"未知识别功能：{feature}")
    bal = await get_balance(user_id)
    tier = bal["member_tier"]
    limit = _extract_daily_limit(tier, feature)
    quota_key = f"{feature}_extract"
    quota = await asyncio.to_thread(points_db.get_daily_quota, user_id, quota_key)
    used = int(quota.get("used_count") or 0)
    if used >= limit:
        raise ValueError("今日识别次数已达上限，明日再来。")
    await asyncio.to_thread(points_db.increment_daily_quota, user_id, quota_key)


RECHARGE_PACKAGES = [
    {"id": "pack_6", "label": "体验包", "price_cents": 600, "points": 60, "bonus_pct": 0},
    {"id": "pack_30", "label": "常用包", "price_cents": 3000, "points": 350, "bonus_pct": 17},
    {"id": "pack_98", "label": "进阶包", "price_cents": 9800, "points": 1200, "bonus_pct": 22},
    {"id": "pack_198", "label": "尊享包", "price_cents": 19800, "points": 2600, "bonus_pct": 31},
]


class InsufficientPointsError(Exception):
    def __init__(self, required: int, balance: int):
        self.required = required
        self.balance = balance
        super().__init__(f"积分不足，需要 {required} 点，当前 {balance} 点。")


def _gen_referral_code(user_id: int) -> str:
    suffix = secrets.token_hex(2).upper()
    return f"YI{user_id:04d}{suffix}"


def _effective_member_tier(record: dict) -> str:
    tier = record.get("member_tier") or "none"
    if tier == "none":
        return "none"
    expire = record.get("member_expire_at")
    if not expire:
        return tier
    try:
        exp = datetime.fromisoformat(expire)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            return "none"
    except ValueError:
        return "none"
    return tier


def _member_discount(tier: str) -> float:
    return float(MEMBER_TIERS.get(tier, MEMBER_TIERS["none"])["discount"])


def compute_bazi_cost(focus_count: int, is_redo: bool = False) -> int:
    base = 40
    extra = min(max(0, focus_count - 1), 3) * 5
    total = base + extra
    if is_redo:
        total = max(20, total // 2)
    return total


def compute_cost(
    feature: str,
    *,
    focus_count: int = 1,
    is_redo: bool = False,
    member_tier: str = "none",
    use_free_quota: bool = False,
) -> tuple[int, int, bool]:
    """返回 (原价, 实付, 是否使用免费额度)。"""
    if feature == "bazi":
        base = compute_bazi_cost(focus_count, is_redo)
    else:
        rule = points_db.get_pricing(feature)
        if not rule:
            raise ValueError(f"未知功能：{feature}")
        base = int(rule["base_cost"])

    if use_free_quota and feature in INTERPRET_FEATURES:
        return base, 0, True

    discount = _member_discount(member_tier)
    paid = max(0, int(base * discount))
    return base, paid, False


async def setup_new_user(user_id: int, invite_code: str | None = None) -> dict:
    """新用户初始化账户、注册礼、邀请奖励。"""
    code = _gen_referral_code(user_id)
    record = await asyncio.to_thread(points_db.ensure_user_points, user_id, code)

    await grant_points(
        user_id,
        REGISTER_BONUS,
        note="新用户注册礼",
        tx_type="grant",
        feature="register",
    )

    if invite_code and invite_code.strip():
        await _process_invite(user_id, invite_code.strip())

    return await get_balance(user_id)


async def _process_invite(invitee_id: int, invite_code: str) -> None:
    inviter = await asyncio.to_thread(points_db.get_user_by_referral_code, invite_code.upper())
    if not inviter or inviter["user_id"] == invitee_id:
        return

    inviter_id = int(inviter["user_id"])
    await asyncio.to_thread(points_db.create_invite_record, inviter_id, invitee_id)

    await grant_points(
        invitee_id,
        INVITEE_BONUS,
        note="填写邀请码奖励",
        tx_type="grant",
        feature="invite",
        ref_id=str(inviter_id),
    )
    await asyncio.to_thread(points_db.mark_invitee_granted, invitee_id)

    monthly = await asyncio.to_thread(points_db.count_inviter_grants_this_month, inviter_id)
    if monthly * INVITER_BONUS < INVITER_MONTHLY_CAP:
        await grant_points(
            inviter_id,
            INVITER_BONUS,
            note="邀请好友奖励",
            tx_type="grant",
            feature="invite",
            ref_id=str(invitee_id),
        )
        await asyncio.to_thread(points_db.mark_inviter_granted, invitee_id)


async def grant_points(
    user_id: int,
    amount: int,
    *,
    note: str,
    tx_type: str = "grant",
    feature: str | None = None,
    ref_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    if amount <= 0:
        raise ValueError("赠送积分须为正数。")

    if idempotency_key:
        existing = await asyncio.to_thread(
            points_db.get_transaction_by_idempotency, idempotency_key
        )
        if existing:
            bal = await get_balance(user_id)
            return {"transaction_id": existing["id"], "balance": bal["balance"], "duplicate": True}

    await asyncio.to_thread(points_db.ensure_user_points, user_id)
    balance_after = await asyncio.to_thread(points_db.update_balance, user_id, amount)
    tx_id = await asyncio.to_thread(
        points_db.insert_transaction,
        user_id=user_id,
        tx_type=tx_type,
        amount=amount,
        balance_after=balance_after,
        feature=feature,
        ref_id=ref_id,
        idempotency_key=idempotency_key,
        note=note,
    )
    return {"transaction_id": tx_id, "balance": balance_after}


async def _maybe_grant_member_monthly(user_id: int, tier: str) -> None:
    """有效会员每月首次访问 balance 时发放月赠积分。"""
    if tier == "none":
        return
    month = date.today().strftime("%Y-%m")
    granted = await asyncio.to_thread(points_db.get_member_grant_month, user_id)
    if granted == month:
        return
    monthly = int(MEMBER_TIERS[tier]["monthly_points"])
    if monthly <= 0:
        return
    await grant_points(
        user_id,
        monthly,
        note=f"{MEMBER_TIERS[tier]['label']} 月赠积分",
        tx_type="grant",
        feature="member",
        idempotency_key=f"member_monthly:{user_id}:{month}",
    )
    await asyncio.to_thread(points_db.set_member_grant_month, user_id, month)


async def get_balance(user_id: int) -> dict:
    record = await asyncio.to_thread(points_db.ensure_user_points, user_id)
    tier = _effective_member_tier(record)
    if tier != record.get("member_tier"):
        await asyncio.to_thread(points_db.set_member, user_id, "none", None)
        record["member_tier"] = "none"
        record["member_expire_at"] = None
        tier = "none"

    if tier != "none":
        await _maybe_grant_member_monthly(user_id, tier)

    record = await asyncio.to_thread(points_db.get_user_points, user_id) or record
    discount = _member_discount(tier)
    return {
        "balance": int(record["balance"]),
        "member_tier": tier,
        "member_label": MEMBER_TIERS.get(tier, MEMBER_TIERS["none"])["label"],
        "member_discount": discount,
        "member_expire_at": record.get("member_expire_at"),
        "referral_code": record.get("referral_code"),
        "checkin_streak": int(record.get("checkin_streak") or 0),
        "last_checkin_date": record.get("last_checkin_date"),
    }


async def get_quota(user_id: int, feature: str) -> dict:
    bal = await get_balance(user_id)
    tier = bal["member_tier"]
    free_daily = _free_daily_for_feature(tier, feature) if feature in INTERPRET_FEATURES else 0

    quota_key = _interpret_quota_feature(feature) if feature in INTERPRET_FEATURES else feature
    quota = await asyncio.to_thread(points_db.get_daily_quota, user_id, quota_key)
    used = int(quota.get("used_count") or 0)
    remaining = max(0, free_daily - used)

    tomorrow = date.today() + timedelta(days=1)
    reset_at = datetime.combine(tomorrow, datetime.min.time(), tzinfo=timezone.utc).isoformat()

    return {
        "feature": feature,
        "free_daily": free_daily,
        "free_remaining": remaining,
        "used_today": used,
        "reset_at": reset_at,
    }


async def quote_consume(
    user_id: int,
    feature: str,
    *,
    focus_count: int = 1,
    is_redo: bool = False,
) -> dict:
    bal = await get_balance(user_id)
    tier = bal["member_tier"]

    quota = await get_quota(user_id, feature) if feature in INTERPRET_FEATURES else None
    use_free = bool(quota and quota["free_remaining"] > 0)

    base, paid, free_used = compute_cost(
        feature,
        focus_count=focus_count,
        is_redo=is_redo,
        member_tier=tier,
        use_free_quota=use_free,
    )

    return {
        "feature": feature,
        "base_cost": base,
        "cost": paid,
        "member_discount": bal["member_discount"],
        "uses_free_quota": free_used,
        "balance": bal["balance"],
        "sufficient": bal["balance"] >= paid,
    }


async def consume_points(
    user_id: int,
    feature: str,
    *,
    focus_count: int = 1,
    is_redo: bool = False,
    idempotency_key: str | None = None,
    meta: dict | None = None,
) -> dict:
    if idempotency_key:
        existing = await asyncio.to_thread(
            points_db.get_transaction_by_idempotency, idempotency_key
        )
        if existing and existing["type"] == "consume":
            bal = await get_balance(user_id)
            return {
                "transaction_id": existing["id"],
                "balance": bal["balance"],
                "cost": abs(int(existing["amount"])),
                "duplicate": True,
            }

    quote = await quote_consume(
        user_id, feature, focus_count=focus_count, is_redo=is_redo
    )
    paid = quote["cost"]

    if paid > 0 and quote["balance"] < paid:
        raise InsufficientPointsError(paid, quote["balance"])

    await asyncio.to_thread(points_db.ensure_user_points, user_id)

    if quote["uses_free_quota"]:
        quota_key = _interpret_quota_feature(feature)
        await asyncio.to_thread(points_db.increment_daily_quota, user_id, quota_key)
        tx_id = await asyncio.to_thread(
            points_db.insert_transaction,
            user_id=user_id,
            tx_type="consume",
            amount=0,
            balance_after=quote["balance"],
            feature=feature,
            ref_id=None,
            idempotency_key=idempotency_key,
            note=_free_quota_note(feature),
        )
        return {
            "transaction_id": tx_id,
            "balance": quote["balance"],
            "cost": 0,
            "uses_free_quota": True,
        }

    balance_after = await asyncio.to_thread(points_db.update_balance, user_id, -paid)
    tx_id = await asyncio.to_thread(
        points_db.insert_transaction,
        user_id=user_id,
        tx_type="consume",
        amount=-paid,
        balance_after=balance_after,
        feature=feature,
        ref_id=None,
        idempotency_key=idempotency_key,
        note=_consume_note(feature, meta),
    )
    return {
        "transaction_id": tx_id,
        "balance": balance_after,
        "cost": paid,
        "uses_free_quota": False,
    }


def _free_quota_note(feature: str) -> str:
    labels = {
        "qian": "解签",
        "liuyao": "解卦",
        "meihua": "解卦",
        "bazi": "断语",
        "palm": "解读",
        "face": "解读",
    }
    action = labels.get(feature, "解读")
    return f"使用每日免费{action}额度"


def _consume_note(feature: str, meta: dict | None) -> str:
    rule = points_db.get_pricing(feature)
    label = rule["label"] if rule else feature
    if feature == "bazi" and meta:
        fc = meta.get("focus_count")
        if fc:
            return f"{label}（关注 {fc} 项）"
    action = {
        "qian": "解签",
        "liuyao": "解卦",
        "meihua": "解卦",
        "bazi": "断语",
    }.get(feature, "AI 解读")
    return f"{label} {action}"


async def refund_points(transaction_id: int, *, note: str = "解读失败，积分已退回") -> dict:
    tx = await asyncio.to_thread(points_db.get_transaction_by_id, transaction_id)
    if not tx:
        raise ValueError("流水不存在。")
    if tx["type"] != "consume":
        raise ValueError("仅可退还消费流水。")

    refund_key = f"refund:{transaction_id}"
    existing = await asyncio.to_thread(points_db.get_transaction_by_idempotency, refund_key)
    if existing:
        bal = await get_balance(int(tx["user_id"]))
        return {"transaction_id": existing["id"], "balance": bal["balance"], "duplicate": True}

    amount = abs(int(tx["amount"]))
    if amount == 0:
        bal = await get_balance(int(tx["user_id"]))
        return {"transaction_id": tx["id"], "balance": bal["balance"], "refunded": 0}

    user_id = int(tx["user_id"])
    balance_after = await asyncio.to_thread(points_db.update_balance, user_id, amount)
    refund_id = await asyncio.to_thread(
        points_db.insert_transaction,
        user_id=user_id,
        tx_type="refund",
        amount=amount,
        balance_after=balance_after,
        feature=tx.get("feature"),
        ref_id=str(transaction_id),
        idempotency_key=refund_key,
        note=note,
    )
    return {"transaction_id": refund_id, "balance": balance_after, "refunded": amount}


async def checkin(user_id: int) -> dict:
    record = await asyncio.to_thread(points_db.ensure_user_points, user_id)
    today = date.today().isoformat()
    last = record.get("last_checkin_date")

    if last == today:
        raise ValueError("今日已签到。")

    streak = int(record.get("checkin_streak") or 0)
    if last:
        try:
            last_date = date.fromisoformat(last)
            if (date.today() - last_date).days == 1:
                streak += 1
            else:
                streak = 1
        except ValueError:
            streak = 1
    else:
        streak = 1

    idx = (streak - 1) % len(CHECKIN_REWARDS)
    reward = CHECKIN_REWARDS[idx]

    await asyncio.to_thread(points_db.update_checkin, user_id, streak, today)
    result = await grant_points(
        user_id,
        reward,
        note=f"每日签到（连续 {streak} 天）",
        tx_type="grant",
        feature="checkin",
        idempotency_key=f"checkin:{user_id}:{today}",
    )
    result["streak"] = streak
    result["reward"] = reward
    return result


async def list_ledger(user_id: int, page: int = 1, page_size: int = 20) -> dict:
    items, total = await asyncio.to_thread(
        points_db.list_transactions, user_id, page, page_size
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def make_idempotency_key(user_id: int, feature: str, payload: str) -> str:
    digest = hashlib.sha256(f"{user_id}:{feature}:{payload}".encode()).hexdigest()[:24]
    return f"{feature}:{user_id}:{digest}"


async def create_recharge_order(user_id: int, product_id: str) -> dict:
    pkg = next((p for p in RECHARGE_PACKAGES if p["id"] == product_id), None)
    if not pkg:
        raise ValueError("充值档位不存在。")
    order_id = await asyncio.to_thread(
        points_db.create_payment_order,
        user_id,
        "recharge",
        product_id,
        pkg["price_cents"],
        pkg["points"],
    )
    return {"order_id": order_id, "product": pkg, "status": "pending"}


async def create_member_order(user_id: int, tier: str) -> dict:
    if tier not in MEMBER_TIERS or tier == "none":
        raise ValueError("会员档位不存在。")
    plan = MEMBER_TIERS[tier]
    order_id = await asyncio.to_thread(
        points_db.create_payment_order,
        user_id,
        "member",
        tier,
        plan["price_cents"],
        plan["monthly_points"],
    )
    return {"order_id": order_id, "tier": tier, "plan": plan, "status": "pending"}


async def confirm_payment(order_id: int, user_id: int) -> dict:
    """模拟支付成功（开发/MVP）；生产环境由支付回调触发。"""
    order = await asyncio.to_thread(points_db.get_payment_order, order_id)
    if not order or order["user_id"] != user_id:
        raise ValueError("订单不存在。")
    if order["status"] == "paid":
        return {"order_id": order_id, "status": "paid", "duplicate": True}

    completed = await asyncio.to_thread(
        points_db.complete_payment_order, order_id, f"mock_{order_id}"
    )
    if not completed:
        raise ValueError("订单状态异常。")

    if completed["order_type"] == "recharge":
        await grant_points(
            user_id,
            int(completed["points"]),
            note="积分充值",
            tx_type="grant",
            feature="recharge",
            ref_id=str(order_id),
            idempotency_key=f"pay:{order_id}",
        )
    elif completed["order_type"] == "member":
        tier = completed["product_id"]
        expire = datetime.now(timezone.utc) + timedelta(days=30)
        await asyncio.to_thread(
            points_db.set_member, user_id, tier, expire.isoformat()
        )
        await asyncio.to_thread(
            points_db.set_member_grant_month, user_id, date.today().strftime("%Y-%m")
        )
        monthly = int(MEMBER_TIERS[tier]["monthly_points"])
        if monthly > 0:
            await grant_points(
                user_id,
                monthly,
                note=f"{MEMBER_TIERS[tier]['label']} 开通月赠积分",
                tx_type="grant",
                feature="member",
                ref_id=str(order_id),
                idempotency_key=f"member_grant:{order_id}",
            )

    bal = await get_balance(user_id)
    return {"order_id": order_id, "status": "paid", "balance": bal["balance"]}
