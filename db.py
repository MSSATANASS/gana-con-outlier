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
        unsubscribed INTEGER DEFAULT 0
    );
    """
    ddl_sqlite = ddl_pg.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(ddl_pg if _IS_PG else ddl_sqlite)
        conn.commit()


def _row_to_dict(row: Any) -> dict:
    if _IS_PG:
        return {c: row[i] for i, c in enumerate(_COLUMNS)}
    return {k: row[k] for k in row.keys()}


def insert_lead(*, nombre, email, whatsapp, fuente, ip, created_at, deadline) -> int:
    sql = (
        f"INSERT INTO leads (nombre,email,whatsapp,fuente,ip,created_at,deadline,etapa) "
        f"VALUES ({_ph(8)})"
    )
    args = (nombre, email, whatsapp, fuente, ip, created_at, deadline, "registrado")
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
