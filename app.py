"""Outlier referral capture + follow-up system.

Single FastAPI service that:
  - serves the existing static landing (index.html, style.css, script.js)
  - captures leads (POST /api/lead) then hands back the Outlier referral link
  - runs a time-based email follow-up sequence (APScheduler)
  - exposes a private /admin panel (X-Admin-Secret) with the money-at-risk view
    and a ready-to-send WhatsApp queue

Persistence: DATABASE_URL (Postgres on Render) if set, else a local SQLite file
for dev. The interface is the same either way.

Env vars:
  ADMIN_SECRET          gate for /admin (default: dev-secret, CHANGE in prod)
  REFERRAL_LINK         Outlier referral URL (has a sane default)
  BONUS_USD             payout per qualified referral (default 100)
  WINDOW_DAYS           qualifying window in days (default 30)
  SMTP_HOST/PORT/USER/PASS/FROM/REPLY_TO   email sending (optional; if unset,
                        the sequence is logged but not sent)
  PUBLIC_URL            base URL for unsubscribe links
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, field_validator

import db
import emails
from scheduler import start_scheduler

BASE_DIR = Path(__file__).parent
REFERRAL_LINK = os.environ.get(
    "REFERRAL_LINK",
    "https://app.outlier.ai/expert/referrals/link/4JBXAOTH_L2a6J68TED52x5hpHk",
)
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "dev-secret")
BONUS_USD = int(os.environ.get("BONUS_USD", "100"))
WINDOW_DAYS = int(os.environ.get("WINDOW_DAYS", "30"))
PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://gana-con-outlier.onrender.com")

STAGES = ["registrado", "assessment", "trabajando", "pagado", "estancado", "perdido"]
# Stages that still count as "at risk" money (not yet paid, not yet lost).
AT_RISK = {"registrado", "assessment", "trabajando", "estancado"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    start_scheduler()
    yield


app = FastAPI(title="Outlier Referrals", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Lead capture
# ---------------------------------------------------------------------------


class LeadIn(BaseModel):
    nombre: str
    email: EmailStr
    whatsapp: str
    fuente: str = "directo"
    # honeypot — bots fill it, humans never see it
    website: str = ""

    @field_validator("nombre")
    @classmethod
    def _name_ok(cls, v: str) -> str:
        v = (v or "").strip()
        if len(v) < 2:
            raise ValueError("nombre demasiado corto")
        return v[:80]

    @field_validator("whatsapp")
    @classmethod
    def _wa_ok(cls, v: str) -> str:
        digits = "".join(c for c in (v or "") if c.isdigit() or c == "+")
        if len(digits) < 8:
            raise ValueError("whatsapp inválido")
        return digits[:20]


@app.post("/api/lead")
async def create_lead(lead: LeadIn, request: Request) -> JSONResponse:
    # Honeypot: silently accept but drop bots.
    if lead.website:
        return JSONResponse({"ok": True, "referral": REFERRAL_LINK})

    ip = request.client.host if request.client else "unknown"
    now = datetime.now(timezone.utc)
    existing = db.get_lead_by_email(lead.email)
    if existing:
        # Idempotent: don't duplicate, just hand back the link again.
        return JSONResponse({"ok": True, "referral": REFERRAL_LINK, "returning": True})

    lead_id = db.insert_lead(
        nombre=lead.nombre,
        email=lead.email,
        whatsapp=lead.whatsapp,
        fuente=lead.fuente,
        ip=ip,
        created_at=now.isoformat(),
        deadline=(now + timedelta(days=WINDOW_DAYS)).isoformat(),
    )
    # Fire the welcome email immediately (best-effort).
    try:
        emails.send_stage_email(
            to=lead.email, nombre=lead.nombre, day=0,
            unsubscribe_url=f"{PUBLIC_URL}/unsubscribe?id={lead_id}",
        )
        db.mark_email_sent(lead_id, 0)
    except Exception:
        pass

    return JSONResponse({"ok": True, "referral": REFERRAL_LINK, "id": lead_id})


@app.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe(id: int) -> HTMLResponse:
    db.unsubscribe(id)
    return HTMLResponse(
        "<html><body style='font-family:sans-serif;text-align:center;padding:60px'>"
        "<h2>Listo</h2><p>Ya no recibirás más correos de seguimiento. "
        "Si fue un error, escríbeme y te reactivo.</p></body></html>"
    )


# ---------------------------------------------------------------------------
# Admin panel
# ---------------------------------------------------------------------------


def _check_admin(secret: Optional[str]) -> None:
    if secret != ADMIN_SECRET:
        raise HTTPException(401, "unauthorized")


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(x_admin_secret: Optional[str] = Header(None)) -> HTMLResponse:
    # Allow ?secret= too, for browser convenience.
    return HTMLResponse(_render_admin())


@app.get("/admin/data")
async def admin_data(
    secret: Optional[str] = None,
    x_admin_secret: Optional[str] = Header(None),
) -> JSONResponse:
    _check_admin(secret or x_admin_secret)
    leads = db.all_leads()
    now = datetime.now(timezone.utc)
    enriched = []
    at_risk = secured = 0
    for l in leads:
        deadline = datetime.fromisoformat(l["deadline"])
        days_left = (deadline - now).days
        etapa = l["etapa"]
        if etapa == "pagado":
            secured += BONUS_USD
        elif etapa in AT_RISK:
            at_risk += BONUS_USD
        enriched.append({**l, "days_left": days_left})
    conv = round(100 * sum(1 for l in leads if l["etapa"] == "pagado") / len(leads)) if leads else 0
    return JSONResponse({
        "leads": enriched,
        "metrics": {
            "total": len(leads),
            "at_risk_usd": at_risk,
            "secured_usd": secured,
            "conversion_pct": conv,
            "bonus_usd": BONUS_USD,
        },
        "stages": STAGES,
    })


class StageUpdate(BaseModel):
    id: int
    etapa: str
    notas: str = ""


@app.post("/admin/update")
async def admin_update(
    upd: StageUpdate,
    secret: Optional[str] = None,
    x_admin_secret: Optional[str] = Header(None),
) -> JSONResponse:
    _check_admin(secret or x_admin_secret)
    if upd.etapa not in STAGES:
        raise HTTPException(400, "etapa inválida")
    db.update_stage(upd.id, upd.etapa, upd.notas)
    return JSONResponse({"ok": True})


class ManualLead(BaseModel):
    nombre: str
    email: EmailStr
    whatsapp: str
    fuente: str = "ig-manual"
    created_at: Optional[str] = None  # ISO; for backfilling the existing 8


@app.post("/admin/add")
async def admin_add(
    m: ManualLead,
    secret: Optional[str] = None,
    x_admin_secret: Optional[str] = Header(None),
) -> JSONResponse:
    _check_admin(secret or x_admin_secret)
    created = m.created_at or datetime.now(timezone.utc).isoformat()
    created_dt = datetime.fromisoformat(created)
    if created_dt.tzinfo is None:
        created_dt = created_dt.replace(tzinfo=timezone.utc)
    if db.get_lead_by_email(m.email):
        raise HTTPException(409, "ya existe")
    lead_id = db.insert_lead(
        nombre=m.nombre, email=m.email, whatsapp=m.whatsapp, fuente=m.fuente,
        ip="manual", created_at=created_dt.isoformat(),
        deadline=(created_dt + timedelta(days=WINDOW_DAYS)).isoformat(),
    )
    return JSONResponse({"ok": True, "id": lead_id})


# ---------------------------------------------------------------------------
# Static landing (mounted LAST so /api and /admin win)
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def index() -> FileResponse:
    return FileResponse(BASE_DIR / "index.html")


app.mount("/", StaticFiles(directory=str(BASE_DIR), html=True), name="static")


def _render_admin() -> str:
    return (BASE_DIR / "admin.html").read_text(encoding="utf-8")
