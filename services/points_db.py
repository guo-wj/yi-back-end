"""积分账户、流水、配额、定价与签到（SQLite）。"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone

from config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_points (
    user_id            INTEGER PRIMARY KEY,
    balance            INTEGER NOT NULL DEFAULT 0,
    member_tier        TEXT NOT NULL DEFAULT 'none',
    member_expire_at   TEXT,
    member_grant_month TEXT,
    checkin_streak     INTEGER NOT NULL DEFAULT 0,
    last_checkin_date  TEXT,
    referral_code      TEXT UNIQUE,
    updated_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS point_transactions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    type           TEXT NOT NULL,
    amount         INTEGER NOT NULL,
    feature        TEXT,
    ref_id         TEXT,
    idempotency_key TEXT UNIQUE,
    balance_after  INTEGER NOT NULL,
    note           TEXT,
    created_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pt_user_created ON point_transactions(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS daily_quotas (
    user_id     INTEGER NOT NULL,
    feature     TEXT NOT NULL,
    quota_date  TEXT NOT NULL,
    used_count  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, feature, quota_date)
);

CREATE TABLE IF NOT EXISTS pricing_rules (
    feature              TEXT PRIMARY KEY,
    base_cost            INTEGER NOT NULL,
    member_discountable  INTEGER NOT NULL DEFAULT 1,
    label                TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS invite_rewards (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    inviter_id      INTEGER NOT NULL,
    invitee_id      INTEGER NOT NULL UNIQUE,
    inviter_granted INTEGER NOT NULL DEFAULT 0,
    invitee_granted INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payment_orders (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    order_type    TEXT NOT NULL,
    product_id    TEXT NOT NULL,
    amount_cents  INTEGER NOT NULL,
    points        INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'pending',
    external_id   TEXT,
    created_at    TEXT NOT NULL,
    paid_at       TEXT
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.sqlite_path)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return date.today().isoformat()


def _migrate_points(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(user_points)").fetchall()}
    if "member_grant_month" not in cols:
        conn.execute("ALTER TABLE user_points ADD COLUMN member_grant_month TEXT")


def init_points_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        _migrate_points(conn)
        _seed_pricing(conn)
        conn.commit()


def _seed_pricing(conn: sqlite3.Connection) -> None:
    rows = [
        ("qian", 10, 1, "今日灵签"),
        ("liuyao", 25, 1, "六爻起卦"),
        ("meihua", 25, 1, "梅花易数"),
        ("bazi", 40, 1, "八字命理"),
        ("palm", 35, 1, "掌纹解析"),
        ("face", 35, 1, "面相解析"),
    ]
    for feature, cost, discountable, label in rows:
        conn.execute(
            """
            INSERT OR IGNORE INTO pricing_rules (feature, base_cost, member_discountable, label)
            VALUES (?, ?, ?, ?)
            """,
            (feature, cost, discountable, label),
        )
    conn.execute(
        "UPDATE pricing_rules SET base_cost = 20 WHERE feature IN ('liuyao', 'meihua')"
    )


def ensure_user_points(user_id: int, referral_code: str | None = None) -> dict:
    now = _now()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM user_points WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row:
            return dict(row)
        conn.execute(
            """
            INSERT INTO user_points (user_id, balance, member_tier, referral_code, updated_at)
            VALUES (?, 0, 'none', ?, ?)
            """,
            (user_id, referral_code, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM user_points WHERE user_id = ?", (user_id,)
        ).fetchone()
        return dict(row)


def get_user_points(user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM user_points WHERE user_id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_referral_code(code: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM user_points WHERE referral_code = ?", (code.strip().upper(),)
        ).fetchone()
        return dict(row) if row else None


def set_referral_code(user_id: int, code: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE user_points SET referral_code = ?, updated_at = ? WHERE user_id = ?",
            (code, _now(), user_id),
        )
        conn.commit()


def update_balance(user_id: int, delta: int) -> int:
    """原子增减余额，返回新余额。"""
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE user_points SET balance = balance + ?, updated_at = ?
            WHERE user_id = ?
            """,
            (delta, now, user_id),
        )
        row = conn.execute(
            "SELECT balance FROM user_points WHERE user_id = ?", (user_id,)
        ).fetchone()
        conn.commit()
        return int(row["balance"]) if row else 0


