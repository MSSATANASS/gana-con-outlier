"""Email follow-up sequence for Outlier referrals.

Templates keyed by day-since-registration. Copy is deliberately sober (no
income promises) to stay within Outlier's community guidelines. Sending is
best-effort: if SMTP is not configured, callers should catch and log.
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER or "admin@lastminutestickets.com")
REPLY_TO = os.environ.get("REPLY_TO", "gael@lastminutestickets.com")
SENDER_NAME = os.environ.get("SENDER_NAME", "Gael L. Chulim Gongora")
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


def send_stage_email(*, to: str, nombre: str, day: int, unsubscribe_url: str) -> bool:
    """Send the email for ``day``. Returns True if actually sent."""
    if day not in SEQUENCE:
        return False
    subject, text = render(day, nombre, unsubscribe_url)

    if not SMTP_USER or not SMTP_PASS:
        # Not configured — caller decides what to do. Log to stdout for Render.
        print(f"[emails] (dry-run, no SMTP) day={day} to={to} subj={subject!r}")
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
    print(f"[emails] sent day={day} to={to}")
    return True
