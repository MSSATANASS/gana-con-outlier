"""Email follow-up sequence for Outlier referrals.

Templates keyed by day-since-registration. Copy is deliberately sober (no
income promises) to stay within Outlier's community guidelines. Sending is
best-effort: if SMTP is not configured, callers should catch and log.
"""
from __future__ import annotations

import json
import os
import smtplib
import urllib.request
from email.message import EmailMessage

# Optional HTTP email provider (works on hosts that block outbound SMTP, e.g.
# Render's free tier). If RESEND_API_KEY is set, we use Resend's HTTP API and
# skip SMTP entirely.
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER or "admin@lastminutestickets.com")
REPLY_TO = os.environ.get("REPLY_TO", "gael@lastminutestickets.com")
SENDER_NAME = os.environ.get("SENDER_NAME", "Gael L. Chulim Gongora")

# Resend sits behind Cloudflare bot protection: urllib's default UA
# (Python-urllib/3.x) gets blocked with HTTP 403 / error code 1010, so we
# spoof a browser UA on every API call.
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
LANDING = os.environ.get("PUBLIC_URL", "https://gana-con-outlier.onrender.com")

# day -> (subject, body). {nombre} and {unsub} are filled at send time.
SEQUENCE: dict[int, tuple[str, str]] = {
    0: (
        "¡Bienvenido a Outlier! Tus primeros pasos (soy el de redes)",
        """Hola {nombre},

¡Qué bueno que te registraste! Soy Gael, el que te pasó el enlace de Outlier. Te acompaño para que no te pierdas en el proceso.

Haz esto hoy:
1. Completa tu perfil al 100% (CV, LinkedIn, y TODAS tus áreas: idiomas, redacción, matemáticas, programación).
2. Verifica tu identidad (identificación oficial + celular). Es normal y seguro; Outlier es de Scale AI.
3. Haz las pruebas de habilidad CON CALMA. De esto depende que te asignen proyectos.

Todo resumido aquí: {landing}

Cualquier duda, respóndeme este correo. ¡Éxito, hermano!
{firma}

—
Si no quieres más correos: {unsub}""",
    ),
    2: (
        "¿Ya hiciste el assessment? (es el paso clave)",
        """Hola {nombre},

Paso rápido para ver cómo vas. El punto donde más gente se atora es el ASSESSMENT / prueba de habilidad.

Tips para pasarlo:
- Léelo completo antes de empezar; no lo hagas a la carrera.
- Sé 100% honesto y NO uses IA para responderlo (te pueden expulsar).
- Revisa antes de enviar.

Si ya lo hiciste: ¡excelente! Ahora toca esperar asignación. Si te trabaste, respóndeme y te ayudo.
{firma}

—
Baja: {unsub}""",
    ),
    5: (
        "¿Ya te asignaron proyecto? Qué hacer si aún no",
        """Hola {nombre},

Si ya estás trabajando, ¡felicidades! Enfócate en acumular horas con calidad.

Si AÚN no tienes tareas (es normal), haz esto:
- Revisa la plataforma y tu correo varias veces al día.
- Asegúrate de tener TODAS tus habilidades marcadas en el perfil.
- Los proyectos llegan según tu perfil y la demanda; no te desesperes.

¿Llevas días sin nada? Respóndeme y vemos tu perfil juntos.
{firma}

—
Baja: {unsub}""",
    ),
    10: (
        "Tu meta: llegar a tus primeras horas facturables",
        """Hola {nombre},

Recordatorio con cariño: lo importante ahora es llegar a tus primeras horas de trabajo real en la plataforma. Ahí es donde empiezas a ganar.

Si ya estás facturando horas, vas perfecto. Si sigues esperando proyecto, escríbeme y lo revisamos, porque a veces es cosa de ajustar el perfil.
{firma}

—
Baja: {unsub}""",
    ),
    20: (
        "Quedan pocos días — no dejes pasar tu arranque",
        """Hola {nombre},

Ya llevas un tiempo en Outlier. Si todavía no arrancas con tareas, este es buen momento para darle un último empujón: revisa perfil, pruebas pendientes y disponibilidad.

Estoy para ayudarte. Respóndeme y lo resolvemos.
{firma}

—
Baja: {unsub}""",
    ),
}


