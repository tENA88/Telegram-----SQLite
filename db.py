from datetime import datetime

import aiosqlite

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_applications_user
    ON applications(user_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_applications_status
    ON applications(status, id DESC);
"""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def format_dt(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return value


async def init() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def upsert_user(user_id: int, username: str | None, full_name: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (id, username, full_name, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name
            """,
            (user_id, username, full_name, now()),
        )
        await db.commit()


async def create_application(
    user_id: int,
    name: str,
    phone: str,
    category: str,
    description: str,
) -> int:
    ts = now()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO applications
                (user_id, name, phone, category, description, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'new', ?, ?)
            """,
            (user_id, name, phone, category, description, ts, ts),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def get_application(app_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT a.*, u.username, u.full_name AS tg_name
            FROM applications a
            JOIN users u ON u.id = a.user_id
            WHERE a.id = ?
            """,
            (app_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def list_user_applications(user_id: int, limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM applications
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def list_by_status(status: str, limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT a.*, u.username
            FROM applications a
            JOIN users u ON u.id = a.user_id
            WHERE a.status = ?
            ORDER BY a.id DESC
            LIMIT ?
            """,
            (status, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def set_status(app_id: int, status: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT status FROM applications WHERE id = ?", (app_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        if row["status"] == status:
            return await get_application(app_id)
        await db.execute(
            "UPDATE applications SET status = ?, updated_at = ? WHERE id = ?",
            (status, now(), app_id),
        )
        await db.commit()
    return await get_application(app_id)
