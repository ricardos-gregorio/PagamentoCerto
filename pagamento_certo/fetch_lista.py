from __future__ import annotations

import csv
import io
import os
import re

import requests

_SHEET_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,text/plain,*/*;q=0.9",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

_DOC_HEADERS = {
    "User-Agent": _SHEET_HEADERS["User-Agent"],
    "Accept": "text/plain,*/*;q=0.8",
}


def extract_google_doc_id(url: str) -> str:
    u = url.strip()
    m = re.search(r"/document/d/([a-zA-Z0-9_-]+)", u)
    if m:
        return m.group(1)
    raise ValueError("Não foi possível obter o ID do Google Doc a partir da URL.")


def export_url_for_doc_id(doc_id: str) -> str:
    return f"https://docs.google.com/document/d/{doc_id}/export?format=txt"


def extract_spreadsheet_id_and_gid(url: str) -> tuple[str, str]:
    u = url.strip()
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", u)
    if not m:
        raise ValueError(
            "Não foi possível obter o ID da planilha. Use um link do tipo "
            "https://docs.google.com/spreadsheets/d/.../edit..."
        )
    sheet_id = m.group(1)
    gm = re.search(r"gid=(\d+)", u)
    gid = gm.group(1) if gm else "0"
    return sheet_id, gid


def _raise_if_html_login(text: str, fonte: str) -> None:
    head = text[:8000].lower()
    if text.strip().startswith("<") and ("<html" in head or "<!doctype html" in head):
        raise RuntimeError(
            f"A URL do {fonte} devolveu HTML em vez dos dados. "
            "Compartilhe como «Qualquer pessoa com o link — Leitor»."
        )


def _values_to_csv(values: list[list[object]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    for row in values:
        w.writerow(row)
    return buf.getvalue()


def _range_a1_for_title(title: str) -> str:
    """Monta intervalo A1:Z5000 com nome de aba escapado para a API."""
    t = title.replace("'", "''")
    if re.fullmatch(r"[A-Za-z0-9_.]+", title):
        return f"{title}!A1:Z5000"
    return f"'{t}'!A1:Z5000"


def _download_via_sheets_api(sheet_id: str, gid: str, api_key: str, timeout_s: float) -> str | None:
    """
    Google Sheets API v4 — estável no CI (sem redirect para usercontent).
    Crie uma chave em Google Cloud (Sheets API ativada) e defina SHEETS_API_KEY.
    """
    meta_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
    r = requests.get(
        meta_url,
        params={"fields": "sheets.properties", "key": api_key},
        timeout=timeout_s,
    )
    if r.status_code != 200:
        return None
    meta = r.json()
    gid_int = int(gid)
    title: str | None = None
    for s in meta.get("sheets", []):
        p = s.get("properties") or {}
        if p.get("sheetId") == gid_int:
            title = p.get("title")
            break
    if title is None and meta.get("sheets"):
        title = (meta["sheets"][0].get("properties") or {}).get("title")
    if not title:
        return None

    rng = _range_a1_for_title(title)
    batch_url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values:batchGet"
    )
    r2 = requests.get(
        batch_url,
        params={"ranges": rng, "key": api_key},
        timeout=timeout_s,
    )
    if r2.status_code != 200:
        return None
    payload = r2.json()
    ranges = payload.get("valueRanges") or []
    values = (ranges[0].get("values") if ranges else None) or []
    if not values:
        return ""
    return _values_to_csv(values)


def _response_to_text(r: requests.Response) -> str:
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def _try_http_get(url: str, headers: dict[str, str], timeout_s: float) -> str | None:
    """GET sem raise_for_status — 400 em redirect não deve derrubar o processo."""
    r = requests.get(url, headers=headers, timeout=timeout_s, allow_redirects=True)
    if r.status_code != 200:
        return None
    text = _response_to_text(r)
    _raise_if_html_login(text, "Google Sheets")
    return text if text.strip() else None


def _try_session_then_csv(sheet_id: str, gid: str, timeout_s: float) -> str | None:
    """Abre a planilha no navegador (cookies) e tenta export/gviz — reduz 400 em alguns casos."""
    session = requests.Session()
    session.headers.update(_SHEET_HEADERS)
    edit = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    session.get(edit, timeout=timeout_s)
    referer = edit
    h = {**_SHEET_HEADERS, "Referer": referer}
    urls = [
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}",
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}",
    ]
    for url in urls:
        r = session.get(url, headers=h, timeout=timeout_s, allow_redirects=True)
        if r.status_code != 200:
            continue
        text = _response_to_text(r)
        try:
            _raise_if_html_login(text, "Google Sheets")
        except RuntimeError:
            continue
        if text.strip():
            return text
    return None


def _try_plain_urls(sheet_id: str, gid: str, timeout_s: float) -> str | None:
    """gviz antes de export — export costuma redirecionar para usercontent e dar 400."""
    referer = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    h = {**_SHEET_HEADERS, "Referer": referer}
    for url in (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}",
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}",
    ):
        t = _try_http_get(url, h, timeout_s)
        if t:
            return t
    return None


def _download_google_sheet_csv(sheet_id: str, gid: str, timeout_s: float) -> str:
    api_key = os.environ.get("SHEETS_API_KEY", "").strip()
    if api_key:
        got = _download_via_sheets_api(sheet_id, gid, api_key, timeout_s)
        if got is not None:
            return got

    got = _try_session_then_csv(sheet_id, gid, timeout_s)
    if got:
        return got

    got = _try_plain_urls(sheet_id, gid, timeout_s)
    if got:
        return got

    hint = (
        "1) Planilha: «Qualquer pessoa com o link — Leitor». "
        "2) LISTA_URL com gid da aba correta. "
        "3) Opcional: crie um Secret SHEETS_API_KEY (Google Cloud → Sheets API → chave de API) "
        "— leitura pública da planilha funciona sem OAuth."
    )
    raise RuntimeError(
        "Não foi possível baixar o CSV (export HTTP 400/redirect é comum no GitHub Actions). "
        + hint
    )


def download_lista_text(lista_fonte_url: str, timeout_s: float = 45.0) -> str:
    u = lista_fonte_url.strip()

    if "/spreadsheets/d/" in u:
        sheet_id, gid = extract_spreadsheet_id_and_gid(u)
        return _download_google_sheet_csv(sheet_id, gid, timeout_s)

    if "/document/d/" in u:
        doc_id = extract_google_doc_id(u)
        url = export_url_for_doc_id(doc_id)
        r = requests.get(url, headers=_DOC_HEADERS, timeout=timeout_s)
        r.raise_for_status()
        text = _response_to_text(r)
        _raise_if_html_login(text, "Google Docs")
        return text

    raise ValueError(
        "LISTA_URL deve ser um link do Google Sheets (planilha) ou do Google Docs. "
        "Ex.: https://docs.google.com/spreadsheets/d/ID/edit?gid=0"
    )
