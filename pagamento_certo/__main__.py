from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from .check_run import print_check_report
from .config import load_settings
from .due_dates import reminder_due_and_offset
from .email_render import body_plain_and_html, subject_urgente
from .fetch_lista import download_lista_text
from .notify import send_reminder_email
from .parse_table import iter_bill_rows_from_text
from .time_br import today_brazil


def _format_money_br(value: float) -> str:
    s = f"{value:.2f}"
    intp, frac = s.split(".")
    intp = intp[::-1]
    groups = [intp[i : i + 3] for i in range(0, len(intp), 3)]
    intp_fmt = ".".join(g[::-1] for g in groups[::-1])
    return f"{intp_fmt},{frac}"


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="PagamentoCerto — lembretes de vencimento")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Baixa o documento, mostra diagnóstico (sem enviar e-mail nem logar dados sensíveis)",
    )
    args = parser.parse_args()
    settings = load_settings()

    text = download_lista_text(settings.lista_fonte_url)
    if args.check:
        print_check_report(text)
        return

    fd, tmp_name = tempfile.mkstemp(prefix="lista_", suffix=".md", text=True)
    os.close(fd)
    path = Path(tmp_name)
    try:
        path.write_text(text, encoding="utf-8")
        processed = path.read_text(encoding="utf-8")
        _run(settings, processed)
    finally:
        path.unlink(missing_ok=True)


def _run(settings, text: str) -> None:
    # Data “hoje” no fuso de São Paulo — evita divergência UTC no Actions.
    today = today_brazil()
    items = []
    for row in iter_bill_rows_from_text(text):
        ctx = reminder_due_and_offset(today, row)
        if ctx is None:
            continue
        due, n = ctx
        items.append((row, due, n))

    if not items:
        print("Nenhum lembrete para a data de hoje.")
        return

    sent = 0
    for row, due, n in sorted(items, key=lambda x: (x[1], x[0].descricao.lower())):
        valor_fmt = _format_money_br(row.valor)
        subject = subject_urgente(row.descricao, due, valor_fmt, n)
        body_plain, body_html = body_plain_and_html(row, due, valor_fmt, n)
        send_reminder_email(
            settings,
            subject=subject,
            body_plain=body_plain,
            body_html=body_html,
        )
        sent += 1

    print(f"E-mail enviado: {sent} mensagem(ns) de lembrete.")


if __name__ == "__main__":
    main()
