#!/usr/bin/env python3
"""
Envía el correo de bienvenida de Outlier a un referido nuevo.
Uso:
    SMTP_USER="tu_correo@gmail.com" SMTP_PASS="tu_contraseña_de_aplicacion" \
    python3 enviar_correo.py destinatario@correo.com "Nombre"
"""
import os
import sys
import smtplib
from email.message import EmailMessage

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
ASUNTO = "¡Bienvenido a Outlier! Te guío en tus primeros pasos (soy el de Facebook)"


def main():
    if len(sys.argv) < 2:
        sys.exit('Uso: python3 enviar_correo.py destinatario@correo.com "Nombre"')

    destinatario = sys.argv[1]
    nombre = sys.argv[2] if len(sys.argv) > 2 else "amigo"

    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    if not smtp_user or not smtp_pass:
        sys.exit("Error: define SMTP_USER y SMTP_PASS como variables de entorno.")

    with open("correo-bienvenida.txt", encoding="utf-8") as f:
        lineas = f.read().splitlines()

    # Saltar las 3 primeras líneas (PARA/ASUNTO/separador) y personalizar el nombre
    cuerpo = "\n".join(lineas[3:]).replace("[nombre]", nombre).strip()

    msg = EmailMessage()
    msg["From"] = f"Gael L. Chulim Gongora <{smtp_user}>"
    msg["To"] = destinatario
    msg["Subject"] = ASUNTO
    msg.set_content(cuerpo, charset="utf-8")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as servidor:
        servidor.starttls()
        servidor.login(smtp_user, smtp_pass)
        servidor.send_message(msg)

    print(f"✅ Correo enviado a {destinatario}")


if __name__ == "__main__":
    main()