def _firma() -> str:
    return f"{SENDER_NAME}"


def render(day: int, nombre: str, unsubscribe_url: str) -> tuple[str, str]:
    subject, body = SEQUENCE[day]
    text = body.format(
        nombre=nombre, landing=LANDING, unsub=unsubscribe_url, firma=_firma()
    )
    return subject, text


# Stage changes that deserve an immediate alert to the admin (Gael).
ALERT_SUBJECTS = {
    "trabajando": "🔥 {nombre} está TRABAJANDO — casi cobras",
    "pagado": "💰 ¡{nombre} PAGÓ! {reward} USD asegurados",
    "estancado": "⚠️ {nombre} se estancó — intervenir hoy",
}


def send_admin_alert(to: str, lead: dict) -> bool:
    """Alert the admin about a stage change that needs attention."""
    etapa = lead.get("etapa", "")
    if etapa not in ALERT_SUBJECTS or not RESEND_API_KEY:
        return False
    subject = ALERT_SUBJECTS[etapa].format(nombre=lead.get("nombre", ""), reward=lead.get("reward_usd", ""))
    text = (
        f"Cambio de etapa: {lead.get('nombre')} → {etapa}\n"
        f"Email: {lead.get('email')}\n"
        f"Tipo: {lead.get('tipo')} · Recompensa: ${lead.get('reward_usd')}\n"
        f"Tareas: {lead.get('tasks_done', 0)}/{lead.get('tasks_total', 0)}\n"
        f"Días restantes: {lead.get('days_left', '?')}\n"
        f"Notas: {lead.get('notas') or '—'}\n"
        f"Panel: {LANDING}/admin"
    )
    payload = json.dumps({
        "from": f"{SENDER_NAME} <{SMTP_FROM}>",
        "to": [to],
        "reply_to": REPLY_TO,
        "subject": subject,
        "text": text,
    }).encode()
    try:
        req = urllib.request.Request(
            "https://api.resend.com/emails", data=payload,
            headers={"Authorization": f"Bearer {RESEND_API_KEY}",
                     "Content-Type": "application/json",
                     "User-Agent": _BROWSER_UA},
        )
        urllib.request.urlopen(req, timeout=20)
        print(f"[emails] alert sent to={to} etapa={etapa}")
        return True
    except Exception as e:
        print(f"[emails] alert failed to={to}: {e}")
        return False


def send_stage_email(*, to: str, nombre: str, day: int, unsubscribe_url: str) -> bool:
    """Send the email for ``day``. Returns True if actually sent."""
    if day not in SEQUENCE:
        return False
    subject, text = render(day, nombre, unsubscribe_url)

    # Preferred: Resend HTTP API (not blocked by hosts that firewall SMTP).
    if RESEND_API_KEY:
        try:
            payload = json.dumps({
                "from": f"{SENDER_NAME} <{SMTP_FROM}>",
                "to": [to],
                "reply_to": REPLY_TO,
                "subject": subject,
                "text": text,
            }).encode()
            req = urllib.request.Request(
                "https://api.resend.com/emails", data=payload,
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                    "User-Agent": _BROWSER_UA,
                },
            )
            urllib.request.urlopen(req, timeout=20)
            print(f"[emails] sent via resend day={day} to={to}")
            return True
        except Exception as e:
            print(f"[emails] resend failed day={day} to={to}: {e}")
            return False

    # Fallback: SMTP (works locally / on hosts that allow port 587).
    if not SMTP_USER or not SMTP_PASS:
        print(f"[emails] (dry-run, no provider) day={day} to={to} subj={subject!r}")
        return False

    msg = EmailMessage()
    msg["From"] = f"{SENDER_NAME} <{SMTP_FROM}>"
    msg["To"] = to
    msg["Reply-To"] = REPLY_TO
    msg["Subject"] = subject
    msg.set_content(text, charset="utf-8")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)
    print(f"[emails] sent via smtp day={day} to={to}")
    return True
