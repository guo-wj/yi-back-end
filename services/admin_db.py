"""管理后台数据查询（SQLite）。"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from config import settings
from services import auth_db, points_db

_PHONE_EMAIL_SUFFIX = auth_db._PHONE_EMAIL_SUFFIX


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.sqlite_path)
    conn.row_factory = sqlite3.Row
    return conn


def _public_email(email: str | None) -> str | None:
    if not email or not isinstance(email, str):
        return None
    if email.endswith(_PHONE_EMAIL_SUFFIX):
        return None
    return email


def _user_row(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["email"] = _public_email(data.get("email"))
    phone = data.get("phone")
    if not phone and isinstance(row["email"], str) and row["email"].endswith(_PHONE_EMAIL_SUFFIX):
        data["phone"] = row["email"][: -len(_PHONE_EMAIL_SUFFIX)]
    return data


def list_users(
    *,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
) -> tuple[list[dict], int]:
    offset = max(0, (page - 1) * page_size)
    params: list = []
    where = ""
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        where = """
            WHERE u.id LIKE ? OR u.phone LIKE ? OR u.email LIKE ?
            OR CAST(u.id AS TEXT) LIKE ?
        """
        params = [kw, kw, kw, kw]

    with _connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM users u {where}",
            params,
        ).fetchone()["c"]
        rows = conn.execute(
            f"""
            SELECT u.*,
                   COALESCE(p.balance, 0) AS balance,
                   COALESCE(p.member_tier, 'none') AS member_tier,
                   p.member_expire_at,
                   p.referral_code,
                   p.checkin_streak
            FROM users u
            LEFT JOIN user_points p ON p.user_id = u.id
            {where}
            ORDER BY u.id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()
        return [_user_row(r) for r in rows], int(total)


def get_user_detail(user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT u.*,
                   COALESCE(p.balance, 0) AS balance,
                   COALESCE(p.member_tier, 'none') AS member_tier,
                   p.member_expire_at,
                   p.referral_code,
                   p.checkin_streak,
                   p.last_checkin_date,
                   p.updated_at AS points_updated_at
            FROM users u
            LEFT JOIN user_points p ON p.user_id = u.id
            WHERE u.id = ?
            """,
            (user_id,),
        ).fetchone()
        if not row:
            return None
        return _user_row(row)


def list_orders(
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    order_type: str | None = None,
    user_id: int | None = None,
) -> tuple[list[dict], int]:
    offset = max(0, (page - 1) * page_size)
    clauses: list[str] = []
    params: list = []

    if status:
        clauses.append("o.status = ?")
        params.append(status)
    if order_type:
        clauses.append("o.order_type = ?")
        params.append(order_type)
    if user_id is not None:
        clauses.append("o.user_id = ?")
        params.append(user_id)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with _connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM payment_orders o {where}",
            params,
        ).fetchone()["c"]
        rows = conn.execute(
            f"""
            SELECT o.*, u.phone, u.email AS user_email
            FROM payment_orders o
            LEFT JOIN users u ON u.id = o.user_id
            {where}
            ORDER BY o.id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()
        items = []
        for r in rows:
            item = dict(r)
            item["user_email"] = _public_email(item.get("user_email"))
            items.append(item)
        return items, int(total)


def get_overview_stats() -> dict:
    today = date.today().isoformat()
    with _connect() as conn:
        total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        today_users = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE created_at LIKE ?",
            (f"{today}%",),
        ).fetchone()["c"]
        total_balance = conn.execute(
            "SELECT COALESCE(SUM(balance), 0) AS s FROM user_points"
        ).fetchone()["s"]
        paid_orders = conn.execute(
            "SELECT COUNT(*) AS c, COALESCE(SUM(amount_cents), 0) AS revenue "
            "FROM payment_orders WHERE status = 'paid'"
        ).fetchone()
        today_revenue = conn.execute(
            """
            SELECT COALESCE(SUM(amount_cents), 0) AS s
            FROM payment_orders WHERE status = 'paid' AND paid_at LIKE ?
            """,
            (f"{today}%",),
        ).fetchone()["s"]
        today_consumes = conn.execute(
            """
            SELECT COUNT(*) AS c FROM point_transactions
            WHERE type = 'consume' AND created_at LIKE ?
            """,
            (f"{today}%",),
        ).fetchone()["c"]
        member_counts = conn.execute(
            """
            SELECT member_tier, COUNT(*) AS c FROM user_points
            WHERE member_tier != 'none'
            GROUP BY member_tier
            """
        ).fetchall()
        return {
            "total_users": int(total_users),
            "today_new_users": int(today_users),
            "total_points_balance": int(total_balance),
            "paid_orders": int(paid_orders["c"]),
            "total_revenue_cents": int(paid_orders["revenue"]),
            "today_revenue_cents": int(today_revenue),
            "today_consumes": int(today_consumes),
            "member_counts": {r["member_tier"]: int(r["c"]) for r in member_counts},
        }


def get_feature_usage_stats(days: int = 30) -> list[dict]:
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT feature, COUNT(*) AS count, COALESCE(SUM(ABS(amount)), 0) AS points_spent
            FROM point_transactions
            WHERE type = 'consume' AND created_at >= ? AND feature IS NOT NULL
            GROUP BY feature
            ORDER BY count DESC
            """,
            (since,),
        ).fetchall()
        pricing = {p["feature"]: p["label"] for p in points_db.list_pricing()}
        return [
            {
                "feature": r["feature"],
                "label": pricing.get(r["feature"], r["feature"]),
                "count": int(r["count"]),
                "points_spent": int(r["points_spent"]),
            }
            for r in rows
        ]


def get_daily_trends(days: int = 14) -> dict:
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    with _connect() as conn:
        user_rows = conn.execute(
            """
            SELECT substr(created_at, 1, 10) AS d, COUNT(*) AS c
            FROM users WHERE created_at >= ?
            GROUP BY d ORDER BY d
            """,
            (since,),
        ).fetchall()
        revenue_rows = conn.execute(
            """
            SELECT substr(paid_at, 1, 10) AS d, COALESCE(SUM(amount_cents), 0) AS s
            FROM payment_orders
            WHERE status = 'paid' AND paid_at >= ?
            GROUP BY d ORDER BY d
            """,
            (since,),
        ).fetchall()
        consume_rows = conn.execute(
            """
            SELECT substr(created_at, 1, 10) AS d, COUNT(*) AS c
            FROM point_transactions
            WHERE type = 'consume' AND created_at >= ?
            GROUP BY d ORDER BY d
            """,
            (since,),
        ).fetchall()
        return {
            "new_users": [{"date": r["d"], "count": int(r["c"])} for r in user_rows],
            "revenue_cents": [{"date": r["d"], "amount": int(r["s"])} for r in revenue_rows],
            "consumes": [{"date": r["d"], "count": int(r["c"])} for r in consume_rows],
        }


def list_user_transactions(
    user_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    return points_db.list_transactions(user_id, page, page_size)
