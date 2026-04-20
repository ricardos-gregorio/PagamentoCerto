from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    gmail_user: str
    gmail_app_password: str
    email_from_name: str
    email_to: list[str]
    lista_fonte_url: str


def _split_emails(raw: str) -> list[str]:
    return [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]


def _resolve_lista_url() -> str:
    """Planilha (recomendado), depois legado Docs."""
    return (
        os.environ.get("LISTA_URL", "").strip()
        or os.environ.get("LISTA_GOOGLE_SHEET_URL", "").strip()
        or os.environ.get("LISTA_GOOGLE_DOC_URL", "").strip()
    )


def load_settings() -> Settings:
    user = os.environ.get("GMAIL_USER", "").strip()
    password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    name = os.environ.get("EMAIL_FROM_NAME", "PagamentoCerto").strip() or "PagamentoCerto"
    to_raw = os.environ.get("EMAIL_TO", "").strip()
    lista_url = _resolve_lista_url()

    missing = []
    if not user:
        missing.append("GMAIL_USER")
    if not password:
        missing.append("GMAIL_APP_PASSWORD")
    if not to_raw:
        missing.append("EMAIL_TO")
    if not lista_url:
        missing.append("LISTA_URL")
    if missing:
        raise SystemExit(
            "Variáveis de ambiente obrigatórias ausentes: "
            + ", ".join(missing)
            + ". No GitHub: Secret ou Variable LISTA_URL com o link da planilha. "
            + "No PC: .env com LISTA_URL=... Veja .env.example."
        )

    return Settings(
        gmail_user=user,
        gmail_app_password=password,
        email_from_name=name,
        email_to=_split_emails(to_raw),
        lista_fonte_url=lista_url,
    )