def insert_transaction(
    *,
    user_id: int,
    tx_type: str,
    amount: int,
    balance_after: int,
    feature: str | None = None,
    ref_id: str | None = None,
    idempotency_key: str | None = None,
    note: str | None = None,
) -> int:
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO point_transactions
            (user_id, type, amount, feature, ref_id, idempotency_key, balance_after, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, tx_type, amount, feature, ref_id, idempotency_key, balance_after, note, now),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_transaction_by_idempotency(idempotency_key: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM point_transactions WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        return dict(row) if row else None


def get_transaction_by_id(tx_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM point_transactions WHERE id = ?", (tx_id,)
        ).fetchone()
        return dict(row) if row else None


def list_transactions(user_id: int, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
    offset = max(0, (page - 1) * page_size)
    with _connect() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS c FROM point_transactions WHERE user_id = ?",
            (user_id,),
        ).fetchone()["c"]
        rows = conn.execute(
            """
            SELECT * FROM point_transactions WHERE user_id = ?
            ORDER BY created_at DESC LIMIT ? OFFSET ?
            """,
            (user_id, page_size, offset),
        ).fetchall()
        return [dict(r) for r in rows], int(total)


def get_pricing(feature: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM pricing_rules WHERE feature = ?", (feature,)
        ).fetchone()
        return dict(row) if row else None


def list_pricing() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM pricing_rules ORDER BY base_cost").fetchall()
        return [dict(r) for r in rows]


def get_daily_quota(user_id: int, feature: str, quota_date: str | None = None) -> dict:
    d = quota_date or _today()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM daily_quotas
            WHERE user_id = ? AND feature = ? AND quota_date = ?
            """,
            (user_id, feature, d),
        ).fetchone()
        if row:
            return dict(row)
        return {"user_id": user_id, "feature": feature, "quota_date": d, "used_count": 0}


def increment_daily_quota(user_id: int, feature: str) -> int:
    d = _today()
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO daily_quotas (user_id, feature, quota_date, used_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id, feature, quota_date)
            DO UPDATE SET used_count = used_count + 1
            """,
            (user_id, feature, d),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT used_count FROM daily_quotas
            WHERE user_id = ? AND feature = ? AND quota_date = ?
            """,
            (user_id, feature, d),
        ).fetchone()
        return int(row["used_count"]) if row else 1


def update_checkin(user_id: int, streak: int, checkin_date: str) -> None:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE user_points
            SET checkin_streak = ?, last_checkin_date = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (streak, checkin_date, _now(), user_id),
        )
        conn.commit()


def set_member_grant_month(user_id: int, month: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE user_points SET member_grant_month = ?, updated_at = ? WHERE user_id = ?",
            (month, _now(), user_id),
        )
        conn.commit()


def get_member_grant_month(user_id: int) -> str | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT member_grant_month FROM user_points WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["member_grant_month"] if row else None


def set_member(user_id: int, tier: str, expire_at: str | None) -> None:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE user_points
            SET member_tier = ?, member_expire_at = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (tier, expire_at, _now(), user_id),
        )
        conn.commit()


def create_invite_record(inviter_id: int, invitee_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO invite_rewards (inviter_id, invitee_id, created_at)
            VALUES (?, ?, ?)
            """,
            (inviter_id, invitee_id, _now()),
        )
        conn.commit()


def mark_invitee_granted(invitee_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE invite_rewards SET invitee_granted = 1 WHERE invitee_id = ?",
            (invitee_id,),
        )
        conn.commit()


def mark_inviter_granted(invitee_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE invite_rewards SET inviter_granted = 1 WHERE invitee_id = ?",
            (invitee_id,),
        )
        conn.commit()


def get_invite_record(invitee_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM invite_rewards WHERE invitee_id = ?", (invitee_id,)
        ).fetchone()
        return dict(row) if row else None


def count_inviter_grants_this_month(inviter_id: int) -> int:
    month_prefix = date.today().strftime("%Y-%m")
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(CASE WHEN inviter_granted = 1 THEN 1 ELSE 0 END), 0) AS c
            FROM invite_rewards
            WHERE inviter_id = ? AND created_at LIKE ?
            """,
            (inviter_id, f"{month_prefix}%"),
        ).fetchone()
        return int(row["c"]) if row else 0


def create_payment_order(
    user_id: int,
    order_type: str,
    product_id: str,
    amount_cents: int,
    points: int,
) -> int:
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO payment_orders
            (user_id, order_type, product_id, amount_cents, points, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
            """,
            (user_id, order_type, product_id, amount_cents, points, _now()),
        )
        conn.commit()
        return int(cur.lastrowid)


def complete_payment_order(order_id: int, external_id: str | None = None) -> dict | None:
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE payment_orders SET status = 'paid', paid_at = ?, external_id = ?
            WHERE id = ? AND status = 'pending'
            """,
            (now, external_id, order_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM payment_orders WHERE id = ?", (order_id,)).fetchone()
        return dict(row) if row else None


def get_payment_order(order_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM payment_orders WHERE id = ?", (order_id,)).fetchone()
        return dict(row) if row else None


init_points_db()
