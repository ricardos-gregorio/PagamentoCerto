from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from typing import Optional

from .parse_table import BillRow


def _safe_day(year: int, month: int, day: int) -> date:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last))


def _next_monthly_due(today: date, day: int) -> date:
    cand = _safe_day(today.year, today.month, day)
    if cand >= today:
        return cand
    y, m = today.year, today.month
    if m == 12:
        y, m = y + 1, 1
    else:
        m += 1
    return _safe_day(y, m, day)


def _parse_fixed_date(raw: str) -> Optional[date]:
    t = raw.strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return date(y, mo, d)
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return date(y, mo, d)
    return None


def _parse_month_day(raw: str) -> Optional[int]:
    t = raw.strip().replace("\xa0", "").replace(" ", "")
    if not t:
        return None
    # Planilha pode exportar o dia como número (20.0)
    m = re.fullmatch(r"(\d{1,2})(?:[.,]0+)?$", t.replace(",", "."))
    if m:
        d = int(m.group(1))
        if 1 <= d <= 31:
            return d
    return None


def next_due_date(today: date, row: BillRow) -> Optional[date]:
    raw = row.vencimento_raw
    fixed = _parse_fixed_date(raw)
    if fixed is not None:
        return fixed if fixed >= today else None
    md = _parse_month_day(raw)
    if md is not None:
        return _next_monthly_due(today, md)
    return None


def days_until(d0: date, d1: date) -> int:
    return (d1 - d0).days


def reminder_window_days() -> frozenset[int]:
    """Compat: conjunto de valores de `days_until` que disparam lembrete."""
    return frozenset(_reminder_day_counts())


def _reminder_day_counts() -> tuple[int, ...]:
    """Quantidade de dias corridos até o vencimento (n) em que enviamos alerta.

    Regra: enviar no **dia do vencimento** (n=0) e nos **3 dias anteriores** (n=1, 2, 3).

    Ex.: vencimento dia 20 → enviamos nos dias 17, 18, 19 (n=3,2,1) e no dia 20 (n=0).
    """
    return (0, 1, 2, 3)


def should_send_reminder(today: date, due: date) -> bool:
    """True se hoje é o vencimento ou um dos 3 dias anteriores."""
    n = days_until(today, due)
    return n in _reminder_day_counts()


def reminder_due_and_offset(today: date, row: BillRow) -> Optional[tuple[date, int]]:
    """Retorna (data de referência do lembrete, dias até essa data) ou None.

    - Coluna «Pago?» com X: nunca lembra.
    - Vencimento mensal (só dia): janela nos 3 dias anteriores e no dia do vencimento;
      após o vencimento sem X, lembrete diário (até marcar X). Entre meses, cobra
      atraso do mês anterior só se o atraso não for muito maior que a espera pelo
      vencimento do mês atual (evita cobrar março no início de abril).
    - Data fixa dd/mm/aaaa: mesma janela; após a data, diário até X.
    """
    if row.pago:
        return None
    raw = row.vencimento_raw
    fixed = _parse_fixed_date(raw)
    if fixed is not None:
        if fixed >= today:
            n = days_until(today, fixed)
            if n in _reminder_day_counts():
                return (fixed, n)
            return None
        return (fixed, days_until(today, fixed))
    md = _parse_month_day(raw)
    if md is None:
        return None
    return _reminder_monthly_dom(today, md)


def _reminder_monthly_dom(today: date, day: int) -> Optional[tuple[date, int]]:
    up = _next_monthly_due(today, day)
    n_up = days_until(today, up)
    if n_up in _reminder_day_counts():
        return (up, n_up)
    this_due = _safe_day(today.year, today.month, day)
    if this_due < today:
        return (this_due, days_until(today, this_due))
    if today.month == 1:
        py, pm = today.year - 1, 12
    else:
        py, pm = today.year, today.month - 1
    prev_due = _safe_day(py, pm, day)
    if prev_due >= today:
        return None
    gap = (this_due - today).days
    late = (today - prev_due).days
    if gap <= 3:
        return None
    if late <= gap + 7:
        return (prev_due, days_until(today, prev_due))
    return None
