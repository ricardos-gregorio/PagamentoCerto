from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class BillRow:
    descricao: str
    valor: float
    vencimento_raw: str
    pix: str
    pago: bool = False


def _normalize_header(h: str) -> str:
    return re.sub(r"\s+", " ", h.strip().lower())


def cell_marks_paid(raw: str) -> bool:
    """Coluna «Pago?»: X (maiúsculo ou minúsculo) = já pago, sem lembrete."""
    t = raw.strip().replace("\xa0", "")
    return t.upper() == "X"


def _header_is_pago(h: str) -> bool:
    return "pago" in h


def _row_pago(cells: list[str], i_pago: int | None) -> bool:
    if i_pago is None or i_pago >= len(cells):
        return False
    return cell_marks_paid(cells[i_pago])


def _header_is_vencimento(h: str) -> bool:
    """Coluna do dia/mês ou data fixa: vencimento, data, etc."""
    if not h:
        return False
    if "venc" in h:
        return True
    # Planilhas em PT usam só «data» para o dia do vencimento
    if h == "data":
        return True
    return False


def _split_pipe_line(line: str) -> list[str]:
    if "|" not in line:
        return []
    parts = [p.strip() for p in line.split("|")]
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def parse_valor_br(s: str) -> float:
    t = s.strip().replace(" ", "").replace("\xa0", "")
    if not t:
        return 0.0
    if re.fullmatch(r"-?\d+([.,]\d+)?", t):
        if "," in t and "." not in t:
            t = t.replace(",", ".")
        return float(t)
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
        return float(t)
    if "," in t:
        return float(t.replace(",", "."))
    return float(t)


