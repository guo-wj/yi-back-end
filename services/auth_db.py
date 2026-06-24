"""用户表（SQLite 标准库）。

阻塞型操作（建表/查/插），调用方应放入线程池执行。导入时自动建表。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    email      TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    last_login TEXT
);
"""

_PHONE_EMAIL_SUFFIX = "@phone.yijian.local"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.sqlite_path)
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("PRAGMA table_info(users)").fetchall()
    return {row[1] for row in rows}


def _migrate(conn: sqlite3.Connection) -> None:
    cols = _table_columns(conn)
    if "phone" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN phone TEXT")
    if "password_hash" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    if "invite_code" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN invite_code TEXT")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone ON users(phone) "
        "WHERE phone IS NOT NULL"
    )


def init_db() -> None:
    with _connect() as conn:
        conn.execute(_SCHEMA)
        _migrate(conn)
        conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _phone_email(phone: str) -> str:
    return f"{phone}{_PHONE_EMAIL_SUFFIX}"


def _row_to_user(row: sqlite3.Row) -> dict:
    data = dict(row)
    phone = data.get("phone")
    if not phone and isinstance(data.get("email"), str):
        email = data["email"]
        if email.endswith(_PHONE_EMAIL_SUFFIX):
            phone = email[: -len(_PHONE_EMAIL_SUFFIX)]
            data["phone"] = phone
    return data


def get_user_by_email(email: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return _row_to_user(row) if row else None


def get_user_by_phone(phone: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE phone = ? OR email = ?",
            (phone, _phone_email(phone)),
        ).fetchone()
        return _row_to_user(row) if row else None


def create_user(email: str) -> dict:
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO users (email, created_at, last_login) VALUES (?, ?, ?)",
            (email, now, now),
        )
        conn.commit()
        user_id = cur.lastrowid
    return {"id": user_id, "email": email, "created_at": now, "last_login": now}


def create_phone_user(
    phone: str,
    password_hash: str,
    invite_code: str | None = None,
) -> dict:
    now = _now()
    email = _phone_email(phone)
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO users (email, phone, password_hash, invite_code, created_at, last_login)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (email, phone, password_hash, invite_code, now, now),
        )
        conn.commit()
        user_id = cur.lastrowid
    return {
        "id": user_id,
        "email": email,
        "phone": phone,
        "created_at": now,
        "last_login": now,
    }


def create_email_user(
    email: str,
    password_hash: str,
    invite_code: str | None = None,
) -> dict:
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO users (email, password_hash, invite_code, created_at, last_login)
            VALUES (?, ?, ?, ?, ?)
            """,
            (email, password_hash, invite_code, now, now),
        )
        conn.commit()
        user_id = cur.lastrowid
    return {
        "id": user_id,
        "email": email,
        "created_at": now,
        "last_login": now,
    }


def get_user_by_id(user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _row_to_user(row) if row else None


def touch_last_login(user_id: int) -> str:
    now = _now()
    with _connect() as conn:
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (now, user_id))
        conn.commit()
    return now


def get_or_create_user(email: str) -> tuple[dict, bool]:
    """返回 (用户, 是否新注册)。已存在则刷新 last_login。"""
    user = get_user_by_email(email)
    if user:
        user["last_login"] = touch_last_login(user["id"])
        return user, False
    return create_user(email), True


# 导入即建表，保证首次调用前表已存在
init_db()
