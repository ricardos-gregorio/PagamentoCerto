from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from .config import Settings


def send_reminder_email(
    settings: Settings,
    subject: str,
    body_plain: str,
    body_html: str | None = None,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((settings.email_from_name, settings.gmail_user))
    msg["To"] = ", ".join(settings.email_to)
    msg.set_content(body_plain, charset="utf-8")
    if body_html is not None:
        msg.add_alternative(body_html, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as smtp:
        try:
            smtp.login(settings.gmail_user, settings.gmail_app_password)
        except smtplib.SMTPAuthenticationError as e:
            raise SystemExit(
                "Autenticação SMTP rejeitada pelo Gmail (535). Confira os secrets "
                "GMAIL_USER (e-mail completo da conta) e GMAIL_APP_PASSWORD (senha de app de 16 "
                "caracteres em Conta Google → Segurança → Como fazer login no Google → "
                "Senhas de app; não use a senha da conta). Gere uma senha nova se necessário."
            ) from e
        smtp.send_message(msg)
