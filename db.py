"""Persistence layer for leads.

Uses Postgres when ``DATABASE_URL`` is set (Render), else a local SQLite file.
Same function interface for both. Rows are returned as plain dicts.
"""
from __future__ import annotations

import os
import sqlite3
from typing import Any, Optional

_DATABASE_URL = os.environ.get("DATABASE_URL", "")
_IS_PG = _DATABASE_URL.startswith(("postgres://", "postgresql://"))

if _IS_PG:
    import psycopg2
    import psycopg2.extras

    # Render sometimes gives postgres://; psycopg2 wants postgresql://
    _DSN = _DATABASE_URL.replace("postgres://", "postgresql://", 1)
else:
    _SQLITE_PATH = os.environ.get("SQLITE_PATH", "leads.db")


_COLUMNS = [
    "id", "nombre", "email", "whatsapp", "fuente", "ip",
    "created_at", "deadline", "etapa", "notas", "last_email_day", "unsubscribed",
    "tipo", "reward_usd", "tasks_done", "tasks_total", "expires",
]

# Columns added after the first release; migrated in-place on startup.
_MIGRATIONS = [
    ("tipo", "TEXT DEFAULT 'Outlier'"),
    ("reward_usd", "INTEGER DEFAULT 100"),
    ("tasks_done", "INTEGER DEFAULT 0"),
    ("tasks_total", "INTEGER DEFAULT 0"),
    ("expires", "TEXT DEFAULT ''"),
]


def _conn():
    if _IS_PG:
        return psycopg2.connect(_DSN)
    c = sqlite3.connect(_SQLITE_PATH)
    c.row_factory = sqlite3.Row
    return c


def _ph(n: int) -> str:
    """Placeholder string: %s for pg, ? for sqlite."""
    return ", ".join(["%s" if _IS_PG else "?"] * n)


def init_db() -> None:
    ddl_pg = """
    CREATE TABLE IF NOT EXISTS leads (
        id SERIAL PRIMARY KEY,
        nombre TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        whatsapp TEXT,
        fuente TEXT,
        ip TEXT,
        created_at TEXT,
        deadline TEXT,
        etapa TEXT DEFAULT 'registrado',
        notas TEXT DEFAULT '',
        last_email_day INTEGER DEFAULT -1,
        unsubscribed INTEGER DEFAULT 0,
        tipo TEXT DEFAULT 'Outlier',
        reward_usd INTEGER DEFAULT 100,
        tasks_done INTEGER DEFAULT 0,
        tasks_total INTEGER DEFAULT 0,
        expires TEXT DEFAULT ''
    );
    """
    ddl_sqlite = ddl_pg.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(ddl_pg if _IS_PG else ddl_sqlite)
        # Additive migrations for pre-existing tables.
        for col, decl in _MIGRATIONS:
            try:
                cur.execute(f"ALTER TABLE leads ADD COLUMN {col} {decl}")
            except Exception:
                pass  # column already exists
        conn.commit()


def _row_to_dict(row: Any) -> dict:
    if _IS_PG:
        return {c: row[i] for i, c in enumerate(_COLUMNS)}
    return {k: row[k] for k in row.keys()}


def insert_lead(*, nombre, email, whatsapp, fuente, ip, created_at, deadline,
                tipo="Outlier", reward_usd=100, tasks_done=0, tasks_total=0,
                expires="", etapa="registrado") -> int:
    sql = (
        f"INSERT INTO leads (nombre,email,whatsapp,fuente,ip,created_at,deadline,"
        f"etapa,tipo,reward_usd,tasks_done,tasks_total,expires) "
        f"VALUES ({_ph(13)})"
    )
    args = (nombre, email, whatsapp, fuente, ip, created_at, deadline, etapa,
            tipo, reward_usd, tasks_done, tasks_total, expires)
    with _conn() as conn:
        cur = conn.cursor()
        if _IS_PG:
            cur.execute(sql + " RETURNING id", args)
            lead_id = cur.fetchone()[0]
        else:
            cur.execute(sql, args)
            lead_id = cur.lastrowid
        conn.commit()
        return int(lead_id)


def get_lead_by_email(email: str) -> Optional[dict]:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT {','.join(_COLUMNS)} FROM leads WHERE email = {_ph(1)}", (email,))
        row = cur.fetchone()
        return _row_to_dict(row) if row else None


def get_lead_by_id(lead_id: int) -> Optional[dict]:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT {','.join(_COLUMNS)} FROM leads WHERE id = {_ph(1)}", (lead_id,))
        row = cur.fetchone()
        return _row_to_dict(row) if row else None


def all_leads() -> list[dict]:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT {','.join(_COLUMNS)} FROM leads ORDER BY id DESC")
        return [_row_to_dict(r) for r in cur.fetchall()]


def due_for_email(day: int) -> list[dict]:
    """Leads whose last sent email day < ``day``, still active, not unsubscribed."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT {','.join(_COLUMNS)} FROM leads "
            f"WHERE last_email_day < {_ph(1)} AND unsubscribed = 0 "
            f"AND etapa NOT IN ('pagado','perdido')",
            (day,),
        )
        return [_row_to_dict(r) for r in cur.fetchall()]


def update_stage(lead_id: int, etapa: str, notas: str) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE leads SET etapa = {_ph(1)}, notas = {_ph(1)} WHERE id = {_ph(1)}",
            (etapa, notas, lead_id),
        )
        conn.commit()


def mark_email_sent(lead_id: int, day: int) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE leads SET last_email_day = {_ph(1)} WHERE id = {_ph(1)}",
            (day, lead_id),
        )
        conn.commit()


def unsubscribe(lead_id: int) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE leads SET unsubscribed = 1 WHERE id = {_ph(1)}", (lead_id,))
        conn.commit()


def delete_lead(lead_id: int) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM leads WHERE id = {_ph(1)}", (lead_id,))
        conn.commit()


def update_progress(lead_id: int, tasks_done: int, tasks_total: int,
                    tipo: str, reward_usd: int, expires: str) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE leads SET tasks_done={_ph(1)}, tasks_total={_ph(1)}, "
            f"tipo={_ph(1)}, reward_usd={_ph(1)}, expires={_ph(1)} WHERE id={_ph(1)}",
            (tasks_done, tasks_total, tipo, reward_usd, expires, lead_id),
        )
        conn.commit()
