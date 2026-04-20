from __future__ import annotations

import html
from datetime import date


def _format_date_br(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def subject_urgente(descricao: str, due: date, valor_fmt: str, days_until_due: int) -> str:
    """Assunto alinhado ao modelo: 🔴 URGENTE: Conta vence … (data) — R$ …"""
    d_str = _format_date_br(due)
    desc = descricao.strip()
    if days_until_due < 0:
        return f"🔴 URGENTE: {desc} em ATRASO (venc. {d_str}) — R$ {valor_fmt}"
    phrase = {
        3: "EM 3 DIAS",
        2: "EM 2 DIAS",
        1: "AMANHÃ",
        0: "HOJE",
    }[days_until_due]
    return f"🔴 URGENTE: {desc} vence {phrase} ({d_str}) — R$ {valor_fmt}"


def _intro_phrase(days_until_due: int) -> str:
    """Trecho em negrito na frase de abertura (HTML usa <strong> externamente)."""
    if days_until_due < 0:
        return "em atraso"
    return {3: "em 3 dias", 2: "em 2 dias", 1: "amanhã", 0: "hoje"}[days_until_due]


def body_plain_and_html(
    row,
    due: date,
    valor_fmt: str,
    days_until_due: int,
) -> tuple[str, str]:
    d_str = _format_date_br(due)
    intro = _intro_phrase(days_until_due)
    conta = row.descricao.strip()
    pix = row.pix.strip() if row.pix else ""
    pix_plain = pix if pix else "—"
    pix_html = html.escape(pix) if pix else "—"

    if days_until_due < 0:
        opener = f"Oi! Passando pra te lembrar de uma conta em atraso (vencimento {d_str}):"
    else:
        opener = f"Oi! Passando pra te lembrar de uma conta que vence {intro}:"
    lines = [
        opener,
        "",
        f"Conta: {conta}",
        f"Valor: R$ {valor_fmt}",
        f"Vencimento: {d_str}",
        f"PIX: {pix_plain}",
        "",
        "Se já pagou, marque X na coluna Pago? na planilha para parar os lembretes.",
        "",
        "— Enviado automaticamente pelo PagamentoCerto",
        "",
        "PagamentoCerto • lembrete automático",
    ]
    plain = "\n".join(lines) + "\n"

    conta_h = html.escape(conta)
    intro_h = html.escape(intro)
    if days_until_due < 0:
        opener_html = f"Oi! Passando pra te lembrar de uma conta em atraso (vencimento {html.escape(d_str)}):"
    else:
        opener_html = f"Oi! Passando pra te lembrar de uma conta que vence <strong>{intro_h}</strong>:"

    html_body = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PagamentoCerto</title>
</head>
<body style="margin:0;padding:24px 16px;background:#f1f3f4;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;-webkit-text-size-adjust:100%;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">
<tr><td align="center">
<table role="presentation" style="max-width:560px;width:100%;background:#ffffff;border-radius:12px;padding:28px 32px;box-shadow:0 1px 3px rgba(60,64,67,.15);border-collapse:collapse;">
<tr><td style="color:#202124;font-size:16px;line-height:1.55;">
<p style="margin:0 0 18px;">{opener_html}</p>
<ul style="margin:0 0 0 20px;padding:0;color:#202124;font-size:15px;line-height:1.65;">
<li style="margin-bottom:10px;"><strong>Conta:</strong> {conta_h}</li>
<li style="margin-bottom:10px;"><strong>Valor:</strong> R$ {html.escape(valor_fmt)}</li>
<li style="margin-bottom:10px;"><strong>Vencimento:</strong> {html.escape(d_str)}</li>
<li style="margin-bottom:10px;"><strong>PIX:</strong> {pix_html}</li>
</ul>
<p style="margin:22px 0 0;font-size:15px;color:#202124;">Se já pagou, marque X na coluna Pago? na planilha para parar os lembretes.</p>
<p style="margin:20px 0 0;font-size:14px;color:#5f6368;">— <em>Enviado automaticamente pelo PagamentoCerto</em></p>
</td></tr></table>
<p style="margin:16px 0 0;font-size:12px;color:#9aa0a6;text-align:center;">PagamentoCerto • lembrete automático</p>
</td></tr></table>
</body>
</html>
"""
    return plain, html_body
