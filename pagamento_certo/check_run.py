from __future__ import annotations

from .due_dates import days_until, next_due_date, reminder_due_and_offset
from .parse_table import iter_bill_rows_from_text
from .time_br import today_brazil


def print_check_report(text: str) -> None:
    """
    Diagnóstico sem expor descrições, valores ou PIX (apenas contagens e formato).
    """
    today = today_brazil()
    lines = text.replace("\r\n", "\n").split("\n")
    has_pipe = any("|" in ln for ln in lines)
    has_tab = any("\t" in ln for ln in lines)
    has_semi = any(";" in ln for ln in lines[:120])

    rows = list(iter_bill_rows_from_text(text))
    skipped_no_due = 0
    skipped_outside = 0
    items = 0
    ns_valid: list[int] = []
    for row in rows:
        due = next_due_date(today, row)
        if due is None:
            skipped_no_due += 1
            continue
        n = days_until(today, due)
        ns_valid.append(n)
        ctx = reminder_due_and_offset(today, row)
        if ctx is None:
            skipped_outside += 1
            continue
        items += 1

    print("=== PagamentoCerto — modo --check (não envia e-mail) ===")
    print(f"Data de hoje (America/Sao_Paulo): {today.isoformat()}")
    print(
        f"Texto baixado: {len(text)} caracteres, {len(lines)} linhas "
        f"(contém '|': {'sim' if has_pipe else 'não'}, "
        f"TAB: {'sim' if has_tab else 'não'}, "
        f"';' em linhas iniciais: {'sim' if has_semi else 'não'})"
    )
    print(f"Registros interpretados na tabela: {len(rows)}")
    print(
        f"Linhas sem próximo vencimento válido (ex.: data fixa já passou): {skipped_no_due}"
    )
    print(
        f"Linhas com vencimento, mas sem lembrete hoje (fora da janela, coluna Pago? com X, "
        f"ou regra de atraso): {skipped_outside}"
    )
    print(f"Lembretes que seriam enviados hoje: {items}")
    if ns_valid:
        print(
            f"Dias até o vencimento (por linha com data válida): "
            f"mín. {min(ns_valid)}, máx. {max(ns_valid)} "
            f"(alertas: 0–3 dias antes do vencimento, ou atraso conforme regras)"
        )
    if len(rows) == 0 and len(text.strip()) > 0:
        print(
            "\nNenhuma linha foi interpretada. Confira se o Google Docs tem uma tabela "
            "com cabeçalho descricao / valor / vencimento / pix. "
            "O export em TXT costuma usar TAB entre colunas (não precisa ser Markdown com |)."
        )
    elif items == 0 and len(rows) > 0:
        print(
            "\nA tabela foi lida, mas nenhum item dispara lembrete hoje (janela 0–3 dias, "
            "atraso ou coluna Pago?)."
        )