def _looks_like_separator(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    return bool(re.fullmatch(r"[|\s:\-–—_=]+", s))


def _split_row_delimited(line: str, delimiter: str) -> list[str]:
    if delimiter == "\t":
        return [p.strip() for p in line.split("\t")]
    return [p.strip() for p in line.split(delimiter)]


def _try_parse_delimited_table(
    text: str, delimiter: str
) -> Iterator[BillRow] | None:
    """
    Tabelas exportadas do Google Docs costumam vir sem '|', com TAB ou ';' entre colunas.
    """
    lines = [ln for ln in text.replace("\r\n", "\n").split("\n")]
    search_limit = min(len(lines), 80)
    for idx in range(search_limit):
        raw = lines[idx]
        if delimiter not in raw and delimiter != " ":
            continue
        parts = _split_row_delimited(raw, delimiter)
        if len(parts) < 4:
            continue
        headers = [_normalize_header(h) for h in parts]
        try:
            i_desc = next(i for i, h in enumerate(headers) if "desc" in h)
            i_val = next(i for i, h in enumerate(headers) if h.startswith("valor"))
            i_ven = next(i for i, h in enumerate(headers) if _header_is_vencimento(h))
            i_pix = next(i for i, h in enumerate(headers) if "pix" in h)
        except StopIteration:
            continue
        i_pago = next((i for i, h in enumerate(headers) if _header_is_pago(h)), None)
        min_cells = max(i_desc, i_val, i_ven, i_pix) + 1

        def _gen_bill_rows() -> Iterator[BillRow]:
            for ln in lines[idx + 1 :]:
                s = ln.strip()
                if not s:
                    continue
                if _looks_like_separator(s):
                    continue
                cells = _split_row_delimited(ln, delimiter)
                if len(cells) < min_cells:
                    continue
                desc = cells[i_desc].strip()
                if not desc or _normalize_header(desc) == "descricao":
                    continue
                ven = cells[i_ven].strip()
                if not ven:
                    continue
                yield BillRow(
                    descricao=desc,
                    valor=parse_valor_br(cells[i_val]),
                    vencimento_raw=ven,
                    pix=cells[i_pix].strip() if i_pix < len(cells) else "",
                    pago=_row_pago(cells, i_pago),
                )

        it = _gen_bill_rows()
        first = next(it, None)
        if first is None:
            continue

        def _chain() -> Iterator[BillRow]:
            yield first
            yield from it

        return _chain()
    return None


def _try_parse_sheet_csv(text: str, delimiter: str) -> Iterator[BillRow] | None:
    """Export CSV do Google Sheets (vírgula ou ponto e vírgula)."""
    t = text.lstrip("\ufeff").strip()
    if not t:
        return None
    first_nonempty = next((ln for ln in t.splitlines() if ln.strip()), "")
    if delimiter not in first_nonempty:
        return None
    try:
        rows = list(csv.reader(io.StringIO(t), delimiter=delimiter))
    except csv.Error:
        return None
    if len(rows) < 2:
        return None
    headers = [_normalize_header(h) for h in rows[0]]
    if not any(h and "desc" in h for h in headers):
        return None
    try:
        i_desc = next(i for i, h in enumerate(headers) if h and "desc" in h)
        i_val = next(i for i, h in enumerate(headers) if h and h.startswith("valor"))
        i_ven = next(i for i, h in enumerate(headers) if h and _header_is_vencimento(h))
        i_pix = next(i for i, h in enumerate(headers) if h and "pix" in h)
    except StopIteration:
        return None
    i_pago = next((i for i, h in enumerate(headers) if h and _header_is_pago(h)), None)
    min_cells = max(i_desc, i_val, i_ven, i_pix) + 1

    def _gen_bill_rows() -> Iterator[BillRow]:
        for parts in rows[1:]:
            if len(parts) < min_cells:
                continue
            desc = parts[i_desc].strip()
            ven = parts[i_ven].strip() if i_ven < len(parts) else ""
            if not desc or not ven:
                continue
            if _normalize_header(desc) == "descricao":
                continue
            yield BillRow(
                descricao=desc,
                valor=parse_valor_br(parts[i_val] if i_val < len(parts) else ""),
                vencimento_raw=ven,
                pix=parts[i_pix].strip() if i_pix < len(parts) else "",
                pago=_row_pago(parts, i_pago),
            )

    it = _gen_bill_rows()
    first = next(it, None)
    if first is None:
        return None

    def _chain() -> Iterator[BillRow]:
        yield first
        yield from it

    return _chain()


def iter_bill_rows_from_text(text: str) -> Iterator[BillRow]:
    """
    Aceita tabela estilo Markdown (| col |), TAB/CSV ou texto delimitado com cabeçalho.
    Cabeçalhos típicos: descrição, valor, vencimento ou data (dia), pix / pix-conta;
    opcional «Pago?» com X quando já pago.
    """
    text = text.lstrip("\ufeff")
    lines = [ln.rstrip("\n") for ln in text.replace("\r\n", "\n").split("\n")]
    pipe_lines = [ln for ln in lines if "|" in ln.strip()]
    if len(pipe_lines) >= 2:
        header_parts = _split_pipe_line(pipe_lines[0])
        headers = [_normalize_header(h) for h in header_parts]
        try:
            i_desc = next(i for i, h in enumerate(headers) if "desc" in h)
            i_val = next(i for i, h in enumerate(headers) if h.startswith("valor"))
            i_ven = next(i for i, h in enumerate(headers) if _header_is_vencimento(h))
            i_pix = next(i for i, h in enumerate(headers) if "pix" in h)
        except StopIteration:
            i_desc, i_val, i_ven, i_pix = 0, 1, 2, 3
        i_pago = next((i for i, h in enumerate(headers) if _header_is_pago(h)), None)
        min_cells = max(i_desc, i_val, i_ven, i_pix) + 1

        for ln in pipe_lines[1:]:
            if _looks_like_separator(ln):
                continue
            parts = _split_pipe_line(ln)
            if len(parts) < min_cells:
                continue
            desc = parts[i_desc].strip()
            if not desc or _normalize_header(desc) == "descricao":
                continue
            ven = parts[i_ven].strip()
            if not ven:
                continue
            yield BillRow(
                descricao=desc,
                valor=parse_valor_br(parts[i_val]),
                vencimento_raw=ven,
                pix=parts[i_pix].strip() if i_pix < len(parts) else "",
                pago=_row_pago(parts, i_pago),
            )
        return

    # Google Docs (export txt): geralmente TAB ou ';' entre colunas, sem pipes.
    for delim in ("\t", ";"):
        attempt = _try_parse_delimited_table(text, delim)
        if attempt is not None:
            yield from attempt
            return

    # Google Sheets (export CSV): vírgula ou ';' conforme região da planilha.
    for delim in (",", ";"):
        attempt = _try_parse_sheet_csv(text, delim)
        if attempt is not None:
            yield from attempt
            return

    # Fallback: CSV com detecção de dialeto
    buf = io.StringIO(text)
    sample = buf.read(4096)
    buf = io.StringIO(sample + buf.read())
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";\t,")
    except csv.Error:
        dialect = csv.excel
    buf.seek(0)
    reader = csv.reader(buf, dialect)
    rows = list(reader)
    if not rows:
        return
    headers = [_normalize_header(h) for h in rows[0]]
    try:
        i_desc = next(i for i, h in enumerate(headers) if "desc" in h)
        i_val = next(i for i, h in enumerate(headers) if h.startswith("valor"))
        i_ven = next(i for i, h in enumerate(headers) if _header_is_vencimento(h))
        i_pix = next(i for i, h in enumerate(headers) if "pix" in h)
    except StopIteration:
        return
    i_pago = next((i for i, h in enumerate(headers) if _header_is_pago(h)), None)
    min_cells = max(i_desc, i_val, i_ven, i_pix) + 1
    for parts in rows[1:]:
        if len(parts) < min_cells:
            continue
        desc = parts[i_desc].strip()
        ven = parts[i_ven].strip()
        if not desc or not ven:
            continue
        yield BillRow(
            descricao=desc,
            valor=parse_valor_br(parts[i_val]),
            vencimento_raw=ven,
            pix=parts[i_pix].strip() if i_pix < len(parts) else "",
            pago=_row_pago(parts, i_pago),
        )
